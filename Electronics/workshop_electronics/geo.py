# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Electronics' own copy of Agent Link for FreeCAD's geometry.py, trimmed to what Electronics uses; 14 Nov 2026.
# Shape building and reading on FreeCAD's Part module: rounded-rectangle
# prisms and ruled lofts (what the generators are made of), and the readings
# the checks give — sound or not, sliver faces, the least wall by rays.
# Everything in millimetres, the document's own unit.

import math

import FreeCAD
import Part

V = FreeCAD.Vector


def round_rect(cx, cy, w, d, r, z):
    """A w x d rectangle centred on (cx, cy) at height z, corners of radius r,
    as a closed wire. Always eight edges when r > 0, so ruled lofts between
    stations pair edge for edge."""
    hw, hd = w / 2.0, d / 2.0
    R = max(0.0, min(r, hw - 1e-3, hd - 1e-3))
    if R < 1e-3:
        p = [V(cx - hw, cy - hd, z), V(cx + hw, cy - hd, z), V(cx + hw, cy + hd, z), V(cx - hw, cy + hd, z)]
        return Part.Wire([Part.LineSegment(p[i], p[(i + 1) % 4]).toShape() for i in range(4)])
    x0, x1, y0, y1 = cx - hw, cx + hw, cy - hd, cy + hd
    c = R * (1 - math.sqrt(0.5))
    e = [
        Part.LineSegment(V(x0 + R, y0, z), V(x1 - R, y0, z)).toShape(),
        Part.Arc(V(x1 - R, y0, z), V(x1 - c, y0 + c, z), V(x1, y0 + R, z)).toShape(),
        Part.LineSegment(V(x1, y0 + R, z), V(x1, y1 - R, z)).toShape(),
        Part.Arc(V(x1, y1 - R, z), V(x1 - c, y1 - c, z), V(x1 - R, y1, z)).toShape(),
        Part.LineSegment(V(x1 - R, y1, z), V(x0 + R, y1, z)).toShape(),
        Part.Arc(V(x0 + R, y1, z), V(x0 + c, y1 - c, z), V(x0, y1 - R, z)).toShape(),
        Part.LineSegment(V(x0, y1 - R, z), V(x0, y0 + R, z)).toShape(),
        Part.Arc(V(x0, y0 + R, z), V(x0 + c, y0 + c, z), V(x0 + R, y0, z)).toShape(),
    ]
    return Part.Wire(e)


def prism(cx, cy, w, d, r, z0, z1):
    """A rounded-rectangle prism from z0 up to z1."""
    return Part.Face(round_rect(cx, cy, w, d, r, z0)).extrude(V(0, 0, z1 - z0))


def cylinder(r, h, x, y, z):
    return Part.makeCylinder(r, h, V(x, y, z))


def fuse_all(shapes):
    out = shapes[0]
    if len(shapes) > 1:
        out = out.fuse(shapes[1:])
    return clean(out)


def cut_all(shape, tools):
    if not tools:
        return shape
    return clean(shape.cut(tools))


def clean(shape):
    """One solid, coplanar faces merged: a boolean leaves faces split where
    its pieces met, which reads as clutter and as short edges."""
    try:
        shape = shape.removeSplitter()
    except Exception:  # removeSplitter refuses some compounds; the shape stands
        pass
    if shape.ShapeType == "Compound" and len(shape.Solids) == 1:
        shape = shape.Solids[0]
    return shape


# ---- readings -----------------------------------------------------------------------------

def r3(v):
    return round(float(v), 3) + 0.0


def vec(v):
    return [r3(v.x), r3(v.y), r3(v.z)]


def narrow_faces(shape, width_mm=0.01):
    """Faces under width_mm wide, by 2 x area / perimeter — the width of a
    strip — a sliver two faces a hair apart leave, which a round beside it
    stumbles on."""
    out = []
    for i, f in enumerate(shape.Faces):
        p = sum(e.Length for e in f.Edges)
        if p <= 0:
            continue
        w = 2.0 * f.Area / p
        if w < width_mm:
            out.append({"index": i, "width": round(w, 5), "area": round(f.Area, 4), "centroid": vec(f.CenterOfMass)})
    return sorted(out, key=lambda x: x["width"])


def short_edges(shape, length_mm=0.02):
    out = []
    for i, e in enumerate(shape.Edges):
        if e.Length < length_mm:
            out.append({"index": i, "length": round(e.Length, 5), "at": vec(e.CenterOfMass)})
    return out


def soundness(shape):
    """Valid, closed, one solid, no slivers: as a body check reads it."""
    shells = shape.Shells
    closed = bool(shells) and all(s.isClosed() for s in shells)
    narrow = narrow_faces(shape)
    short = short_edges(shape)
    problems = []
    if not shape.isValid():
        problems.append("The shape is not valid: a boolean or loft left it broken. Rebuild the last step.")
    if not closed:
        problems.append("The shape is not closed: it has open edges, so it has no inside to print or weigh.")
    if len(shape.Solids) != 1:
        problems.append(f"{len(shape.Solids)} solids where one is meant: pieces that do not touch, or none.")
    if narrow:
        problems.append(
            f"{len(narrow)} face{'s' if len(narrow) != 1 else ''} under 0.01 mm wide — a sliver two faces a hair apart leave: "
            + ", ".join(f"{n['index']} ({n['width']} mm at {n['centroid']})" for n in narrow[:5])
            + ". Overlap the pieces clearly, or carry a cutter on along its slope."
        )
    return {
        "valid": shape.isValid(),
        "closed": closed,
        "solids": len(shape.Solids),
        "narrow": narrow[:10],
        "shortEdges": short[:10],
        "problems": problems,
        "ok": not problems,
    }
