# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's Python API: what a macro, a command or an agent calls alike.
Plain values in, plain values out (mm); a refusal is workshop_make.refusal.Refused with
what to do instead. Nothing here imports Agent Link.

    from workshop_make import api
    api.thread("M6")                    # sizes from the standards
    api.nearest_threads(4.98, inside=True)
    api.calibration(doc, "Bracket")     # the printer fit the sizes take
    api.fit_size(8.0, "hole", "slide", doc=doc)
    api.hole(doc, "Bracket", "counterbore", "M3", at=[10, 10, 5])
"""

from workshop_make.refusal import Refused
from workshop_make import fits
from workshop_make import geo
from workshop_make import records

from . import embeds, pdhole, threads


FIT_KINDS = tuple(fits.FITS)
HOLE_KINDS = fits.KINDS
SIZES = tuple(fits.M)


# ---- the printer's fit --------------------------------------------------------------------

def calibration(doc, body=None):
    """(calibration, where it came from): the body's print setup's fit, else
    the document's (fit calibrate), else the typical printer's."""
    s = records.setup_of(doc, body, "print") if body else None
    c = (s or {}).get("fit") or records.read(doc, "fit", None)
    return (c, "calibrated") if c else (dict(fits.DEFAULT_CAL), NO_CALIBRATION)


# What printerFit says with no calibration kept: a clause that reads in a
# sentence ("Printer calibration: none, so …").
NO_CALIBRATION = "none, so holes are assumed to print 0.2 mm small"


def calibration_said(said):
    """printerFit as a person reads it after "Printer calibration: "."""
    return "the one kept with this document" if said == "calibrated" else str(said)


def calibrate(doc, hole=0.2, shaft=0.0):
    """Keep how much this printer prints a hole small and a peg big
    (diametral mm, -1 to 1); every size from now on takes it."""
    c = {"hole": float(hole), "shaft": float(shaft)}
    if not (-1 <= c["hole"] <= 1 and -1 <= c["shaft"] <= 1):
        raise Refused("hole and shaft: how much a printed hole comes out small and a peg big, diametral mm, -1 to 1.")
    records.write(doc, "fit", c)
    return c


def fit_size(nominal, of="hole", kind=None, doc=None, body=None, cal=None):
    """The size to model a hole or a peg at, for one fit or all of them."""
    if not isinstance(nominal, (int, float)):
        raise Refused("nominal: the size to fit, mm — the bought part's, or the mating part's.")
    if of not in ("hole", "shaft"):
        raise Refused("of: hole or shaft.")
    if kind is not None and kind not in fits.FITS:
        raise Refused(f"kind: one of {', '.join(fits.FITS)}.")
    said = "given"
    if cal is None:
        cal, said = calibration(doc, body) if doc is not None else (dict(fits.DEFAULT_CAL), NO_CALIBRATION)
    out = {k: round(fits.size_fit(k, nominal, of, cal), 3) for k in ([kind] if kind else fits.FITS)}
    return {"of": of, "nominal": nominal, "model": out, "printerFit": said}


def stack(items, target=None):
    """A tolerance stack: worst case and root-sum-square; with target [lo, hi]
    whether each stays inside."""
    if not items or not all(isinstance(i.get("nominal"), (int, float)) for i in items):
        raise Refused("items: [{ name, nominal (mm, signed), tol (± mm) }], one or more.")
    out = fits.stack(items)
    if target is not None:
        lo, hi = target
        out["worstCaseOk"] = lo <= out["worstCase"][0] and out["worstCase"][1] <= hi
        out["rssOk"] = lo <= out["rss"][0] and out["rss"][1] <= hi
    return out


def _through(shape, at, d, frame=None):
    """How much material a through hole at `at` going `d` passes, mm (the
    line's length inside the solid), or None when it cannot be read. at and
    d are global; frame: the placement the shape's coordinates are in (a
    Body inside an App::Part: the Part's)."""
    try:
        import FreeCAD
        import Part

        p = FreeCAD.Vector(*at)
        v = FreeCAD.Vector(d)
        if frame is not None:
            inv = frame.inverse()
            p, v = inv.multVec(p), inv.Rotation.multVec(v)
        v.normalize()
        reach = shape.BoundBox.DiagonalLength * 2
        inside = shape.common(Part.makeLine(p - v * 1e-3, p + v * reach))
        n = round(sum(e.Length for e in inside.Edges), 2)
        return n if n > 0 else None
    except Exception:  # noqa: BLE001
        return None


def _named(doc, name):
    """An object by its name or its label (live 105: a lesson bound the
    sketch by its name, Sketch001, and the label was not that)."""
    o = doc.getObject(name) if hasattr(doc, "getObject") else None
    if o is None:
        got = doc.getObjectsByLabel(name)
        o = got[0] if got else None
    return o


def hole(doc, body, kind, size="M3", at=None, direction="-z", depth="through", fit="normal", face=None, sketch=None):
    """A hole for hardware: clearance, counterbore, countersink, nut_trap,
    insert or magnet, with the printer's allowance added.

    In a PartDesign Body it is FreeCAD's own PartDesign::Hole (its ISO 273
    clearance, its counterbore and countersink for the screw standards it
    knows), editable in its task panel; Make adds only what the Hole lacks:
    the printer allowance, a nut trap (a Pocket from a hexagon), insert and
    magnet pockets. face: the entry face ("Face6") when the person picked
    one; sketch: a sketch whose circles are the holes. In a plain Part solid
    (no Body) the hole is cut as a shape, and the answer says so."""
    o = _named(doc, body) if isinstance(body, str) else body
    if o is None or isinstance(o, str):
        raise Refused(f"body: no body called {body}.", "not_found")
    if kind not in fits.KINDS:
        raise Refused(f"kind: one of {', '.join(fits.KINDS)}.")
    sk = None
    if sketch:
        sk = _named(doc, sketch) if isinstance(sketch, str) else sketch
        if sk is None:
            raise Refused(f"sketch: no sketch called {sketch}.", "not_found")
    if sk is None and not (isinstance(at, (list, tuple)) and len(at) == 3):
        raise Refused("at: [x, y, z], mm — where the hole enters the part, on its face.")
    cal, said = calibration(doc, o.Label)
    pd = pdhole.body_of(o)
    if pd is not None:
        try:
            dvec = fits._dir(direction)
        except ValueError as e:
            raise Refused(str(e))
        before = pd.Shape.Volume if not pd.Shape.isNull() else 0.0
        through = _through(pd.Shape, at, dvec, frame=pdhole.shape_frame(pd)) if depth == "through" and at else None
        try:
            names, sizes = pdhole.make(doc, pd, kind, size, list(at) if at else None, dvec, depth, fit, cal, face=face, sketch=sk)
        except pdhole.Failed as e:
            raise Refused(str(e), "failed")
        except Refused:
            raise
        except Exception as e:  # noqa: BLE001 — FreeCAD's own words, in a sentence
            raise Refused(f"FreeCAD's Hole could not be made at {list(at) if at else 'the sketch'}: {pdhole.sentence(e)}. Nothing was kept.", "failed")
        pdhole.settle(doc, [pd])
        s = geo.soundness(pd.Shape)
        return {"body": pd.Label, "kind": kind, "size": size, "sizes": sizes, "printerFit": said, "allowance": float(cal.get("hole", 0.0)),
                "depth": depth, **({"through": through} if through else {}), "removed": round(before - pd.Shape.Volume, 2),
                "route": "PartDesign Hole", "features": names,
                **pdhole.head_side(kind, list(at) if at and sk is None else None, dvec),
                # sizes.allowanceOn says how the allowance is kept: named here, not said twice.
                "note": ("FreeCAD's own Hole (double-click it to edit). " + (f"Printer allowance {float(cal.get('hole', 0.0)):g} mm added: sizes.allowanceOn says where and how it is kept."
                                                                             if sizes.get("allowanceOn") else
                         "No printer allowance: FreeCAD's sizes as they are, kept by its size and fit.")),
                "sound": s["ok"], **({"problems": s["problems"]} if not s["ok"] else {})}
    if sk is not None:
        raise Refused("sketch: a sketch's circles make holes in a PartDesign Body only; give at for a plain Part solid.")
    why = geo.rebuilt(o, "a hole")
    if why:
        # A Part::Box, a boolean, an extrusion: the hole was cut, answered,
        # and gone at the same call's recompute.
        raise Refused(why + " Or pd_clone it into a PartDesign Body, where the hole is FreeCAD's own editable Hole.", "invalid_state")
    bb = o.Shape.BoundBox
    d = bb.DiagonalLength if depth == "through" else float(depth)
    try:
        tool, sizes = fits.hole_tool(kind, size, list(at), direction, d, fit, cal)
    except ValueError as e:
        raise Refused(str(e))
    if depth == "through" and "clearance" in sizes:
        # The cutter is as long as the body's diagonal (116.658 on a 100 x
        # 60 x 3 plate, found live as sizes.depth): the hole's depth is
        # "through", as the PartDesign route says; `through` is the material passed.
        sizes["depth"] = "through"
    before = o.Shape.Volume
    through = _through(o.Shape, at, fits._dir(direction)) if depth == "through" else None
    cut = geo.clean(o.Shape.cut(tool))
    removed = before - cut.Volume
    if removed < 1e-3:
        raise Refused(f"The hole cut nothing at {list(at)} going {direction}: put at on the part's face, dir into the material.", "failed")
    o.Shape = cut
    doc.recompute()
    s = geo.soundness(cut)
    return {"body": o.Label, "kind": kind, "size": size, "sizes": sizes, "printerFit": said, "allowance": float(cal.get("hole", 0.0)),
            "depth": depth, **({"through": through} if through else {}), "removed": round(removed, 2),
            "route": "Part solid", **pdhole.head_side(kind, list(at), fits._dir(direction)),
            "note": "Cut as a shape: the part is a plain Part solid, not a PartDesign Body, so FreeCAD's Hole cannot go on it (put it in a Body for an editable Hole).",
            "sound": s["ok"], **({"problems": s["problems"]} if not s["ok"] else {})}


# ---- threads ------------------------------------------------------------------------------

def thread(size):
    """One thread by name (M6, M10x1.25, 1/4-20, #10-32), or None."""
    return threads.lookup(size)


def thread_table(series=None):
    if series not in threads.SERIES + ("all", None):
        raise Refused(f"series: {', '.join(threads.SERIES)} or all.")
    return threads.table(series)


def nearest_threads(diameter, inside, count=3):
    """The standard sizes nearest a measured diameter, each with how far off."""
    return threads.nearest(float(diameter), bool(inside), count)


# ---- parts encased mid-print --------------------------------------------------------------

def pauses(doc, body, extra=()):
    """The pauses a body's print needs from its encased-part records: one per
    layer (two on one layer joined), on its print setup's layer grid."""
    setup = records.setup_of(doc, body, "print")
    if not setup:
        raise Refused(f"{body} is in no print setup: the pauses are on its layer grid.", "invalid_state")
    first, lh = embeds.grid(setup)
    recs = [{"id": r["id"], "layer": r["layer"], "note": r["note"]} for r in records.read(doc, "embeds", {}).get(body, [])]
    return embeds.pauses(recs + list(extra), first, lh)


# ---- how each part is made (setups), what it must meet (spec) -----------------------------

LINE = 0.42  # mm, one extrusion line of a 0.4 mm nozzle
NDFEB = 7.5  # g/cm³, the magnets
MAGNET_T_MM = 2.0  # a 6 x 2 mm magnet, as Workshop Parts' Gridfinity bins take


def setup_types():
    return {k: v["settings"] for k, v in records.TYPES.items()}


def _settings(kind, given):
    from . import printability

    known = records.TYPES[kind]["settings"]
    bad = [k for k in given if k not in known]
    if bad:
        raise Refused(f"settings.{bad[0]}: not a {kind} setting — they are: {', '.join(known)}.")
    out = dict(given)
    if "nozzle" in out:
        out["nozzle"] = str(float(out["nozzle"]))
    if "printer" in out and out["printer"] not in printability.PRINTERS:
        raise Refused(f"settings.printer: one of {', '.join(printability.PRINTERS)}.")
    if out.get("up", "+z") != "+z":
        raise Refused("settings.up: +z only in this build — turn the part to stand it another way.")
    return out


def setup_add(doc, kind, bodies, settings=None, name=None):
    """A setup of one process (print, cut, mill …) for bodies (labels)."""
    if kind not in records.TYPES:
        raise Refused(f"type: one of {', '.join(records.TYPES)}.")
    all_ = records.setups(doc)
    for b in bodies:
        other = records.setup_of(doc, b, kind)
        if other:
            raise Refused(f"{b} is in {other['name']} ({other['id']}) already: setup set {{ id: \"{other['id']}\", remove: [\"{b}\"] }} first.")
    st = _settings(kind, settings or {})
    n = 1 + max([int(x["id"][1:]) for x in all_] or [0])
    same = sum(1 for x in all_ if x["type"] == kind)
    s = {"id": f"S{n}", "type": kind, "name": name or records.TYPES[kind]["label"] + (f" {same + 1}" if same else ""), "bodies": list(bodies), **st}
    records.save_setups(doc, all_ + [s])
    return s


def setup_find(doc, ref):
    s = next((x for x in records.setups(doc) if x["id"] == ref or x["name"] == ref), None)
    if s is None:
        raise Refused(f"setup {ref!r}: not here — setup list gives them.", "not_found")
    return s


def setup_set(doc, ref, bodies=None, add=(), remove=(), settings=None, name=None):
    all_ = records.setups(doc)
    s = next((x for x in all_ if x["id"] == ref or x["name"] == ref), None)
    if s is None:
        raise Refused(f"setup {ref!r}: not here — setup list gives them.", "not_found")
    if bodies is not None:
        s["bodies"] = list(bodies)
    for b in add:
        if b not in s["bodies"]:
            s["bodies"].append(b)
    s["bodies"] = [x for x in s["bodies"] if x not in set(remove)]
    for k, v in (settings or {}).items():
        if v is None:
            s.pop(k, None)
        else:
            s.update(_settings(s["type"], {k: v}))
    if name:
        s["name"] = name
    records.save_setups(doc, all_)
    return s


def setup_remove(doc, ref):
    all_ = records.setups(doc)
    s = setup_find(doc, ref)
    records.save_setups(doc, [x for x in all_ if x["id"] != s["id"]])
    return s["id"]


SPEC_KEYS = ("minWall", "massMin", "massMax", "minSafety", "minClearance")


def spec_set(doc, spec=None, clear=False):
    """The document's spec: limits every part must meet (mm, g)."""
    out = {} if clear else dict(records.spec(doc))
    for k, v in (spec or {}).items():
        if v is None:
            out.pop(k, None)
        elif k in SPEC_KEYS and isinstance(v, (int, float)):
            out[k] = v
        else:
            raise Refused(f"spec.{k}: not a limit, or not a number — the limits are minWall (mm), massMin and massMax (g), minSafety (a safety factor) "
                          f"and minClearance (mm); null drops one.")
    records.write(doc, "spec", out)
    return out


def material_set(doc, bodies, material):
    """A printing filament for bodies (labels)."""
    from workshop_make import materials

    m = str(material).lower()
    if m not in materials.DENSITY:
        raise Refused(f"material: one of {', '.join(materials.DENSITY)}.")
    mats = records.materials(doc)
    for b in bodies:
        mats[b] = m
    records.write(doc, "materials", mats)
    return mats


def material_clear(doc, bodies):
    """Bodies (labels) back to no material of their own (PLA assumed)."""
    mats = records.materials(doc)
    for b in bodies:
        mats.pop(b, None)
    records.write(doc, "materials", mats)
    return mats


def freecad_material(doc, bodies, material=None):
    """FreeCAD's own material (ShapeMaterial) on bodies (labels) to match
    Make's: the FreeCAD card for the filament material, or FreeCAD's
    default when material is None (forgotten). So FreeCAD's Inspect
    Material names what Make weighs the part with. {label: {"card"} or
    {"note"}}."""
    from . import fcmaterials, materials

    out = {}
    for b in bodies:
        objs = doc.getObjectsByLabel(b) if hasattr(doc, "getObjectsByLabel") else []
        if not objs:
            continue
        if material is None:
            out[b] = {"card": "FreeCAD's default"} if fcmaterials.clear(objs[0]) else {"note": "FreeCAD's material left as it was"}
            continue
        key = str(material).lower()
        name, why = fcmaterials.give(objs[0], key, (materials.FILAMENTS.get(key) or {}).get("name"))
        out[b] = {"card": name} if name else {"note": why}
    return out


def rules_of(doc, body):
    """(rules, print setup) for a body: its print setup's nozzle and printer."""
    from . import printability

    s = records.setup_of(doc, body, "print") or {}
    return printability.rules_for(s.get("nozzle", "0.4"), s.get("printer")), s


def dfm_verdict(findings):
    """dfm_check's verdict in a few words, from the findings not waived:
    "not printable: 1 problem, 2 warnings", "printable, 2 warnings" or
    "printable" (results.dfm says the same to the person)."""
    open_ = [f for f in findings or [] if not f.get("waived")]
    errors = sum(1 for f in open_ if f.get("severity") == "error")
    warns = sum(1 for f in open_ if f.get("severity") == "warning")

    def n(k, word):
        return f"{k} {word}{'' if k == 1 else 's'}"
    if errors:
        return "not printable: " + n(errors, "problem") + (f", {n(warns, 'warning')}" if warns else "")
    return "printable" + (f", {n(warns, 'warning')}" if warns else "")


def slice_verdict(read):
    """slice's and slice_with's verdict in a few words, from the G-code read
    back: "12m 3s, 3.21 g", "12m 3s", "3.21 g", else "G-code written" (the window's
    words use it: a sliced read kept an earlier call's caption, round 4
    2008, 2010)."""
    r = read if isinstance(read, dict) else {}
    bits = []
    if r.get("time"):
        bits.append(str(r["time"]))
    g = r.get("filamentG")
    if isinstance(g, (int, float)) and not isinstance(g, bool):
        bits.append(f"{g:.6g} g")
    return ", ".join(bits) or "G-code written"


def frame_verdict(members):
    """fea_frame's verdict in a few words: the least safety factor and its
    member ("least safety 2.4, Rafter"; "under yield: 0.8, Post" below 1),
    or the largest von Mises stress where no member's material gives a yield
    ("at most 12.5 MPa, no yield to judge")."""
    rows = [r for r in members or [] if isinstance(r, dict)]
    safe = [r for r in rows if isinstance(r.get("safety"), (int, float))]
    if safe:
        w = min(safe, key=lambda r: r["safety"])
        head = "least safety" if w["safety"] >= 1 else "past yield: safety"
        return f"{head} {w['safety']:g}, {w.get('member')}"
    vm = [r["vonMisesMPa"] for r in rows if isinstance(r.get("vonMisesMPa"), (int, float))]
    if vm:
        return f"at most {max(vm):.3g} MPa, no yield to judge"
    return "solved"


# The frame dfm_check reads a part in: the body's own, +z of the body up (a
# print setup's "up" is +z only). A body an assembly turned (its Placement)
# is read as it is modelled, not in its assembled pose (desk-lamp test
# drive, finding 7).
FRAME_OWN = "the body's own frame: +z of the body up, as modelled"
FRAME_MOVED = "the body's own frame: +z of the body up, as modelled (its Placement in the document, such as an assembly's pose, is left out)"


def print_frame(body_obj):
    """(shape, frame words, placement): the body's shape in its own frame,
    the words that say so, and the placement taken out (None when there
    was none to take out)."""
    shape = body_obj.Shape
    pl = getattr(body_obj, "Placement", None)
    try:
        moved = pl is not None and not pl.isIdentity()
    except Exception:  # noqa: BLE001 — a stand-in without isIdentity: as it is
        moved = False
    if not moved:
        return shape, FRAME_OWN, None
    local = shape.copy()
    local.Placement = pl.inverse().multiply(shape.Placement)
    return local, FRAME_MOVED, pl


def _rec_frame(rec, placement):
    """The placement a record's coordinates are in: the body's when it was
    embedded (the record's frame), else the body's now."""
    f = rec.get("frame")
    if isinstance(f, list) and len(f) == 7:
        import FreeCAD

        return FreeCAD.Placement(FreeCAD.Vector(*f[:3]), FreeCAD.Rotation(*f[3:]))
    return placement


def carried_tops(doc, body_obj, placement, shape):
    """The tops of the pockets hw_embed made in the body, in the frame of
    shape (print_frame's): [{ id, what, at [x, y, z], reach, area }]. After
    the pause the part in the pocket carries the layers that close over
    it, so a flat ceiling there is no bridge. A record whose pocket is
    filled (an undo) is left out."""
    import math

    try:
        import FreeCAD
    except ImportError:
        return []
    out = []
    for r in (records.read(doc, "embeds", {}) or {}).get(body_obj.Label, []) or []:
        try:
            x, y, z0 = (float(v) for v in r["at"])
            top = z0 + float(r["top"]) - float(r["floor"])
            sizes = [float(v) for v in r["pocket"]]
            kind = r.get("shape")
            frm = _rec_frame(r, placement)
            inv = frm.inverse() if frm is not None else None

            def here(v):
                v = FreeCAD.Vector(*v)
                return inv.multVec(v) if inv is not None else v

            c = r.get("centre")
            if c and shape.isInside(here(c), 1e-6, True):
                continue  # filled again: no pocket there now
            p = here((x, y, top))
            if kind == "cyl":
                reach, area = sizes[0] / 2, math.pi * (sizes[0] / 2) ** 2
            elif kind == "hex":
                reach, area = sizes[0] / math.sqrt(3), math.sqrt(3) / 2 * sizes[0] ** 2
            else:
                reach, area = math.hypot(sizes[0], sizes[1]) / 2, sizes[0] * sizes[1]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        out.append({"id": r.get("id", "E?"), "what": r.get("what", "the part"), "at": [p.x, p.y, p.z], "reach": reach + 0.05, "area": area})
    return out


def dfm(doc, body_obj, waive=None, last=None):
    """The printability check of a body as it stands on the bed, its
    print setup's rules, in the body's own frame (print_frame). waive:
    {id, reason} of a finding of `last` (the previous check's findings) to
    keep as waived."""
    from . import printability

    waivers = records.waivers(doc)
    if waive:
        f = next((x for x in (last or []) if x["id"] == waive.get("id")), None)
        if f is None:
            raise Refused(f"waive.id {waive.get('id')!r}: not a finding of the last check on {body_obj.Label} — dfm_check it first.", "not_found")
        waivers.append({"body": body_obj.Label, "rule": f["rule"], "at": f["at"], "reason": waive.get("reason") or "waived"})
        records.write(doc, "waivers", waivers)
    rules, setup = rules_of(doc, body_obj.Label)
    shape, frame, pl = print_frame(body_obj)
    out = printability.check(shape, rules, [x for x in waivers if x.get("body") == body_obj.Label], carried=carried_tops(doc, body_obj, pl, shape))
    out["body"] = body_obj.Label
    out["frame"] = frame
    out["verdict"] = dfm_verdict(out.get("findings"))
    if setup:
        out["setup"] = f"{setup['name']} ({setup['id']})"
    return out
