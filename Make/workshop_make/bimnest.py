# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cut Export's layout by FreeCAD's own BIM Nest (BIM_Nest, the nesting
module ArchNesting): the parts' flat profiles nested in the sheet, turns
off (a sheet part keeps the way it was drawn, for the grain and the
machine's own setup), the gap as BIM Nest's margin. Make keeps its own
kerf, least-feature rules, cut check and DXF/SVG writer; only the
positions come from BIM Nest. Without BIM (or with no sheet size to nest
in) Cut Export lays the parts out in rows as before and says so.

Reading BIM Nest's answer back to each part is pure Python (tested
without FreeCAD)."""


def _key(area, w, h):
    return (round(area, 1), round(w, 1), round(h, 1))


def match_moves(origs, placed, tol=0.2):
    """Each original's (dx, dy) to where BIM Nest put a face of its size, or
    None for one it left out. origs and placed: [(area, w, h, xmin, ymin)];
    copies of one part are alike, so any placed face of its size is its."""
    free = list(range(len(placed)))
    out = []
    for a, w, h, x0, y0 in origs:
        hit = None
        for j in free:
            pa, pw, ph, px, py = placed[j]
            if abs(pa - a) <= tol * max(1.0, a / 100) and abs(pw - w) <= tol and abs(ph - h) <= tol:
                hit = j
                break
        if hit is None:
            out.append(None)
            continue
        free.remove(hit)
        out.append((placed[hit][3] - x0, placed[hit][4] - y0))
    return out


def _faces_of(result):
    """BIM Nest's placed shapes, whatever list it keeps them in."""
    if result is None:
        return []
    if hasattr(result, "Faces") and not isinstance(result, (list, tuple)):
        return list(result.Faces)
    out = []
    for r in result:
        if hasattr(r, "Area") and hasattr(r, "BoundBox"):
            out.append(r)
        elif isinstance(r, (list, tuple)):
            out += [x for x in r if hasattr(x, "Area") and hasattr(x, "BoundBox")]
    return out


def _desc(f):
    b = f.BoundBox
    return (f.Area, b.XLength, b.YLength, b.XMin, b.YMin)


def nest(faces, W, H, gap):
    """[(dx, dy) or None for each face] by BIM Nest in a W x H mm sheet, or
    (None, why not)."""
    try:
        import ArchNesting
    except ImportError:
        return None, "FreeCAD's BIM Nest (ArchNesting) is not in this FreeCAD"
    try:
        import Part

        nester = ArchNesting.Nester(container=Part.makePlane(W, H), shapes=list(faces))
        for attr, v in (("margin", gap), ("rotations", [0])):
            if hasattr(nester, attr):
                setattr(nester, attr, v)
        nester.run()
        results = getattr(nester, "results", None) or []
        placed = _faces_of(results[-1] if results else None)
        if not placed:
            return None, "BIM Nest placed nothing in the sheet"
        return match_moves([_desc(f) for f in faces], [_desc(f) for f in placed]), None
    except Exception as e:  # noqa: BLE001
        return None, f"BIM Nest could not nest them here ({e})"
