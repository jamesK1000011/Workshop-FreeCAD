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
        # The standard's own name first: FreeCAD lists the cuts in the order
        # it read their files, so "ISO 4762 + 7089" (the head with a washer:
        # a wider counterbore) may come before "ISO 4762".
        hit = std if std in enums else next((e for e in enums if e.startswith(std + " ")), None)
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


def shape_frame(o):
    """The placement o.Shape's coordinates are in, from the document's:
    what holds o (an App::Part's placement), o's own placement being in its
    Shape already. Identity for an object at the top."""
    import FreeCAD

    try:
        g = o.getGlobalPlacement()
        return g.multiply(o.Placement.inverse())
    except Exception:  # noqa: BLE001
        return FreeCAD.Placement()


def to_shape(o, at, d=None):
    """A global point (and direction) in o.Shape's coordinates."""
    f = shape_frame(o).inverse()
    p = f.multVec(_V(*at) if not hasattr(at, "x") else at)
    return (p, f.Rotation.multVec(d)) if d is not None else p


def sentence(e):
    """An exception from FreeCAD as words: its message without the class
    name, Python's repr or a trailing full stop; the class when it says
    nothing."""
    msg = getattr(e, "message", None) or (e.args[0] if getattr(e, "args", None) else "") or str(e)
    if isinstance(msg, dict):
        msg = msg.get("sErrMsg") or msg.get("swhat") or str(msg)
    msg = str(msg).strip().rstrip(".")
    msg = STATES.get(msg, msg)
    return msg or type(e).__name__


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


def entry_face(doc, body, tip, face):
    """(feature, "FaceN") the hole's sketch goes on, from face as given:
    "Face4" (the Body's tip), or "Pocket 5.Face4" / "Body.Face4" — a
    feature's face by its label or name (the whole reference was taken as
    the face's name, so the sketch had no face and the Hole stayed
    "Touched"). (tip, None) when no face is given."""
    if not face:
        return tip, None
    import re

    m = re.match(r"^(?:(.+)[.:])?(Face\d+)$", str(face).strip())
    if not m:
        raise Failed(f"face: {face!r} — a face as \"Face4\" or \"Pocket.Face4\".")
    owner, sub = m.group(1), m.group(2)
    on = tip
    if owner and owner not in (body.Label, body.Name):
        hits = [o for o in doc.Objects if owner in (o.Label, o.Name)]
        if not hits:
            raise Failed(f"face: no feature called {owner}.")
        on = hits[0]
    try:
        f = on.Shape.getElement(sub)
    except Exception:  # noqa: BLE001
        f = None
    if f is None:
        raise Failed(f"face: {on.Label} has no {sub} (it has {len(on.Shape.Faces)} faces) — the numbers change after an edit: pick it again.")
    if "Plane" not in type(f.Surface).__name__:
        raise Failed(f"face: {on.Label}.{sub} is not flat — a hole starts on a flat face.")
    return on, sub


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
    settle(doc, [sk])
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


# FreeCAD's object states, as a sentence (getStatusString gives the bare word).
STATES = {
    "Touched": "FreeCAD left it waiting for a recompute",
    "Invalid": "FreeCAD marked it invalid",
    "Error": "FreeCAD's recompute failed on it",
}


def why_not(o, doc=None):
    """Why a feature has no solid, in a sentence: FreeCAD's status words
    (Touched, Invalid …) said as what they mean, a feature before it that
    is broken named."""
    raw = ""
    try:
        raw = (o.getStatusString() or "").strip()
    except Exception:  # noqa: BLE001
        pass
    said = STATES.get(raw, raw)
    broken = []
    if doc is not None:
        for x in getattr(o, "OutListRecursive", []) or []:
            try:
                if "Invalid" in x.State or "Error" in x.State:
                    broken.append(x.Label)
            except Exception:  # noqa: BLE001
                pass
    if broken:
        said = f"{said or 'no solid'}; {', '.join(broken[:3])} before it {'is' if len(broken) == 1 else 'are'} broken"
    return said or "it gave no solid"


