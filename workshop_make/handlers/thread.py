# SPDX-License-Identifier: LGPL-2.1-or-later
# Screw threads: the standards' sizes, what size a cylindrical face is, and
# a thread on a hole through FreeCAD's own PartDesign Hole (a cosmetic
# thread — the hole at its tapping size, the thread recorded — or a
# modelled one, cut into the part).

import math

import FreeCAD
import Part

from workshop_make import geo
from workshop_make import records as store

from .. import pdhole
from .. import threads as tt
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
facepick = None
ToolError = Refusal


V = FreeCAD.Vector

# Add-ons that read a thread off a scan register a reader of kind
# "thread_scan" with Agent Link: f(session, args) -> its reading.
# thread_identify { scan } asks the first, so a CAD face and a scanned
# thread are named by one tool.
SCAN_READERS = []  # lent: Agent Link's live list of "thread_scan" readers
HOLE_TYPE = tt.HOLE_TYPE


def _r(x, n=3):
    return round(float(x), n) + 0.0


def cylinder_of(shape, face):
    """Diameter, inside (a hole) or outside (a shaft), axis, and the two
    ends along the axis of a cylindrical face."""
    s = face.Surface
    if not isinstance(s, Part.Cylinder):
        raise ToolError("invalid_input", "faces: that face is not cylindrical — pick the hole's or shaft's wall ({ near, cylinder: true }).")
    A = V(s.Axis)
    A.normalize()
    C = V(s.Center)
    u0, u1, v0, v1 = face.ParameterRange
    um, vm = (u0 + u1) / 2, (v0 + v1) / 2
    p = face.valueAt(um, vm)
    n = face.normalAt(um, vm)
    radial = (p - C) - A * ((p - C).dot(A))
    inside = n.dot(radial) < 0
    ts = sorted((face.valueAt(um, v) - C).dot(A) for v in (v0, v1))
    return {"diameter": 2 * s.Radius, "inside": inside, "axis": A, "centre": C, "t": ts, "length": ts[1] - ts[0]}


def _entry(shape, cyl, prefer=None):
    """The open end of a hole and the direction into it."""
    A, C = cyl["axis"], cyl["centre"]
    ends = []
    for i, t in enumerate(cyl["t"]):
        other = cyl["t"][1 - i]
        out_dir = A * (1 if t > other else -1)
        e = C + A * t
        beyond = e + out_dir * 0.3
        ends.append({"at": e, "out": out_dir, "open": not shape.isInside(beyond, 0.001, True)})
    opens = [e for e in ends if e["open"]] or ends
    if prefer is not None:
        p = V(*prefer)
        return min(opens, key=lambda e: (e["at"] - p).Length)
    return max(opens, key=lambda e: (e["at"].z, e["at"].x, e["at"].y))


def _table(series=None):
    rows = tt.table(series)
    if not rows and not tt.table():
        try:
            import PartDesign  # noqa: F401

            why = "this FreeCAD's PartDesign Hole gives no thread diameter (ThreadDiameter): FreeCAD 1.1 or newer has it."
        except ImportError:
            why = "PartDesign is not in this build."
        raise ToolError("unavailable", f"FreeCAD's thread tables (PartDesign Hole's) cannot be read here: {why}")
    return rows


def _row(size):
    _table()
    r = tt.lookup(size)
    if r is None:
        raise ToolError("not_found", f"size {size!r}: not in FreeCAD's thread tables (ISO metric coarse and fine, UNC, UNF) — thread_lookup lists them; a size of your own goes in ~/.config/workshop_make/threads.json.")
    return r


NOTE = ("Sizes, majors and tap drills are FreeCAD's own (PartDesign Hole's thread tables); pitch diameter and minors from the ISO 68-1 basic profile. "
        "A Unified pitch and drill name are Workshop Make's, where FreeCAD has none; heat-set insert holes are Fasteners Workbench's IUT table when it is installed, else Workshop Make's typical figures (each row's source says). "
        "A printed hole is better tapped or fitted with an insert than printed threaded under M5.")


