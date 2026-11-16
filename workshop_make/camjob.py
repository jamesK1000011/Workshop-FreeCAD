# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mill Export on FreeCAD's CAM workbench: the part's CAM Job (one that
already holds it is reused as it is; else a new Job with the stock and the
least tool of the mill setup), and its setup sheet by CAM's own route, the
CAM Sanity report (CAM_Sanity's HTML). Make adds to that report only what
it does not carry: the mill check's verdict and findings (reach and
undercuts, thin walls, deep pockets), the least wall, what was assumed,
the stock material where CAM names none, and the STEP.

FreeCAD's CAM is reached by its Python modules (Path.Main.Job,
Path.Main.Stock, Path.Main.Sanity.Sanity); each step is guarded and gives
(None, why) so Mill Export falls back to Make's own sheet and says so. The
HTML additions are pure Python (tested without FreeCAD)."""

import html


def _clone_base(o):
    for name in ("Objects", "Base"):
        v = getattr(o, name, None)
        if isinstance(v, (list, tuple)) and v:
            return v[0]
        if v is not None and not isinstance(v, (list, tuple)):
            return v
    return None


def is_job(o):
    try:
        return hasattr(o, "Proxy") and hasattr(o, "Model") and hasattr(o, "Tools") and hasattr(o, "Stock")
    except Exception:  # noqa: BLE001
        return False


def find_job(doc, body):
    """A CAM Job in doc whose model holds body (its clone of it), or None."""
    for o in getattr(doc, "Objects", []):
        if not is_job(o):
            continue
        try:
            models = list(o.Model.Group)
        except Exception:  # noqa: BLE001
            continue
        if any(m is body or _clone_base(m) is body for m in models):
            return o
    return None


def stock_origin(bb, stock):
    """The stock box's corner so the part sits in its middle in X and Y and
    the margin is shared top and bottom."""
    sx, sy, sz = stock
    return (bb["xmin"] - (sx - bb["x"]) / 2, bb["ymin"] - (sy - bb["y"]) / 2, bb["zmin"] - (sz - bb["z"]) / 2)


def make_job(doc, body, stock, tool, label=None):
    """A new CAM Job for body: a box stock of stock [x, y, z] mm round it
    and the default tool controller's bit at tool mm. (job, None) or (None,
    why not); nothing left behind on failure."""
    had = {o.Name for o in doc.Objects}
    try:
        import FreeCAD
        import Path.Main.Job as PathJob
        import Path.Main.Stock as PathStock

        # Path.Main.Job.Create makes the Job in FreeCAD.ActiveDocument
        # (FreeCAD 1.1 source: src/Mod/CAM/Path/Main/Job.py), whatever
        # document the body is in: the body's document is made the active
        # one first, so the Job never lands in another open file.
        if getattr(FreeCAD, "ActiveDocument", doc) is not doc and getattr(doc, "Name", None):
            FreeCAD.setActiveDocument(doc.Name)
        job = PathJob.Create("Job", [body], None)
        if label:
            job.Label = label
        b = body.Shape.BoundBox
        org = stock_origin({"xmin": b.XMin, "ymin": b.YMin, "zmin": b.ZMin, "x": b.XLength, "y": b.YLength, "z": b.ZLength}, stock)
        old = job.Stock
        job.Stock = PathStock.CreateBox(job, FreeCAD.Vector(*stock), FreeCAD.Placement(FreeCAD.Vector(*org), FreeCAD.Rotation()))
        if old is not None and old is not job.Stock:
            try:
                doc.removeObject(old.Name)
            except Exception:  # noqa: BLE001
                pass
        tcs = list(job.Tools.Group)
        if tcs:
            set_tool(tcs[0], tool)
        doc.recompute()
        return job, None
    except Exception as e:  # noqa: BLE001
        for n in [o.Name for o in doc.Objects if o.Name not in had]:
            try:
                doc.removeObject(n)
            except Exception:  # noqa: BLE001
                pass
        return None, f"FreeCAD's CAM could not make a Job here ({e})"


def tool_name(d):
    """A tool's name by its diameter, as CAM's own are named: "3 mm End Mill"."""
    return f"{float(d):g} mm End Mill"


def set_tool(tc, d):
    """The tool controller's bit at d mm, and both named for it ("TC: 3 mm
    End Mill"), so the Job does not say 5 mm for a 3 mm cutter."""
    try:
        tc.Tool.Diameter = float(d)
    except Exception:  # noqa: BLE001 — a bit without a Diameter: CAM's default stays, its name too
        return False
    for o, label in ((tc.Tool, tool_name(d)), (tc, "TC: " + tool_name(d))):
        try:
            o.Label = label
        except Exception:  # noqa: BLE001
            pass
    return True


def sanity_report(job, path):
    """CAM's own setup sheet for job (the CAM Sanity report, HTML), as text,
    or (None, why not)."""
    try:
        from Path.Main.Sanity import Sanity

        return Sanity.CAMSanity(job, path).get_output_report(), None
    except Exception as e:  # noqa: BLE001
        return None, f"FreeCAD's CAM Sanity report could not be made here ({e})"


def _li(text):
    return f"<li>{html.escape(str(text))}</li>"


def extras(report_html, check, material, step):
    """CAM's report with Make's section added before its end: only what CAM
    does not carry."""
    rows = [f"<p>Mill check verdict: <b>{html.escape(str(check.get('verdict')))}</b>"
            + (f"; least wall read {html.escape(str(check['leastWall']))} mm" if check.get("leastWall") is not None else "") + ".</p>"]
    f = check.get("findings") or []
    rows.append("<ul>" + ("".join(_li(f"{x.get('severity')}: {x.get('rule')}: {x.get('says')}") for x in f) if f else _li("No findings.")) + "</ul>")
    if material and material.lower() not in report_html.lower():
        rows.append(f"<p>Stock material: {html.escape(str(material))}.</p>")
    if check.get("assumed"):
        rows.append("<p>Assumed:</p><ul>" + "".join(_li(f"{k}: {v}") for k, v in check["assumed"].items()) + "</ul>")
    rows.append(f"<p>STEP: {html.escape(str(step))}</p>")
    section = '<section id="workshop-make"><h2>Workshop Make: mill check</h2>' + "".join(rows) + "</section>"
    low = report_html.lower()
    i = low.rfind("</body>")
    return report_html[:i] + section + report_html[i:] if i >= 0 else report_html + section