def settle(doc, objs):
    """Recompute objs and what they stand on (not the rest of the document),
    recomputes switched on for it when the document has them frozen (Skip
    recompute). True when they were frozen."""
    frozen = bool(getattr(doc, "RecomputesFrozen", False))
    if frozen:
        doc.RecomputesFrozen = False
    try:
        try:
            doc.recompute([o for o in objs if o is not None])
        except TypeError:  # an older FreeCAD takes no list
            doc.recompute()
        # What the document's recompute left waiting (it ran nothing on the
        # Mac: "recomputed 0", the new Hole still Touched) is recomputed by
        # itself, forced, in order; then the rest once more.
        for _ in range(2):
            left = [o for o in objs if o is not None and "Touched" in getattr(o, "State", ())]
            if not left:
                break
            for o in left:
                try:
                    o.recompute(True)
                except TypeError:  # a FreeCAD whose recompute takes no force
                    o.recompute()
                except Exception:  # noqa: BLE001
                    pass
    finally:
        if frozen:
            doc.RecomputesFrozen = True
    return frozen


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
    # A recompute pending in the document (an edit not yet recomputed, or
    # recomputes frozen) left the new Hole "Touched": the Body is brought
    # up to date first, and only it.
    settle(doc, [body])
    tip = body.Tip
    made = []
    try:
        if tip is not None and (tip.Shape.isNull() or "Invalid" in tip.State or "Error" in tip.State):
            raise Failed(f"{body.Label}'s last feature, {tip.Label}, is broken ({why_not(tip, doc)}): fix it first, then the hole.")
        if sketch is None:
            if tip is None:
                raise Failed("The Body has no solid yet to put a hole in.")
            p, dl = _local(body, at, d)
            on, face = entry_face(doc, body, tip, face)
            face = face or face_at(tip.Shape, p, dl)
            if face is None:
                raise Failed(f"No flat face of {body.Label} at {list(at)} facing against the drilling direction: put at on a flat face, dir into the material.")
            sk = _sketch_on(doc, body, on, face, "HoleSketch")
            made.append(sk)
            cx, cy = _to_sketch(sk, at)
            _circle(sk, cx, cy, 0.5)  # its centre is the hole's; the Hole sizes it
        else:
            sk, cx, cy = sketch, None, None
        h = body.newObject("PartDesign::Hole", "Hole")
        made.append(h)
        h.Profile = sk
        sizes = _configure(h, kind, size, depth, fit, add)
        settle(doc, [sk, h, body])
        if kind == "nut_trap":
            if sketch is not None:
                raise Failed("A nut trap needs the point it enters at (at), not a sketch.")
            af, mh = fits.M[size]["nut"]
            a, hgt = af + add, mh + 0.3
            sk2 = _sketch_on(doc, body, on, face, "NutTrapSketch")
            made.append(sk2)
            _polygon(sk2, hexagon(a, cx, cy))
            pk = body.newObject("PartDesign::Pocket", "NutTrap")
            made.append(pk)
            pk.Profile = sk2
            pk.Length = hgt
            sizes.update({"nutAcrossFlats": round(a, 3), "nutDepth": round(hgt, 3)})
            settle(doc, [sk2, pk, body])
        for x in made:
            if x.TypeId.startswith("Sketcher"):
                x.Visibility = False
        last = made[-1]
        if last.isValid() is False or last.Shape.isNull() or not last.Shape.Solids:
            raise Failed(f"FreeCAD's {last.TypeId.split('::')[-1]} could not be made here: {why_not(last, doc)}.")
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
    cut = by_freecad = None
    if kind in ("counterbore", "countersink"):
        cut, by_freecad = pick_cut(_enums(h, "HoleCutType"), kind)
        h.HoleCutType = cut
        if not by_freecad:
            m = fits.M.get(size) or {}
            if kind == "counterbore" and m.get("head"):
                h.HoleCutDiameter = m["head"][0] + 0.5
                h.HoleCutDepth = m["head"][1] + 0.3
            elif kind == "countersink" and m.get("csk"):
                h.HoleCutCountersinkAngle = 90
                h.HoleCutDiameter = m["csk"] + 0.3
        out["cut"] = cut
        out["cutSizedBy"] = "FreeCAD" if by_freecad else "Workshop Make (this FreeCAD has no table for it)"
    else:
        h.HoleCutType = "None"
    if add:
        out.update(_keep_allowance(h, kind, size, fv, add))
    out["clearance"] = round(float(h.Diameter), 3)
    if kind in ("counterbore", "countersink"):
        out["cutDiameter"] = round(float(h.HoleCutDiameter), 3)
        if kind == "counterbore":
            out["cutDepth"] = round(float(h.HoleCutDepth), 3)
    out["depth"] = "through" if depth == "through" else round(float(depth), 3)
    return out