def thread_lookup(s, a):
    if a.get("size"):
        r = _row(a["size"])
        return {"thread": r, "units": "mm", "note": NOTE}
    series = (a.get("series") or "all").lower()
    if series not in tt.SERIES + ("all",):
        raise ToolError("invalid_input", f"series: {', '.join(tt.SERIES)} or all.")
    rows = _table(series)
    if a.get("near") is not None:
        d = float(a["near"])
        rows = sorted(rows, key=lambda r: abs(r["major"] - d))[:6]
    return {"threads": [{k: r[k] for k in ("size", "major", "pitch", "minorInt", "tapDrill")} for r in rows], "units": "mm", "columns": "size, major, pitch, internal minor, tap drill",
            "source": "FreeCAD's PartDesign Hole thread tables"}


def thread_identify(s, a):
    if a.get("scan") is not None:
        if not SCAN_READERS:
            raise ToolError("unavailable", "Reading a thread off a scan needs ScanRulerFC installed (its scan_thread): app_extensions, or measure the pitch and give thread_identify { faces, pitch }.")
        out = SCAN_READERS[0](s, {**a["scan"], **({"families": a["families"]} if a.get("families") else {})})
        out = {"from": "scan", **out}
        b = out.get("best") or {}
        if out.get("verdict") == "match" and b.get("family") in ("metric", "unc", "unf"):
            size = b["designation"].replace("×", "x").replace(" UNC", "").replace(" UNF", "")
            out["next"] = f"thread_cut {{ size: \"{size}\" }} threads the modelled hole or shaft to match."
        return out
    if not a.get("faces"):
        raise ToolError("invalid_input", "faces: the hole or shaft's face by query — or scan: { axis } to read a scanned thread.")
    o = s.body(a.get("body"))
    q = dict(a.get("faces") or {})
    q.setdefault("cylinder", True)
    picked = facepick.pick(o.Shape, q, "faces")
    name, face = picked[0]
    cyl = cylinder_of(o.Shape, face)
    d = cyl["diameter"]
    _table()
    near = tt.nearest(d, cyl["inside"], 4)
    out = {
        "body": o.Label, "face": name, "diameter": _r(d), "kind": "hole" if cyl["inside"] else "shaft",
        "length": _r(cyl["length"], 2), "axis": [_r(x) for x in cyl["axis"]],
        "nearest": near,
    }
    if len(picked) > 1:
        out["alsoPicked"] = [n for n, _ in picked[1:]]
    t = tt.tie(near)
    if t and not a.get("pitch"):
        out["needs"] = "pitch"
        out["ask"] = f"Same diameter for pitches {', '.join(str(x['pitch']) for x in t)} mm ({', '.join(x['size'] for x in t)}): ask which, or measure it — thread_identify {{ pitch }} picks."
    elif a.get("pitch"):
        m = [x for x in near if abs(x["pitch"] - float(a["pitch"])) < 0.01]
        out["best"] = m[0] if m else None
        if not m:
            out["note"] = "No near size has that pitch."
    else:
        out["best"] = near[0]
    if out.get("best") and abs(out["best"]["off"]) > 0.3:
        out["note"] = f"{out['best']['off']:+.2f} mm off the nearest: maybe not a thread size — a clearance hole, a press fit or a print's shrinkage."
    return out


def _print_clearance(doc, o, row, mode):
    """(diametral clearance mm, source) for a modelled thread in a printed
    part: Fasteners Workbench's 3D-print nut scaling when it is installed
    and set to 3dprint; else None (the thread as FreeCAD's table has it)."""
    if mode != "modelled" or not store.setup_of(doc, o.Label, "print"):
        return None
    try:
        from workshop_fasteners import api as fasteners

        return fasteners.thread_compensation(float(row["major"]))
    except Exception:  # noqa: BLE001
        return None


