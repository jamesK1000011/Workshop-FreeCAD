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

from . import embeds, threads


FIT_KINDS = tuple(fits.FITS)
HOLE_KINDS = fits.KINDS
SIZES = tuple(fits.M)


# ---- the printer's fit --------------------------------------------------------------------

def calibration(doc, body=None):
    """(calibration, where it came from): the body's print setup's fit, else
    the document's (fit calibrate), else the typical printer's."""
    s = records.setup_of(doc, body, "print") if body else None
    c = (s or {}).get("fit") or records.read(doc, "fit", None)
    return (c, "calibrated") if c else (dict(fits.DEFAULT_CAL), "none — the typical printer assumed (holes print 0.2 mm small)")


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
        cal, said = calibration(doc, body) if doc is not None else (dict(fits.DEFAULT_CAL), "none — the typical printer assumed")
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


def hole(doc, body, kind, size="M3", at=None, direction="-z", depth="through", fit="normal"):
    """Cut a hole for hardware into a body (a Part feature or PartDesign
    body's shape is replaced): clearance, counterbore, countersink,
    nut_trap, insert or magnet, sized from the standards plus the printer's
    fit. Answers the sizes used, what was removed and whether it is sound."""
    o = doc.getObjectsByLabel(body)[0] if isinstance(body, str) and doc.getObjectsByLabel(body) else body
    if o is None or isinstance(o, str):
        raise Refused(f"body: no body called {body}.", "not_found")
    if kind not in fits.KINDS:
        raise Refused(f"kind: one of {', '.join(fits.KINDS)}.")
    if not (isinstance(at, (list, tuple)) and len(at) == 3):
        raise Refused("at: [x, y, z], mm — where the hole enters the part, on its face.")
    cal, said = calibration(doc, o.Label)
    bb = o.Shape.BoundBox
    d = bb.DiagonalLength if depth == "through" else float(depth)
    try:
        tool, sizes = fits.hole_tool(kind, size, list(at), direction, d, fit, cal)
    except ValueError as e:
        raise Refused(str(e))
    before = o.Shape.Volume
    cut = geo.clean(o.Shape.cut(tool))
    removed = before - cut.Volume
    if removed < 1e-3:
        raise Refused(f"The hole cut nothing at {list(at)} going {direction}: put at on the part's face, dir into the material.", "failed")
    o.Shape = cut
    doc.recompute()
    s = geo.soundness(cut)
    return {"body": o.Label, "kind": kind, "size": size, "sizes": sizes, "printerFit": said, "removed": round(removed, 2),
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
            raise Refused(f"spec.{k}: minWall, massMin or massMax (numbers, mm and g).")
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


def rules_of(doc, body):
    """(rules, print setup) for a body: its print setup's nozzle and printer."""
    from . import printability

    s = records.setup_of(doc, body, "print") or {}
    return printability.rules_for(s.get("nozzle", "0.4"), s.get("printer")), s


def dfm(doc, body_obj, waive=None, last=None):
    """The printability check of a body as it stands on the bed, its
    print setup's rules. waive: {id, reason} of a finding of `last` (the
    previous check's findings) to keep as waived."""
    from . import printability

    waivers = records.waivers(doc)
    if waive:
        f = next((x for x in (last or []) if x["id"] == waive.get("id")), None)
        if f is None:
            raise Refused(f"waive.id {waive.get('id')!r}: not a finding of the last check on {body_obj.Label} — dfm_check it first.", "not_found")
        waivers.append({"body": body_obj.Label, "rule": f["rule"], "at": f["at"], "reason": waive.get("reason") or "waived"})
        records.write(doc, "waivers", waivers)
    rules, setup = rules_of(doc, body_obj.Label)
    out = printability.check(body_obj.Shape, rules, [x for x in waivers if x.get("body") == body_obj.Label])
    out["body"] = body_obj.Label
    if setup:
        out["setup"] = f"{setup['name']} ({setup['id']})"
    return out
