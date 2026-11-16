# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop's bridge to Fasteners Workbench (Shai Seger's; screw_maker by
Ulrich Brammer), a separate add-on, called at run time: plain values in,
plain values out (mm). Nothing of Fasteners is copied here; every size,
length and shape comes from its own functions (ScrewMaker.Instance,
FastenersCmd.FSScrewObject, FastenerBase), the same ones its buttons use.
A refusal is workshop_fasteners.fs.Missing (code, message). No Agent Link
import here.

    from workshop_fasteners import api
    api.types(query="socket cap")              # its types, standards, sizes
    api.types(type="ISO4762", size="M3")        # lengths, hole sizes
    api.add(doc, "ISO4762", "M3", 12, edges=["Plate.Edge7"])
    api.change(doc, ["M3x12-Screw"], length=16)
    api.listing(doc)                            # for the BOM
"""
import difflib
import re

from . import detect, fs
from .fs import Missing

CREDIT = detect.CREDIT
SOURCE = "Fasteners Workbench (Shai Seger; screw_maker by Ulrich Brammer)"
# Their parameter group (FSParam): the 3D-print thread settings live here.
PARAMS = "User parameter:BaseApp/Preferences/Mod/Fasteners"
PRINT_KEYS = {"mode": "ScrewToolbarThreadGeneration", "nutA": "NutThrScaleA", "nutB": "NutThrScaleB", "screwA": "ScrewThrScaleA", "screwB": "ScrewThrScaleB"}
# Fasteners' own defaults (ScrewMaker.updateFastenerParameters).
PRINT_DEFAULTS = {"nutA": 1.03, "nutB": 0.1, "screwA": 0.99, "screwB": -0.05}
# The screw a hole kind takes when none is named (screw: true).
HOLE_SCREW = {"clearance": "ISO4762", "counterbore": "ISO4762", "countersink": "ISO10642", "nut_trap": "ISO4762", "insert": "ISO4762"}
# Pass holes match the screw's outer diameter; an insert (or a tapped
# hole) its inner thread — Fasteners' "Match for pass hole / tap hole".
HOLE_MATCH = {"clearance": "outer", "counterbore": "outer", "countersink": "outer", "nut_trap": "outer", "insert": "inner"}


def _num(v):
    try:
        return float(v.Value) if hasattr(v, "Value") else float(v)
    except (TypeError, ValueError):
        return None


def _clean(x):
    x = round(float(x), 3)
    return int(x) if x == int(x) else x


# ---- what Fasteners has ---------------------------------------------------------------

def _table(F):
    return F.FastenersCmd.FSScrewCommandTable


def _check_type(F, ftype):
    t = _table(F)
    if ftype in t:
        return ftype
    for k in t:  # iso4762, ISO 4762
        if k.replace(" ", "").lower() == str(ftype).replace(" ", "").lower():
            return k
    near = difflib.get_close_matches(str(ftype), list(t), n=5)
    raise Missing(f"type {ftype!r}: not one of Fasteners' types" + (f" — near: {', '.join(near)}" if near else "") + " (fastener_types lists them).", "not_found")


def _row(F, k):
    help_, group = _table(F)[k][0], _table(F)[k][1]
    return {"type": k, "kind": F.screwMaker.GetTypeName(k), "group": str(group), "standard": F.FastenersCmd.FSGetStandardFromType(k), "what": str(help_)}


def _params(F, ftype):
    return set(F.FastenersCmd.FSGetParams(ftype))


def _lengths(F, ftype, size):
    p = _params(F, ftype)
    if "Length" in p:
        return [str(x) for x in F.screwMaker.GetAllLengths(ftype, size, False)]
    return None


def hole_sizes(size, F=None):
    """Fasteners' screw-hole calculator for a size: its tap hole (the
    calculator's metric, inch and BSP charts); the pass hole is the
    nominal diameter (Workshop's hw_hole sizes ISO 273 clearances)."""
    F = F or fs.load()
    out = {}
    tap = F.screwMaker.GetInnerThread(size)
    if tap:
        out["tapHole"] = _clean(tap)
    try:
        out["nominal"] = _clean(F.FastenerBase.DiaStr2Num(size))
    except Exception:  # noqa: BLE001
        pass
    return out


def types(query=None, standard=None, kind=None, ftype=None, size=None, limit=40):
    """Fasteners' types, or one type's sizes, or one size's lengths and
    holes — read from its own tables (ScrewMaker)."""
    F = fs.load()
    if ftype:
        k = _check_type(F, ftype)
        row = _row(F, k)
        sizes = [str(x) for x in F.screwMaker.GetAllDiams(k)]
        if not size:
            return {**row, "sizes": sizes, "hasLength": "Length" in _params(F, k) or "lengthArbitrary" in _params(F, k), "source": SOURCE}
        if size not in sizes:
            raise Missing(f"size {size!r}: {k} comes in {', '.join(sizes)}.", "not_found")
        out = {**row, "size": size, "source": SOURCE}
        lens = _lengths(F, k, size)
        if lens is not None:
            out["lengths"] = lens
        elif "lengthArbitrary" in _params(F, k):
            out["length"] = {"any": True, "default": _clean(F.screwMaker.GetTableProperty(k, size, "Length", 20.0))}
        out["hole"] = hole_sizes(size, F)
        if k == "IUTHeatInsert":
            ins = insert_figures(size)
            if ins:
                out["insert"] = ins
        return out
    rows = [_row(F, k) for k in sorted(_table(F))]
    if standard:
        rows = [r for r in rows if r["standard"].lower() == str(standard).lower()]
    if kind:
        kl = str(kind).lower().rstrip("s")
        rows = [r for r in rows if kl in r["kind"].lower() or kl in r["group"].lower()]
    if query:
        words = [w for w in re.split(r"\s+", str(query).lower()) if w]
        rows = [r for r in rows if all(w in f"{r['type']} {r['what']} {r['group']} {r['kind']}".lower() for w in words)]
    out = {"count": len(rows), "types": [{k: r[k] for k in ("type", "kind", "what")} for r in rows[:limit]], "source": SOURCE}
    if len(rows) > limit:
        out["more"] = f"{len(rows) - limit} more: narrow with query, standard or kind."
    if not rows:
        out["kinds"] = sorted({_row(F, k)["kind"] for k in _table(F)})
        out["standards"] = sorted({_row(F, k)["standard"] for k in _table(F)})
    return out


# ---- objects --------------------------------------------------------------------------

def _obj(doc, ref):
    if not isinstance(ref, str):
        return ref
    for o in doc.Objects:
        if o.Name == ref or o.Label == ref:
            return o
    for o in doc.Objects:
        if o.Label.lower() == ref.lower():
            return o
    raise Missing(f"{ref!r}: no such object.", "not_found")


def element(doc, ref):
    """(object, "EdgeN") from "Plate.Edge7", "Plate:Edge7" or {object, element}."""
    if isinstance(ref, dict):
        o, sub = ref.get("object"), ref.get("element") or ref.get("edge")
    else:
        m = re.match(r"^(.*?)[.:]((?:Edge|Face)\d+)$", str(ref).strip())
        if not m:
            raise Missing(f"edges: {ref!r} — an edge as \"Object.Edge7\" (a circular edge of a hole or shaft).", "invalid_input")
        o, sub = m.group(1), m.group(2)
    o = _obj(doc, o)
    try:
        sh = o.getSubObject(sub)
    except Exception:  # noqa: BLE001
        sh = None
    curve = getattr(sh, "Curve", None)
    if sh is None or curve is None or not hasattr(curve, "Radius"):
        raise Missing(f"{o.Label}.{sub}: not a circular edge — Fasteners attaches to a hole's or shaft's round edge.", "invalid_input")
    return o, sub


def _family(o):
    p = getattr(o, "Proxy", None)
    fam = getattr(p, "familyType", None)
    if fam:
        return str(fam)
    return re.sub(r"\d+$", "", getattr(o, "Name", "") or "") or "Fastener"


def _length_of(o):
    if not hasattr(o, "Length"):
        return None
    v = o.Length
    if isinstance(v, str):
        if v == "Custom" and hasattr(o, "LengthCustom"):
            return _clean(_num(o.LengthCustom))
        return v
    n = _num(v)
    return _clean(n) if n is not None else None


def bom_text(o):
    """The line a fastener has in a bill of materials, as Fasteners' own
    BOM words it: type, kind, size (x length)."""
    t = getattr(o, "Type", "") or ""
    d = getattr(o, "Diameter", "") or ""
    if d == "Custom" and hasattr(o, "DiameterCustom"):
        d = str(_clean(_num(o.DiameterCustom)))
    ln = _length_of(o)
    fam = {"ThreadedRod": "Threaded Rod", "HeatSet": "Heat Set Insert", "Insert": "Insert"}.get(_family(o), _family(o))
    return f"{t} {fam} {d}" + (f"x{ln}" if ln not in (None, "") else "")


def describe(o):
    out = {"object": o.Name, "label": o.Label, "type": getattr(o, "Type", None), "kind": _family(o), "size": getattr(o, "Diameter", None)}
    ln = _length_of(o)
    if ln is not None:
        out["length"] = ln
    for k, n in (("MatchOuter", "matchOuter"), ("Invert", "invert")):
        if hasattr(o, k):
            out[n] = bool(getattr(o, k))
    if hasattr(o, "Thread"):
        out["thread"] = "real" if o.Thread else "simple"
    off = _num(getattr(o, "Offset", 0)) or 0.0
    if off:
        out["offset"] = _clean(off)
    try:
        b = o.BaseObject
        if b and b[0] is not None:
            out["attachedTo"] = f"{b[0].Label}.{b[1][0]}" if b[1] else b[0].Label
    except Exception:  # noqa: BLE001
        pass
    try:
        p = o.Placement.Base
        out["at"] = [_clean(p.x), _clean(p.y), _clean(p.z)]
    except Exception:  # noqa: BLE001
        pass
    out["bom"] = bom_text(o)
    return out


def fasteners_in(doc):
    return [o for o in getattr(doc, "Objects", []) if detect.is_fastener(o)]


def _set_length(F, o, length):
    if length is None or not hasattr(o, "Length"):
        return None
    if isinstance(o.Length, str):  # fixed lengths: the nearest standard one (FSChangeParams' way)
        _d, ln, _w = F.screwMaker.FindClosest(o.Type, o.Diameter, str(length))
        o.Length = ln
        return ln
    o.Length = float(length)
    return float(length)


def _view(F, o):
    """Fasteners' own view provider (its tree icon), when there is a window."""
    try:
        import FreeCAD

        if FreeCAD.GuiUp and getattr(o, "ViewObject", None) is not None and hasattr(F.FastenersCmd, "FSViewProviderTree"):
            F.FastenersCmd.FSViewProviderTree(o.ViewObject)
    except Exception:  # noqa: BLE001
        pass


def add(doc, ftype, size=None, length=None, thread="simple", edges=(), at=None, match="outer", invert=False, offset=0.0, container=None):
    """One fastener per circular edge (attached, as Fasteners' buttons do
    with an edge selected), or one loose fastener (at [x, y, z])."""
    F = fs.load()
    k = _check_type(F, ftype)
    if match not in ("inner", "outer"):
        raise Missing("match: inner (a tap hole: the screw's thread fits it) or outer (a pass hole: the screw goes through).", "invalid_input")
    if thread not in ("simple", "real", True, False):
        raise Missing("thread: simple (fast, a plain cylinder) or real (a modelled thread).", "invalid_input")
    sizes = [str(x) for x in F.screwMaker.GetAllDiams(k)]
    if size is not None and size not in sizes and size != "Auto":
        raise Missing(f"size {size!r}: {k} comes in {', '.join(sizes)}.", "not_found")
    targets = [element(doc, e) for e in (edges or [])] or [None]
    family = F.screwMaker.GetTypeName(k)
    made = []
    for tgt in targets:
        o = doc.addObject("Part::FeaturePython", family)
        if container is not None:
            try:
                container.addObject(o)
            except Exception:  # noqa: BLE001
                pass
        F.FastenersCmd.FSScrewObject(o, k, (tgt[0], [tgt[1]]) if tgt else None)
        _view(F, o)
        if hasattr(o, "MatchOuter"):
            o.MatchOuter = match == "outer"
        o.Diameter = size if size else ("Auto" if tgt else o.Diameter)
        if hasattr(o, "Thread"):
            o.Thread = thread in ("real", True)
        o.Invert = bool(invert)
        o.Offset = float(offset or 0.0)
        doc.recompute()
        _set_length(F, o, length)
        if tgt is None and at is not None:
            import FreeCAD

            pl = o.Placement
            pl.Base = FreeCAD.Vector(*[float(v) for v in at])
            o.Placement = pl
        made.append(o)
    doc.recompute()
    return made


def change(doc, refs, ftype=None, size=None, length=None, thread=None, invert=None, offset=None, match=None, edge=None):
    """Change fasteners as Fasteners' Change Parameters (and Flip, Move)
    does: type, size ("Auto": matched to its hole again), length (the
    nearest standard one), thread, invert, offset, match, edge (moved)."""
    F = fs.load()
    objs = [_obj(doc, r) for r in refs]
    bad = [o.Label for o in objs if not detect.is_fastener(o)]
    if bad:
        raise Missing(f"{bad[0]}: not a Fasteners object — fastener_list lists them.", "invalid_input")
    tgt = element(doc, edge) if edge else None
    for o in objs:
        if ftype:
            k = _check_type(F, ftype)
            ok = list(o.getEnumerationsOfProperty("Type")) if hasattr(o, "getEnumerationsOfProperty") else [k]
            if k not in ok:
                raise Missing(f"type {k}: {o.Label} can become {', '.join(ok)} (the types with its properties); add a new one for another kind.", "invalid_input")
            o.Type = k
        if match is not None and hasattr(o, "MatchOuter"):
            o.MatchOuter = match == "outer"
        if size:
            o.Diameter = size
        if thread is not None and hasattr(o, "Thread"):
            o.Thread = thread in ("real", True)
        if invert is not None:
            o.Invert = bool(invert)
        if offset is not None:
            o.Offset = float(offset)
        if tgt is not None:
            o.BaseObject = (tgt[0], [tgt[1]])
    doc.recompute()
    if length is not None:
        for o in objs:
            _set_length(F, o, length)
        doc.recompute()
    return objs


def repeats(o):
    """How many of it the document holds (links, arrays, clones counted),
    Fasteners' own count where it loads; else 1 when shown."""
    F = fs.loaded()
    if F is not None:
        try:
            return int(F.FastenerBase.GetTotalObjectRepeats(o))
        except Exception:  # noqa: BLE001
            pass
    return 1 if getattr(o, "Visibility", True) else 0


def listing(doc):
    objs = fasteners_in(doc)
    items = [describe(o) for o in objs]
    bom = {}
    for o in objs:
        n = repeats(o)
        if n:
            bom[bom_text(o)] = bom.get(bom_text(o), 0) + n
    return {"fasteners": items, "bom": [{"item": k, "qty": v} for k, v in sorted(bom.items())], "source": SOURCE}


def bom_sheet(doc):
    """Fasteners' own Generate BOM (its spreadsheet) in a window; without one
    the same sheet written here (Type, Qty)."""
    before = {o.Name for o in doc.Objects}
    try:
        import FreeCAD
        import FreeCADGui

        if FreeCAD.GuiUp and "Fasteners_BOM" in FreeCADGui.listCommands():
            FreeCAD.setActiveDocument(doc.Name)
            FreeCADGui.runCommand("Fasteners_BOM")
            new = [o for o in doc.Objects if o.Name not in before and o.TypeId == "Spreadsheet::Sheet"]
            if new:
                return {"sheet": new[-1].Label, "by": "Fasteners' Generate BOM"}
    except Exception:  # noqa: BLE001 — headless: written below
        pass
    rows = listing(doc)["bom"]
    sh = doc.addObject("Spreadsheet::Sheet", "Fasteners_BOM")
    sh.set("A1", "Type")
    sh.set("B1", "Qty")
    for i, r in enumerate(rows, start=2):
        sh.set(f"A{i}", r["item"])
        sh.set(f"B{i}", str(r["qty"]))
    doc.recompute()
    return {"sheet": sh.Label, "by": "Workshop (Fasteners' BOM layout; its command needs the window)"}


def restore(doc):
    """Fasteners' Restore fasteners: objects saved where Fasteners was not
    loaded get its proxy back."""
    F = fs.load()
    done = []
    for o in doc.Objects:
        if hasattr(o, "Invert") and hasattr(o, "Type") and getattr(o, "Proxy", None) is None:
            F.FastenersCmd.FSScrewObject(o, o.Type, None)
            _view(F, o)
            done.append(o.Label)
    if done:
        doc.recompute()
    return done


# ---- 3D-print thread settings ----------------------------------------------------------

def _param():
    import FreeCAD

    return FreeCAD.ParamGet(PARAMS)


def print_settings(mode=None, nut=None, screw=None):
    """Fasteners' 3D Print Settings: thread generation standard or 3dprint,
    and the scale a printed thread's diameter takes (d x A + B) for nuts
    and for screws. Given values are set and threaded fasteners redone."""
    g = _param()
    changed = False
    if mode is not None:
        if mode not in ("standard", "3dprint"):
            raise Missing("mode: standard or 3dprint.", "invalid_input")
        g.SetInt(PRINT_KEYS["mode"], 1 if mode == "3dprint" else 0)
        changed = True
    for which, val in (("nut", nut), ("screw", screw)):
        if val is None:
            continue
        if not (isinstance(val, (list, tuple)) and len(val) == 2 and all(isinstance(x, (int, float)) for x in val)):
            raise Missing(f"{which}: [A, B] — a printed thread's diameter is d x A + B.", "invalid_input")
        g.SetFloat(PRINT_KEYS[which + "A"], float(val[0]))
        g.SetFloat(PRINT_KEYS[which + "B"], float(val[1]))
        changed = True
    redone = []
    if changed:
        F = fs.load()
        if F.screwMaker.updateFastenerParameters():
            import FreeCAD

            for d in FreeCAD.listDocuments().values():
                for o in fasteners_in(d):
                    if getattr(o, "Thread", False):
                        o.recompute()
                        redone.append(o.Label)
    out = read_print_settings()
    if redone:
        out["redone"] = redone
    return out


def read_print_settings():
    g = _param()
    out = {"mode": "3dprint" if g.GetInt(PRINT_KEYS["mode"], 0) == 1 else "standard"}
    for which in ("nut", "screw"):
        out[which] = [_clean(g.GetFloat(PRINT_KEYS[which + "A"], PRINT_DEFAULTS[which + "A"])),
                      _clean(g.GetFloat(PRINT_KEYS[which + "B"], PRINT_DEFAULTS[which + "B"]))]
    out["formula"] = "printed thread diameter = d x A + B (nut: inside threads, screw: outside); used when mode is 3dprint"
    out["source"] = SOURCE + " 3D Print Settings"
    return out


def thread_compensation(d):
    """(diametral clearance for an inside thread of major d, source) from
    Fasteners' 3D-print setting when it is installed and in 3dprint mode;
    else None. Reads its settings only (no Fasteners module loaded)."""
    if not detect.present():
        return None
    try:
        s = read_print_settings()
    except Exception:  # noqa: BLE001
        return None
    if s["mode"] != "3dprint":
        return None
    a, b = s["nut"]
    c = d * a + b - d
    return (round(c, 3), f"Fasteners Workbench's 3D-print setting (nut threads d x {a} + {b})") if c > 0 else None


# ---- heat-set inserts ------------------------------------------------------------------

_inserts = None


def insert_figures(size):
    """Fasteners' IUT heat-set insert row for a size, mm: hole (its D, the
    insert's hole diameter), depth (its length), outer (knurl diameter);
    None when Fasteners is not installed or has no row. Read with its own
    reader (FSutils.csv2dict) from its own table; nothing heavier loaded."""
    global _inserts
    info = detect.find()
    if info is None:
        return None
    if _inserts is None:
        try:
            import importlib
            import os
            import sys

            if info["path"] not in sys.path:
                sys.path.append(info["path"])
            FSutils = importlib.import_module("FSutils")
            t = FSutils.csv2dict(os.path.join(FSutils.fsdatapath, "HeatInserts.csv"), "HeatInserts", fieldsnamed=True)
            titles = list(t["titles"].get("IUTHeatInsertdef") or ())
            rows = t.get("IUTHeatInsertdef") or {}
            _inserts = {k: dict(zip(titles, v)) for k, v in rows.items()}
        except Exception:  # noqa: BLE001
            _inserts = {}
    r = _inserts.get(str(size))
    if not r or not all(k in r for k in ("D", "Length", "ExtDia")):
        return None
    return {"hole": _clean(r["D"]), "depth": _clean(r["Length"]), "outer": _clean(r["ExtDia"]), "insert": f"IUT {size}",
            "source": "Fasteners Workbench (its IUT heat-set insert table)"}


# ---- the matching screw in a Hole for Hardware -------------------------------------------

def _vec(d):
    import FreeCAD

    table = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
    v = FreeCAD.Vector(*(table[d] if isinstance(d, str) else d))
    v.normalize()
    return v


def _circle_at(shape, p, d, biggest=False):
    """The circular edge centred on the hole's axis nearest p (within 0.1 mm
    of it), axis along d: (index, edge)."""
    best = None
    for i, e in enumerate(shape.Edges, start=1):
        c = getattr(e, "Curve", None)
        if c is None or not hasattr(c, "Radius") or not hasattr(c, "Center"):
            continue
        ax = c.Axis
        if ax.cross(d).Length > 1e-3 or (c.Center - p).Length > 0.1:
            continue
        key = c.Radius if not biggest else -c.Radius
        if best is None or key < best[0]:
            best = (key, i, e)
    return (best[1], best[2]) if best else (None, None)


def hole_screw(doc, hole_args, hole_out, spec):
    """After Hole for Hardware: the matching screw from Fasteners, put in the
    hole. spec: true, or {type, length, thread}. Length from the hole (the
    plate it passes, less a counterbore; an insert's depth) unless given,
    the nearest length Fasteners has; matched outer for pass holes, inner
    for inserts. Answers {screw: …} or {screwNote: why not}."""
    spec = {} if spec is True else dict(spec or {})
    kind, size = hole_args.get("kind"), hole_args.get("size", "M3")
    if kind not in HOLE_SCREW:
        return {"screwNote": f"No screw for a {kind} hole."}
    at = hole_args.get("at")
    if not (isinstance(at, (list, tuple)) and len(at) == 3):
        return {"screwNote": "The screw goes in with at: one hole at a known point (not a sketch's circles)."}
    F = fs.load()
    import FreeCAD

    ftype = _check_type(F, spec.get("type") or HOLE_SCREW[kind])
    if str(size) not in [str(x) for x in F.screwMaker.GetAllDiams(ftype)]:
        return {"screwNote": f"{ftype} has no {size}: give screw.type one that has (fastener_types {{ type }} lists sizes)."}
    body = _obj(doc, hole_out.get("body"))
    shape = body.Shape
    d = _vec(hole_args.get("dir", "-z"))
    p = FreeCAD.Vector(*[float(v) for v in at])
    sizes = hole_out.get("sizes") or {}
    through = hole_out.get("through")
    depth = hole_args.get("depth", "through")
    plate = through if depth == "through" else _num(depth)
    biggest, inward = False, True
    if kind == "counterbore":
        p = p + d * float(sizes.get("cutDepth") or sizes.get("counterboreDepth") or 0)
        need = (plate or 0) - float(sizes.get("cutDepth") or sizes.get("counterboreDepth") or 0)
    elif kind == "countersink":
        biggest, need = True, plate
    elif kind == "nut_trap":
        if not plate:
            return {"screwNote": "A nut trap's screw comes from the far side: give a through hole."}
        p, inward, need = p + d * plate, False, plate
    elif kind == "insert":
        need = float(sizes.get("depth") or 0)
    else:
        need = plate
    idx, edge = _circle_at(shape, p, d, biggest)
    if idx is None:
        return {"screwNote": f"No round edge of the hole found at {[round(v, 2) for v in (p.x, p.y, p.z)]}: fastener_add {{ edges }} puts one on an edge you pick."}
    length = spec.get("length") or (need if need and need > 0 else None)
    container = None
    try:
        parent = body.getParentGeoFeatureGroup()
        container = parent if parent is not None and parent.TypeId == "App::Part" else None
    except Exception:  # noqa: BLE001
        pass
    o = add(doc, ftype, str(size), length, spec.get("thread", "simple"), edges=[f"{body.Name}.Edge{idx}"], match=HOLE_MATCH[kind], container=container)[0]
    # Shank into the material (away from the far side for a nut trap):
    # Fasteners puts the head on the edge's axis side, the shank opposite.
    want = d if inward else d * -1
    if edge.Curve.Axis.dot(want) > 0:
        o.Invert = True
        doc.recompute()
    out = describe(o)
    out["match"] = HOLE_MATCH[kind]
    if need:
        out["lengthNeeded"] = _clean(need)
    if kind == "insert":
        out["note"] = "Length is the insert's depth: add the thickness of what it clamps (fastener_set { length })."
    elif kind == "nut_trap":
        out["note"] = "From the far side, into the nut in the trap."
    out["credit"] = CREDIT
    return {"screw": out}


def mass_g(o, density=7.85):
    """A fastener's mass, g: its own shape in steel unless its material says
    otherwise (Fasteners keeps no material)."""
    try:
        return round(o.Shape.Volume * density / 1000.0, 2)
    except Exception:  # noqa: BLE001
        return None

