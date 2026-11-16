# SPDX-License-Identifier: LGPL-2.1-or-later
"""Hole for Hardware in a PartDesign Body: FreeCAD's own PartDesign::Hole
(its ISO 273 clearance sizes, its counterbores and countersinks for the
screw standards it knows, its thread tables), editable afterwards in its
own task panel, and only what it lacks on top:

- the printer allowance (the print setup's calibration, else the
  document's) added to the hole's and its cut's diameters;
- a hexagonal nut trap (a PartDesign Pocket from a hexagon sketch on the
  same face);
- heat-set insert and magnet pockets (a plain Hole at the insert's or the
  magnet's size, which FreeCAD has no table for).

A hole in a plain Part solid (no Body) is cut the old way by api.hole.
The name picking below is pure Python (tested without FreeCAD)."""

import math

from . import fits

# Make's fit names against what each release calls ISO 273's columns.
FIT_NAMES = {
    "close": ("Fine", "Close"),
    "normal": ("Medium", "Standard", "Normal"),
    "loose": ("Coarse", "Wide", "Loose"),
}
# The screw standard whose head FreeCAD sizes the cut for, by hole kind.
CUT_STANDARD = {"counterbore": "ISO 4762", "countersink": "ISO 10642"}
CUT_PLAIN = {"counterbore": "Counterbore", "countersink": "Countersink"}


def pick_size(enums, size):
    """The thread size as this FreeCAD lists it: "M3" in 1.0, "M3x0.5" in
    later releases (the coarse pitch first). None when it lists none."""
    enums = list(enums or [])
    s = str(size).strip()
    if s in enums:
        return s
    for e in enums:
        if e.split("x")[0] == s:
            return e
    return None


def pick_fit(enums, fit):
    """ThreadFit's value for close, normal or loose (ISO 273's fine, medium
    and coarse), by its name in this release, else by position."""
    enums = list(enums or [])
    for name in FIT_NAMES.get(fit, FIT_NAMES["normal"]):
        if name in enums:
            return name
    order = ("close", "normal", "loose")
    if len(enums) == 3 and fit in order:
        # Releases list the default first: normal, close, loose.
        return enums[{"normal": 0, "close": 1, "loose": 2}[fit]]
    return enums[0] if enums else None


def pick_cut(enums, kind):
    """(HoleCutType value, sized by FreeCAD): the screw standard's own cut
    where this release has it, else the plain cut sized here."""
    enums = list(enums or [])
    std = CUT_STANDARD.get(kind)
    if std:
        hit = next((e for e in enums if e == std or e.startswith(std + " ")), None)
        if hit:
            return hit, True
    plain = CUT_PLAIN.get(kind, "None")
    return (plain if plain in enums else "None"), False


