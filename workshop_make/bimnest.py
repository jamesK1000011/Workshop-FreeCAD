# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cut Export's layout by FreeCAD's own BIM Nest (BIM_Nest; the nesting
module ArchNesting). Make keeps its own kerf, least-feature rules, cut
check and DXF/SVG writer; only the positions come from BIM Nest. Without
BIM, or with no sheet to nest in, Cut Export lays the parts out in rows as
before and says so.

ArchNesting (FreeCAD 1.1.3, src/Mod/BIM/ArchNesting.py), as BIM_Nest's
task panel uses it:

- Nester(container, shapes): container a Part.Face (the sheet), shapes
  single-face shapes (each part's flat profile at z = 0);
- run() returns the sheets and appends them to nester.results: a list of
  sheets, each a list of [hashCode, face] — the original shape's
  hashCode() and the face as placed;
- it has no margin or rotation settings of its own: TOLERANCE and
  ROTATIONS are module constants.

Here the gap is kept by growing each profile by half of it and shrinking
the sheet by half of it a side; ROTATIONS is held at [0] while it runs (a
sheet part keeps the way it was drawn: the grain, the machine's own setup)
and put back after. Pieces BIM Nest put on a second sheet are left over,
as the rows leave them. Reading the answer back is pure Python (tested
without FreeCAD)."""


def sheets_of(nester, ran=None):
    """The sheets BIM Nest made: run()'s answer, else results[-1]."""
    if ran:
        return ran
    res = getattr(nester, "results", None) or []
    return res[-1] if res else []


def moves(keys, sheets, before):
    """Each piece's (dx, dy) on the first sheet, or None for one left over
    (on a later sheet or not placed). keys: each piece's hashCode, in
    order; sheets: [[[hashCode, face], ...], ...]; before: {hashCode:
    (xmin, ymin)} of the piece as given. A piece BIM Nest turned is
    refused (Turned): Make keeps parts as drawn."""
    first = {}
    for entry in (sheets[0] if sheets else []):
        h, face = entry[0], entry[1]
        first[h] = face
    out = []
    for h in keys:
        f = first.get(h)
        if f is None:
            out.append(None)
            continue
        b = f.BoundBox
        x0, y0, w0, h0 = before[h]
        if abs(b.XLength - w0) > 0.01 or abs(b.YLength - h0) > 0.01:
            raise Turned(f"BIM Nest turned a piece ({w0:g} x {h0:g} mm placed as {b.XLength:g} x {b.YLength:g} mm)")
        out.append((b.XMin - x0, b.YMin - y0))
    return out


class Turned(Exception):
    pass


def nest(faces, W, H, gap):
    """[(dx, dy) or None for each face] by BIM Nest in a W x H mm sheet,
    keeping gap mm between pieces and from the edge; or (None, why not)."""
    try:
        import ArchNesting
    except ImportError:
        return None, "FreeCAD's BIM Nest (ArchNesting) is not in this FreeCAD"
    try:
        import FreeCAD
        import Part

        half = gap / 2.0
        grown = []
        for f in faces:
            g = f.makeOffset2D(half, 2) if half > 0 else f.copy()
            if not hasattr(g, "Area") or len(getattr(g, "Faces", [g])) != 1:
                g = g.Faces[0]
            grown.append(g)
        container = Part.makePlane(W - gap, H - gap, FreeCAD.Vector(half, half, 0))
        before = {}
        keys = []
        for g in grown:
            b = g.BoundBox
            k = g.hashCode()
            keys.append(k)
            before[k] = (b.XMin, b.YMin, b.XLength, b.YLength)
        nester = ArchNesting.Nester(container, grown)
        held = getattr(ArchNesting, "ROTATIONS", None)
        try:
            ArchNesting.ROTATIONS = [0]
            ran = nester.run()
        finally:
            if held is not None:
                ArchNesting.ROTATIONS = held
        sheets = sheets_of(nester, ran)
        if not sheets or not sheets[0]:
            return None, "BIM Nest placed nothing in the sheet"
        return moves(keys, sheets, before), None
    except Turned as e:
        return None, str(e)
    except Exception as e:  # noqa: BLE001
        return None, f"BIM Nest could not nest them here ({e})"