def _thread_hole(h, row, mode, depth, comp, rec):
    """A PartDesign Hole h (its Profile set) made the thread of row: its
    type and size as this FreeCAD lists them, threaded, modelled or not,
    depth mm, a flat end. comp: (diametral clearance mm, source) for a
    printed modelled thread, or None; kept on rec. Refused when FreeCAD's
    Hole lists no such size."""
    h.ThreadType = HOLE_TYPE[row["series"]]
    # The size as this release lists it: "M6x1.0" in later ones, the
    # coarse "M6" in 1.0.
    sizes = list(h.getEnumerationsOfProperty("ThreadSize"))
    want = row["freecad"]
    if not want:
        raise ToolError("unavailable", f"{row['size']} is a size of your own, not in FreeCAD's tables: FreeCAD's Hole cannot thread it. Drill it at its tap drill ({row['tapDrill']} mm) and tap it.")
    pick = want if want in sizes else None
    if pick is None and row["series"].startswith("metric"):
        bare = want.split("x")[0]
        pitch = want.split("x")[1] if "x" in want else None
        pick = next((z for z in sizes if z == bare), None) if row["series"] == "metric" else None
        pick = pick or next((z for z in sizes if pitch and z.startswith(bare + "x") and float(z.split("x")[1]) == float(pitch)), None)
    if pick is None:
        raise ToolError("unavailable", f"FreeCAD {'.'.join(FreeCAD.Version()[:3])} lists no hole thread {want} ({', '.join(sizes[:8])} …): cut it cosmetic, or with a size it lists.")
    h.ThreadSize = pick
    h.Threaded = True
    h.ModelThread = mode == "modelled"
    if comp:
        try:  # FreeCAD's own custom thread clearance on the Hole
            h.UseCustomThreadClearance = True
            h.CustomThreadClearance = comp[0]
            rec["printClearance"] = {"mm": comp[0], "source": comp[1]}
        except Exception:  # noqa: BLE001 — a FreeCAD without it: the thread as the table has it
            pass
    h.HoleCutType = "None"
    h.DepthType = "Dimension"
    h.Depth = depth
    h.DrillPoint = "Flat"
    try:
        h.ThreadDepthType = "Hole Depth"
    except Exception:
        pass


def _cut_in_body(s, o, pd, cyl, end, row, mode, depth, rec, threads):
    """The thread in a PartDesign Body: FreeCAD's own Hole (Threaded) kept
    in the Body as a feature on a sketch at the hole's open end, editable
    in its panel. A shape written into a Body is gone at its next recompute
    (Body::execute takes the tip's shape again), which is what the plain
    route below would do to it."""
    doc = s.doc
    pdhole.settle(doc, [pd])
    tip = pd.Tip
    if tip is None or tip.Shape.isNull() or "Invalid" in tip.State or "Error" in tip.State:
        raise ToolError("invalid_state", f"{pd.Label}'s last feature{' (' + tip.Label + ')' if tip is not None else ''} has no sound solid "
                                         f"({pdhole.why_not(tip, doc) if tip is not None else 'the Body is empty'}): fix it first, then the thread.")
    # The face was picked on o.Shape: the Body's shape carries the Body's
    # Placement, a feature's is in the Body's own frame already; the sketch
    # and the Hole live in the Body's own frame.
    at, out_dir = end["at"], end["out"]
    if o is pd:
        inv = pd.Placement.inverse()
        at, out_dir = inv.multVec(at), inv.Rotation.multVec(out_dir)
    before = pd.Shape.Volume
    made = []
    try:
        sk = pd.newObject("Sketcher::SketchObject", "ThreadSketch")
        made.append(sk)
        sk.MapMode = "Deactivated"
        sk.Placement = FreeCAD.Placement(at, FreeCAD.Rotation(V(0, 0, 1), out_dir))
        sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), cyl["diameter"] / 2), False)
        pdhole.settle(doc, [sk])
        h = pd.newObject("PartDesign::Hole", "Thread")
        made.append(h)
        h.Profile = sk
        _thread_hole(h, row, mode, depth, _print_clearance(doc, o, row, mode), rec)
        pdhole.settle(doc, [sk, h, pd])
        if h.isValid() is False or h.Shape.isNull() or not h.Shape.Solids:
            raise ToolError("failed", f"FreeCAD's Hole could not make {row['size']} here ({mode}): {pdhole.why_not(h, doc)} — try mode cosmetic, or check the hole with body_check. Nothing was kept.")
        hole_d = float(h.Diameter)
        sk.Visibility = False
        try:
            h.Label2 = f"{row['size']} thread, {mode}"
        except Exception:  # noqa: BLE001
            pass
    except Exception:
        for x in reversed(made):
            try:
                pd.removeObject(x)
            except Exception:  # noqa: BLE001
                pass
            try:
                doc.removeObject(x.Name)
            except Exception:  # noqa: BLE001
                pass
        try:
            pd.Tip = tip
            doc.recompute()
        except Exception:  # noqa: BLE001
            pass
        raise
    rec.update({"depth": _r(depth, 2), "at": [_r(x) for x in end["at"]], "into": [_r(x) for x in end["out"] * -1], "holeDiameter": _r(hole_d), "feature": h.Name})
    threads.append(rec)
    store.write(doc, "threads", threads)
    s.snapshot("thread_cut")
    sound = geo.soundness(pd.Shape)
    out = {"thread": rec, "removed": _r(before - pd.Shape.Volume, 2), "sound": sound["ok"], "step": len(s.steps),
           "route": "PartDesign Hole", "features": [x.Name for x in made]}
    if not sound["ok"]:
        out["problems"] = sound["problems"][:3]
    return _notes(out, doc, o, row, mode, cyl, hole_d, "FreeCAD's own Hole in the Body (double-click it to edit). ")


