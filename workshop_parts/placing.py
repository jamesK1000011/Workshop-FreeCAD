# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where a new generated part goes: beside what the document already holds,
never inside it. Pure Python (boxes as (xmin, ymin, zmin, xmax, ymax, zmax)
in mm), no FreeCAD; doc_boxes reads a document's visible solids."""

GAP = 10.0  # mm between the document's solids and the new part


def union(boxes):
    """The box round all the boxes, or None for none."""
    boxes = [tuple(float(v) for v in b) for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
            max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes))


def beside(existing, new, gap=GAP):
    """The move (dx, dy, dz) that puts the new part's box (new: a box or a
    list of boxes, a box and its lid) to the +X side of everything in
    existing (a list of boxes), gap mm clear. (0, 0, 0) when the document
    holds nothing: an empty document keeps the part at the origin. Y and Z
    stay as made (the part sits on the same bed)."""
    have = union(existing)
    if have is None:
        return (0.0, 0.0, 0.0)
    made = union(new if new and isinstance(new[0], (list, tuple)) else [new])
    if made is None:
        return (0.0, 0.0, 0.0)
    return (round(have[3] + gap - made[0], 6), 0.0, 0.0)


def shape_box(shape):
    b = shape.BoundBox
    return (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax)


def doc_boxes(doc):
    """The boxes of the document's visible solids (a PartDesign Body's
    hidden features are inside it, so the visible ones bound it)."""
    out = []
    for o in getattr(doc, "Objects", None) or []:
        if not getattr(o, "Visibility", True):
            continue
        sh = getattr(o, "Shape", None)
        try:
            if sh is None or sh.isNull() or not sh.Solids:
                continue
            out.append(shape_box(sh))
        except Exception:  # noqa: BLE001 — an object without a readable shape
            continue
    return out