def _keep_allowance(h, kind, size, fv, add):
    """The printer allowance put where FreeCAD keeps it. A sized hole
    (Profile ISO metric) has its Diameter set again from size and fit by
    FreeCAD whenever the file is opened (Hole::Restore), and a screw
    standard's cut (ISO 4762, ISO 10642) its cut diameter: an allowance
    added on top was lost (4.7 answered, 4.5 in the feature). So, with an
    allowance, the Hole becomes FreeCAD's plain hole (Profile None), whose
    Diameter is its own, at FreeCAD's ISO 273 size plus the allowance; the
    cut the plain Counterbore or Countersink, at FreeCAD's sizes plus the
    allowance (FreeCAD resets those only at or under the hole's diameter).
    The size it stands for goes in Label2 (the tree's description)."""
    iso = float(h.Diameter)
    was = {}
    if kind in ("counterbore", "countersink"):
        was = {"d": float(h.HoleCutDiameter), "depth": float(h.HoleCutDepth),
               "angle": float(getattr(h, "HoleCutCountersinkAngle", 90) or 90)}
        h.HoleCutType = "None"
    h.ThreadType = "None"
    h.Diameter = iso + add
    out = {"clearanceBeforeAllowance": round(iso, 3)}
    said = f"{size} clearance, ISO 273 {str(fv or 'medium').lower()} {_n(iso)} mm + {_n(add)} mm printer allowance"
    if was:
        h.HoleCutType = CUT_PLAIN[kind]
        if kind == "countersink":
            h.HoleCutCountersinkAngle = was["angle"]
            h.HoleCutDiameter = was["d"] + add  # FreeCAD works the depth out from the angle
        else:
            h.HoleCutDiameter = was["d"] + add
            h.HoleCutDepth = was["depth"]
        out["cutBeforeAllowance"] = round(was["d"], 3)
        said += f"; {kind} {_n(was['d'])} + {_n(add)} mm"
    try:
        h.Label2 = said
    except Exception:  # noqa: BLE001
        pass
    props = "Diameter" + (" and HoleCutDiameter" if was else "")
    out["allowanceOn"] = (f"the Hole's {props} (FreeCAD's size + {_n(add)} mm): a plain hole (Profile None) so FreeCAD keeps it on "
                          f"recompute and reopen; {size} and the fit are in its description (Label2). Double-click it to change "
                          f"the diameters; for another size run hw_hole again (a size picked in its panel takes FreeCAD's size without the allowance).")
    return out


def _n(x):
    """A number in mm as words: 4.5, 0.2, 9 (no trailing zeros)."""
    return f"{round(float(x), 3):g}"


def head_side(kind, at, d):
    """Which face the hole's head side is on, in words, for the answer:
    dir runs into the material, so the screw head, counterbore,
    countersink or nut trap is on the face at enters by, facing against
    dir ("countersink on the face at x=0, facing -x"). A wall-mount
    bracket drilled from the wall side has its countersink on the wall."""
    what = {"clearance": "screw head", "counterbore": "counterbore", "countersink": "countersink", "nut_trap": "nut trap",
            "insert": "insert pocket's opening", "magnet": "magnet pocket's opening"}.get(kind, "hole's entry")
    if at is None:
        return {"headSide": f"{what} on the face the sketch is on (FreeCAD's Hole goes into the material from the sketch)."}
    v = [float(getattr(d, k)) for k in "xyz"] if hasattr(d, "x") else [float(x) for x in d]
    n = sum(x * x for x in v) ** 0.5 or 1.0
    v = [x / n for x in v]
    big = max(range(3), key=lambda i: abs(v[i]))
    if abs(abs(v[big]) - 1) < 1e-6:
        ax = "xyz"[big]
        facing = ("-" if v[big] > 0 else "+") + ax
        face = f"{ax}={_n(at[big])}"
        out = {"face": face, "facing": facing}
        s = f"{what} on the face at {face}, facing {facing}"
    else:
        facing = [round(-x, 4) for x in v]
        out = {"facing": facing}
        s = f"{what} on the face through {[round(float(x), 3) for x in at]}, facing {facing}"
    out["headSide"] = s + " (dir runs into the material from there; for it on the opposite face, enter from that face with dir reversed)."
    return out
