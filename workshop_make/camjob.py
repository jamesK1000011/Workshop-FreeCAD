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
        settle_new(doc, had)
        hide_new_shapes(doc, had, keep=(job,))
        return job, None
    except Exception as e:  # noqa: BLE001
        for n in [o.Name for o in doc.Objects if o.Name not in had]:
            try:
                doc.removeObject(n)
            except Exception:  # noqa: BLE001
                pass
        return None, f"FreeCAD's CAM could not make a Job here ({e})"


def settle_new(doc, had):
    """A second recompute when the first left objects made since `had`
    touched. CAM's tool bit does not rebuild its model when its Diameter is
    set: it queues that for the END of the next document recompute (FreeCAD
    1.1 source: src/Mod/CAM/Path/Tool/toolbit/models/base.py, onChanged ->
    _queue_visual_update, ToolBitRecomputeObserver.slotRecomputedDocument ->
    _update_visual_representation), where it removes the bit's body and
    copies a new one into the document (Path/Tool/shape/models/base.py
    make_body: doc.copyObject). Those copies (a Body, its Sketch and
    Revolution) arrive after the recompute and stay "not recomputed yet"
    until the next one: found live, where the health check listed
    Sketch001, Revolution and Endmill001 after every later call. True when
    it recomputed again."""
    try:
        left = [o for o in doc.Objects if o.Name not in had and "Touched" in getattr(o, "State", ())]
    except Exception:  # noqa: BLE001
        left = []
    if not left:
        return False
    doc.recompute()
    return True


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
    or (None, why not). The report's image builder is let go (and so its
    own visibility restore run) before this returns, so restore_visibility
    after it has the last word."""
    import gc

    try:
        from Path.Main.Sanity import Sanity

        sanity = Sanity.CAMSanity(job, path)
        try:
            return sanity.get_output_report(), None
        finally:
            del sanity
            gc.collect()
    except Exception as e:  # noqa: BLE001
        return None, f"FreeCAD's CAM Sanity report could not be made here ({e})"


# CAM's Sanity report hides the document to take its pictures: with the
# window up its image builder (FreeCAD 1.1 source: src/Mod/CAM/Path/Main/
# Sanity/ImageBuilder.py, GuiImageBuilder) records the objects shown and
# hides every object (record_visibility) before EACH picture — the base
# model, the datum, the stock, each tool — showing only the one it draws,
# and puts back only what the LAST record held, and only in __del__
# (restore_visibility). The second record is taken with everything already
# hidden, so the parts stay hidden and the last picture's object, the stock
# box drawn as a wireframe, stays shown (found live, window review round 3:
# after mill_export only a wireframe stock box was left in the view). Make
# records every object's Visibility before CAM runs and puts it back after.

def visibility(doc):
    """{object name: shown} for every object of doc (its Visibility, which
    FreeCAD keeps from marking an object touched or the document changed)."""
    out = {}
    for o in getattr(doc, "Objects", []):
        try:
            out[o.Name] = bool(o.Visibility)
        except Exception:  # noqa: BLE001
            continue
    return out


def restore_visibility(doc, before):
    """Every object of doc that was in before shown or hidden as it was.
    The labels of those put back."""
    back = []
    for o in getattr(doc, "Objects", []):
        want = before.get(getattr(o, "Name", None))
        if want is None:
            continue
        try:
            if bool(o.Visibility) != want:
                o.Visibility = want
                back.append(o.Label)
        except Exception:  # noqa: BLE001
            continue
    return back


def hide_new_shapes(doc, had, keep=()):
    """New objects (not in had) that are shown and have a shape, hidden as
    CAM's own Job leaves its stock and tools (Path/Main/Job.py setupStock,
    setupToolTable): the box stock made here and a tool bit's model would
    otherwise sit over the part. keep: objects left as they are (the Job).
    The names hidden."""
    hidden = []
    skip = {getattr(k, "Name", k) for k in keep}
    for o in getattr(doc, "Objects", []):
        if o.Name in had or o.Name in skip:
            continue
        try:
            sh = getattr(o, "Shape", None)
            if o.Visibility and sh is not None and not sh.isNull():
                o.Visibility = False
                hidden.append(o.Name)
        except Exception:  # noqa: BLE001
            continue
    return hidden


def _li(text):
    return f"<li>{html.escape(str(text))}</li>"


def extras(report_html, check, material, step):
    """CAM's report with Make's section added before its end: only what CAM
    does not carry."""
    rows = [f"<p>Mill check verdict: <b>{html.escape(str(check.get('verdict')))}</b>"
            + (f"; least wall read {html.escape(str(check['leastWall']))} mm" if check.get("leastWall") is not None else "") + ".</p>"]
    if check.get("directions"):
        rows.append(f"<p>Tool directions: {html.escape(', '.join(str(d) for d in check['directions']))}.</p>")
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
