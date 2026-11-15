# SPDX-License-Identifier: LGPL-2.1-or-later
# The Parts add-on's functions: what a person's command, a macro and an
# agent all call. No agent needed; Agent Link's tools (agentlink_families)
# are a thin layer over these.

from workshop_parts.refusal import Refused
from workshop_parts import geo
from workshop_parts import records

from . import boxes, gridfinity

GENERATORS = {
    "gridfinity_bin": gridfinity.PARAMS,
    "gridfinity_baseplate": boxes.BASEPLATE,
    "project_box": boxes.PROJECT_BOX,
    "board_box": boxes.BOARD_BOX,
}

NAMES = {
    "gridfinity_bin": "Gridfinity bin",
    "gridfinity_baseplate": "Gridfinity baseplate",
    "project_box": "Project box",
    "board_box": "Board box",
}


def calibration(doc):
    """The printer's fit calibration kept with the document (Agent Link's
    fit calibrate writes it), else the typical printer's: holes print 0.2 mm
    small. Gives (calibration, how it was found)."""
    c = records.read(doc, "fit", None) if doc is not None else None
    if c:
        return {"hole": float(c.get("hole", 0.2)), "shaft": float(c.get("shaft", 0.0))}, "calibrated"
    return {"hole": 0.2, "shaft": 0.0}, "none — the typical printer assumed (holes print 0.2 mm small)"


def tight_box(shape):
    """The shape's extent, mm, tight: the plain bounding box runs a little
    loose round lofted faces."""
    try:
        b = shape.optimalBoundingBox(True, False)
    except Exception:  # an older FreeCAD without it: the plain box
        b = shape.BoundBox
    r = geo.r3
    return {"min": [r(b.XMin), r(b.YMin), r(b.ZMin)], "max": [r(b.XMax), r(b.YMax), r(b.ZMax)], "size": [r(b.XLength), r(b.YLength), r(b.ZLength)]}


def build(generator, params=None, cal=None):
    """(values, [(name, shape)], info) for a generator and its params,
    nothing added to a document. A value out of range: Refused."""
    if generator not in GENERATORS:
        raise Refused(f"generator: one of {', '.join(GENERATORS)}.")
    params = params or {}
    cal = cal or {"hole": 0.2, "shaft": 0.0}
    try:
        if generator == "gridfinity_bin":
            p = gridfinity.values(params)
            shape = gridfinity.bin_shape(p)
            mags = gridfinity.magnets(p)
            return p, [(gridfinity.name_of(p), shape)], ({"encased": mags} if mags else {})
        p = boxes.check(GENERATORS[generator], params)
    except ValueError as e:
        raise Refused(str(e))
    if generator == "gridfinity_baseplate":
        shape, info = boxes.baseplate_shape(p, cal)
        return p, [(f"Gridfinity baseplate {p['x']}x{p['y']}", shape)], info
    if generator == "project_box":
        box, lid, info = boxes.project_box(p, cal)
        n = f"Project box {p['length']:g}x{p['width']:g}x{p['height']:g}"
        return p, [(n, box), (n + " lid", lid)], info
    box, lid, info = boxes.board_box(p, cal)
    return p, [("Board box", box), ("Board box lid", lid)], info


def _unique(doc, label):
    taken = {o.Label for o in doc.Objects}
    if label not in taken:
        return label
    i = 2
    while f"{label} {i}" in taken:
        i += 1
    return f"{label} {i}"


def make(doc, generator, params=None, name=None, measure=False, placement=None):
    """Make a standard part in doc, each piece its own body (a box and its
    lid are two). measure: build it and give the sizes, add nothing.
    Gives {generator, values, parts [{name, volume, min, max, size}],
    bodies [labels], printerFit, …what the generator says}."""
    cal, said = calibration(doc)
    p, made, info = build(generator, params, cal)
    box = geo.box_of if generator == "gridfinity_bin" else tight_box
    parts = [{"name": n, "volume": round(sh.Volume, 1), **box(sh)} for (n, sh) in made]
    out = {"generator": generator, "values": p, "parts": parts, **info, "printerFit": said}
    if measure:
        return {**out, "made": False}
    if doc is None:
        raise Refused("No document to make it in: open or make one.", "invalid_state")
    labels = []
    for i, (n, shape) in enumerate(made):
        label = _unique(doc, (name + ("" if i == 0 else " lid")) if name else n)
        o = doc.addObject("Part::Feature", "Body")
        o.Label = label
        if placement is not None:
            shape = shape.copy()
            shape.translate(placement)
        o.Shape = shape
        labels.append(label)
    doc.recompute()
    out["bodies"] = labels
    out["sound"] = {lb: geo.soundness(sh)["ok"] for lb, (_, sh) in zip(labels, made)}
    return out


def check(generator, params=None):
    """The values for a generator's params, defaults filled in, each checked
    and nothing built (a task panel's live line). A value out of range:
    Refused."""
    if generator not in GENERATORS:
        raise Refused(f"generator: one of {', '.join(GENERATORS)}.")
    try:
        if generator == "gridfinity_bin":
            return gridfinity.values(params or {})
        return boxes.check(GENERATORS[generator], params or {})
    except ValueError as e:
        raise Refused(str(e))


def params(generator):
    """The parameter table for a generator: each one's kind, range, default
    and what it means (what the agent's tool description and the dialog
    show)."""
    if generator not in GENERATORS:
        raise Refused(f"generator: one of {', '.join(GENERATORS)}.")
    return GENERATORS[generator]
