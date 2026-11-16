# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's geometry.py, trimmed to what Documents uses; 14 Nov 2026.
# Shape building and reading on FreeCAD's Part module: rounded-rectangle
# prisms and ruled lofts (what the generators are made of), and the readings
# the checks give — sound or not, sliver faces, the least wall by rays.
# Everything in millimetres, the document's own unit.


# ---- readings -----------------------------------------------------------------------------

def r3(v):
    return round(float(v), 3) + 0.0


def vec(v):
    return [r3(v.x), r3(v.y), r3(v.z)]


def box_of(shape):
    b = shape.BoundBox
    return {"min": [r3(b.XMin), r3(b.YMin), r3(b.ZMin)], "max": [r3(b.XMax), r3(b.YMax), r3(b.ZMax)], "size": [r3(b.XLength), r3(b.YLength), r3(b.ZLength)]}


def stats(shape):
    """What a body is, in a few numbers: what a diff compares."""
    return {
        "volume": round(shape.Volume, 2),
        "area": round(shape.Area, 2),
        "faces": len(shape.Faces),
        "solids": len(shape.Solids),
        "box": box_of(shape)["size"],
    }


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


def _ray_hits(shape, rays, reach, tol=0.01):
    """For each ray (start, inward normal), how far in it leaves the
    material: the nearest crossing of the shape's surface past 2 µm, within
    reach, or None. All rays against one fine tessellation at once
    (Möller–Trumbore, numpy), in place of a boolean per ray."""
    import numpy as np

    pts, tris = shape.tessellate(tol)
    if not tris or not rays:
        return [None] * len(rays)
    P = np.array([[q.x, q.y, q.z] for q in pts], dtype=float)
    T = np.array(tris)
    v0, v1, v2 = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    e1, e2 = v1 - v0, v2 - v0
    out = []
    for p, n in rays:
        o = np.array([p.x, p.y, p.z], dtype=float)
        d = -np.array([n.x, n.y, n.z], dtype=float)
        h = np.cross(d, e2)
        a = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(a) > 1e-12
        f = np.zeros_like(a)
        f[ok] = 1.0 / a[ok]
        s_ = o - v0
        u = f * np.einsum("ij,ij->i", s_, h)
        q = np.cross(s_, e1)
        v = f * (q @ d)
        t = f * np.einsum("ij,ij->i", e2, q)
        m = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 2e-3) & (t <= reach)
        out.append(round(float(t[m].min()), 3) if m.any() else None)
    return out
