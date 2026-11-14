# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's Python API: what a macro, a command or an agent calls alike.
Plain values in, plain values out (mm); a refusal is addonkit.Refused with
what to do instead. Nothing here imports Agent Link.

    from workshop_make import api
    api.thread("M6")                    # sizes from the standards
    api.nearest_threads(4.98, inside=True)
    api.calibration(doc, "Bracket")     # the printer fit the sizes take
    api.fit_size(8.0, "hole", "slide", doc=doc)
    api.hole(doc, "Bracket", "counterbore", "M3", at=[10, 10, 5])
"""

import addonkit
from addonkit import Refused, fits, geo, records

from . import embeds, threads

addonkit.require(">=1.1,<2", "Workshop Make")

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