def hexagon(af, cx=0.0, cy=0.0):
    """The six corners of a hexagon af across flats, centred on (cx, cy),
    flats parallel to Y (corners on the Y axis)."""
    r = af / math.sqrt(3)
    return [(cx + r * math.cos(math.radians(30 + 60 * i)), cy + r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]


def body_of(o):
    """The PartDesign Body o is or is in, else None (a plain Part solid)."""
    try:
        if o.isDerivedFrom("PartDesign::Body"):
            return o
    except Exception:  # noqa: BLE001
        pass
    try:
        p = o.getParentGeoFeatureGroup()
        if p is not None and p.isDerivedFrom("PartDesign::Body"):
            return p
    except Exception:  # noqa: BLE001
        pass
    return None


# ---- on FreeCAD ---------------------------------------------------------------------------

def _V(*a):
    import FreeCAD

    return FreeCAD.Vector(*a)


def _local(body, at, d):
    """at and d in the Body's own frame (its features' shapes are there)."""
    import FreeCAD

    try:
        pl = body.getGlobalPlacement()
    except Exception:  # noqa: BLE001
        pl = getattr(body, "Placement", None) or FreeCAD.Placement()
    inv = pl.inverse()
    return inv.multVec(_V(*at)), inv.Rotation.multVec(d)


def face_at(shape, at, d, tol=1e-3):
    """The name of the flat face the hole enters by: the point on it, its
    outward normal against the drilling direction. None if none."""
    import Part

    p = _V(*at) if not hasattr(at, "x") else at
    best = None
    for i, f in enumerate(shape.Faces):
        try:
            if "Plane" not in type(f.Surface).__name__:
                continue
            if f.distToShape(Part.Vertex(p))[0] > tol:
                continue
            u, v = f.Surface.parameter(p)
            n = f.normalAt(u, v)
            dot = n.dot(d)
        except Exception:  # noqa: BLE001
            continue
        if dot < -0.99 and (best is None or dot < best[1]):
            best = (f"Face{i + 1}", dot)
    return best[0] if best else None


def _attach(sk, feature, face):
    support = [(feature, face)]
    try:
        sk.AttachmentSupport = support  # FreeCAD 1.0 on
    except Exception:  # noqa: BLE001
        sk.Support = support
    sk.MapMode = "FlatFace"


def _sketch_on(doc, body, feature, face, name):
    sk = body.newObject("Sketcher::SketchObject", name)
    _attach(sk, feature, face)
    doc.recompute()
    return sk


def _to_sketch(sk, at):
    """A global point in the sketch's plane coordinates."""
    p = sk.getGlobalPlacement().inverse().multVec(_V(*at))
    return p.x, p.y


def _circle(sk, x, y, r):
    import Part

    sk.addGeometry(Part.Circle(_V(x, y, 0), _V(0, 0, 1), r), False)


def _polygon(sk, pts):
    import Part

    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        sk.addGeometry(Part.LineSegment(_V(a[0], a[1], 0), _V(b[0], b[1], 0)), False)


def _enums(o, prop):
    try:
        return list(o.getEnumerationsOfProperty(prop) or [])
    except Exception:  # noqa: BLE001
        return []


class Failed(Exception):
    pass


def make(doc, body, kind, size, at, d, depth, fit, cal, face=None, sketch=None):
    """The hole as PartDesign features in body. at/d: where it enters and
    which way it goes (global); face: the entry face's name on the Body's
    tip, found from at and d when not given; sketch: a sketch of the
    person's whose circles are the holes (at and face then not needed).
    Gives (the features made, the sizes as FreeCAD made them). Raises
    Failed with FreeCAD's reason; nothing is left behind then."""
    if kind not in fits.KINDS:
        raise Failed(f"kind: one of {', '.join(fits.KINDS)}.")
    add = float(cal.get("hole", 0.0))
    tip = body.Tip
    made = []
    try:
        if sketch is None:
            if tip is None:
                raise Failed("The Body has no solid yet to put a hole in.")
            p, dl = _local(body, at, d)
            face = face or face_at(tip.Shape, p, dl)
            if face is None:
                raise Failed(f"No flat face of {body.Label} at {list(at)} facing against the drilling direction: put at on a flat face, dir into the material.")
            sk = _sketch_on(doc, body, tip, face, "HoleSketch")
            made.append(sk)
            cx, cy = _to_sketch(sk, at)
            _circle(sk, cx, cy, 0.5)  # its centre is the hole's; the Hole sizes it
        else:
            sk, cx, cy = sketch, None, None
        h = body.newObject("PartDesign::Hole", "Hole")
        made.append(h)
        h.Profile = sk
        sizes = _configure(h, kind, size, depth, fit, add)
        doc.recompute()
        if kind == "nut_trap":
            if sketch is not None:
                raise Failed("A nut trap needs the point it enters at (at), not a sketch.")
            af, mh = fits.M[size]["nut"]
            a, hgt = af + add, mh + 0.3
            sk2 = _sketch_on(doc, body, tip, face, "NutTrapSketch")
            made.append(sk2)
            _polygon(sk2, hexagon(a, cx, cy))
            pk = body.newObject("PartDesign::Pocket", "NutTrap")
            made.append(pk)
            pk.Profile = sk2
            pk.Length = hgt
            sizes.update({"nutAcrossFlats": round(a, 3), "nutDepth": round(hgt, 3)})
            doc.recompute()
        for x in made:
            if x.TypeId.startswith("Sketcher"):
                x.Visibility = False
        last = made[-1]
        if last.isValid() is False or last.Shape.isNull() or not last.Shape.Solids:
            why = getattr(last, "getStatusString", lambda: "")()
            raise Failed(f"FreeCAD's {last.TypeId.split('::')[-1]} could not be made here: {why or 'no solid'}.")
        return [x.Name for x in made], sizes
    except Exception:
        for x in reversed(made):
            try:
                body.removeObject(x)
            except Exception:  # noqa: BLE001
                pass
            try:
                doc.removeObject(x.Name)
            except Exception:  # noqa: BLE001
                pass
        try:
            body.Tip = tip
            doc.recompute()
        except Exception:  # noqa: BLE001
            pass
        raise


def _configure(h, kind, size, depth, fit, add):
    """Set the Hole: FreeCAD's sizes where it has them, the allowance on
    top. Gives the sizes as set (mm)."""
    if depth == "through":
        h.DepthType = "ThroughAll"
    else:
        h.DepthType = "Dimension"
        h.Depth = float(depth)
    try:
        h.DrillPoint = "Flat"
    except Exception:  # noqa: BLE001
        pass
    if kind in ("insert", "magnet"):
        # No table in FreeCAD for these: a plain hole at the size.
        h.ThreadType = "None"
        if kind == "magnet":
            try:
                dia, t = (float(x) for x in str(size).lower().split("x"))
            except ValueError:
                raise Failed("size: a magnet as diameter x thickness, mm — \"6x2\".")
            hd, hdep = dia + add, t + 0.2
        else:
            if size not in fits.M:
                raise Failed(f"size: one of {', '.join(fits.M)}.")
            ins_d, ins_l, src, note = fits.insert_figures(size)
            hd, hdep = ins_d + add, ins_l + 0.5
        h.DepthType = "Dimension"
        h.Diameter = hd
        h.Depth = hdep
        out = {"hole": round(hd, 3), "depth": round(hdep, 3)}
        if kind == "insert":
            out["insertSource"] = src
            out["note"] = note
        return out
    h.ThreadType = "ISOMetricProfile"
    pick = pick_size(_enums(h, "ThreadSize"), size)
    if pick is None:
        raise Failed(f"size: FreeCAD's Hole lists no {size}.")
    h.ThreadSize = pick
    h.Threaded = False
    fv = pick_fit(_enums(h, "ThreadFit"), fit)
    if fv:
        h.ThreadFit = fv
    out = {"freecadSize": pick, "fit": fv}
    if kind in ("counterbore", "countersink"):
        cut, by_freecad = pick_cut(_enums(h, "HoleCutType"), kind)
        h.HoleCutType = cut
        if not by_freecad:
            m = fits.M.get(size) or {}
            if kind == "counterbore" and m.get("head"):
                h.HoleCutDiameter = m["head"][0] + 0.5
                h.HoleCutDepth = m["head"][1] + 0.3
            elif kind == "countersink" and m.get("csk"):
                h.HoleCutDiameter = m["csk"] + 0.3
                h.HoleCutCountersinkAngle = 90
        out["cut"] = cut
        out["cutSizedBy"] = "FreeCAD" if by_freecad else "Workshop Make (this FreeCAD has no table for it)"
    else:
        h.HoleCutType = "None"
    # The printer allowance on top of FreeCAD's sizes (set last: FreeCAD
    # sets Diameter again when the size or fit changes).
    if add:
        h.Diameter = float(h.Diameter) + add
        if kind in ("counterbore", "countersink"):
            try:
                h.HoleCutCustomValues = True
            except Exception:  # noqa: BLE001
                pass
            h.HoleCutDiameter = float(h.HoleCutDiameter) + add
    out["clearance"] = round(float(h.Diameter), 3)
    if kind in ("counterbore", "countersink"):
        out["cutDiameter"] = round(float(h.HoleCutDiameter), 3)
        if kind == "counterbore":
            out["cutDepth"] = round(float(h.HoleCutDepth), 3)
    out["depth"] = "through" if depth == "through" else round(float(depth), 3)
    return out