def _notes(out, doc, o, row, mode, cyl, hole_d, lead=""):
    if mode == "cosmetic":
        out["note"] = lead + "The hole is at the thread's tapping size and the thread is recorded with the document; tap it after making."
    elif lead:
        out["note"] = lead.strip()
    if mode != "cosmetic" and store.setup_of(doc, o.Label, "print") and row["major"] < 5:
        out["warning"] = "A modelled thread under M5 rarely prints cleanly: print the tapping hole and tap it, or use a heat-set insert."
    if cyl["diameter"] > hole_d + 0.01:
        out["warning2"] = f"The hole was {cyl['diameter']:.2f} mm, over the {hole_d:.2f} mm the thread drills: the thread is shallow there."
    return out


def thread_cut(s, a):
    o = s.body(a.get("body"))
    mode = a.get("mode", "cosmetic")
    if mode not in ("cosmetic", "modelled"):
        raise ToolError("invalid_input", "mode: cosmetic (the hole at its tapping size, the thread recorded) or modelled (the thread cut into the part).")
    q = dict(a.get("faces") or {})
    q.setdefault("cylinder", True)
    name, face = facepick.pick(o.Shape, q, "faces")[0]
    cyl = cylinder_of(o.Shape, face)
    if a.get("size"):
        row = _row(a["size"])
    else:
        _table()
        near = tt.nearest(cyl["diameter"], cyl["inside"], 4)
        if tt.tie(near):
            raise ToolError("invalid_input", f"size: say which — {', '.join(x['size'] for x in tt.tie(near))} fit this diameter alike.")
        if abs(near[0]["off"]) > 0.3:
            raise ToolError("invalid_input", f"size: say which — the face ({cyl['diameter']:.2f} mm) is near no thread size.")
        row = _row(near[0]["size"])
    rec = {"body": o.Label, "size": row["size"], "series": row["series"], "mode": mode, "kind": "hole" if cyl["inside"] else "shaft", "diameter": _r(cyl["diameter"])}
    threads = store.read(s.doc, "threads", [])
    if not cyl["inside"]:
        if mode == "modelled":
            raise ToolError("unavailable", "An outside thread cannot be modelled here: FreeCAD's PartDesign threads holes only. mode: cosmetic records it; a printed bolt is better bought.")
        if cyl["diameter"] > row["major"] + 0.05:
            raise ToolError("invalid_state", f"The shaft ({cyl['diameter']:.2f} mm) is over {row['size']}'s major diameter ({row['major']} mm): turn it to the major first.")
        rec["note"] = "Recorded only: the shaft is left at its diameter."
        threads.append(rec)
        store.write(s.doc, "threads", threads)
        s.snapshot("thread_cut")
        return {"thread": rec, "thread_row": {k: row[k] for k in ("major", "pitch", "minorExt")}, "changed": False}
    if cyl["diameter"] > row["major"] + 0.01:
        raise ToolError("invalid_state", f"The hole ({cyl['diameter']:.2f} mm) is over {row['size']}'s major diameter ({row['major']} mm): nothing left to thread — a larger size, or an insert.")
    try:
        import PartDesign  # noqa: F401
        import Sketcher  # noqa: F401
    except ImportError:
        raise ToolError("unavailable", "PartDesign is not in this build: threads are cut with its Hole feature.")
    end = _entry(o.Shape, cyl, a.get("from"))
    depth = float(a.get("depth", cyl["length"]))
    if depth <= 0:
        raise ToolError("invalid_input", "depth: mm, over 0 (the hole's length by default).")
    pd = pdhole.body_of(o)
    if pd is not None:
        return _cut_in_body(s, o, pd, cyl, end, row, mode, depth, rec, threads)
    why = geo.rebuilt(o, "the thread")
    if why:
        raise ToolError("invalid_state", why + " Or pd_clone it into a PartDesign Body, where the thread is FreeCAD's own editable Hole.")
    doc = s.doc
    had = {x.Name for x in doc.Objects}
    made = []
    try:
        base = doc.addObject("Part::Feature", "AgentLinkThreadBase")
        made.append(base)
        base.Shape = o.Shape.copy()
        body = doc.addObject("PartDesign::Body", "AgentLinkThreadBody")
        made.append(body)
        body.BaseFeature = base
        sk = doc.addObject("Sketcher::SketchObject", "AgentLinkThreadSketch")
        made.append(sk)
        body.addObject(sk)
        sk.MapMode = "Deactivated"
        sk.Placement = FreeCAD.Placement(end["at"], FreeCAD.Rotation(V(0, 0, 1), end["out"]))
        sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), cyl["diameter"] / 2), False)
        doc.recompute()
        h = doc.addObject("PartDesign::Hole", "AgentLinkThreadHole")
        made.append(h)
        h.Profile = sk
        body.addObject(h)
        _thread_hole(h, row, mode, depth, _print_clearance(doc, o, row, mode), rec)
        doc.recompute()
        shape = h.Shape
        bad = h.isValid() is False or shape.isNull() or not shape.Solids
        if bad:
            raise ToolError("failed", f"FreeCAD's Hole could not make {row['size']} here ({mode}): {getattr(h, 'getStatusString', lambda: '')()} — try mode cosmetic, or check the hole with body_check.")
        shape = shape.copy()
        hole_d = float(h.Diameter)
    finally:
        # Everything the Hole needed goes again, the Body's own helpers too.
        for x in reversed(made):
            try:
                if x.isDerivedFrom("PartDesign::Body"):
                    x.Group = []
            except Exception:
                pass
        for _ in range(3):
            extra = [x.Name for x in doc.Objects if x.Name not in had]
            if not extra:
                break
            for n in extra:
                try:
                    doc.removeObject(n)
                except Exception:
                    pass
        doc.recompute()
    if len(shape.Solids) == 1 and shape.ShapeType != "Solid":
        shape = shape.Solids[0]
    shape.Placement = FreeCAD.Placement()
    before = o.Shape.Volume
    o.Shape = shape
    doc.recompute()
    rec.update({"depth": _r(depth, 2), "at": [_r(x) for x in end["at"]], "into": [_r(x) for x in end["out"] * -1], "holeDiameter": _r(hole_d)})
    threads.append(rec)
    store.write(s.doc, "threads", threads)
    s.snapshot("thread_cut")
    sound = geo.soundness(o.Shape)
    out = {"thread": rec, "removed": _r(before - o.Shape.Volume, 2), "sound": sound["ok"], "step": len(s.steps), "route": "Part solid"}
    if not sound["ok"]:
        out["problems"] = sound["problems"][:3]
    return _notes(out, doc, o, row, mode, cyl, hole_d)


HANDLERS = {
    "thread_lookup": thread_lookup,
    "thread_identify": thread_identify,
    "thread_cut": thread_cut,
}
