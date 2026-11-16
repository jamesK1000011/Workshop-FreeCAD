# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make's own copy of Agent Link for FreeCAD's geometry.py, trimmed to what Make uses; 14 Nov 2026.
# Shape building and reading on FreeCAD's Part module: rounded-rectangle
# prisms and ruled lofts (what the generators are made of), and the readings
# the checks give — sound or not, sliver faces, the least wall by rays.
# Everything in millimetres, the document's own unit.

import math

import Part


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


def rebuilt(o, what="a cut"):
    """Why a shape written into o (o.Shape = …) would not stay, as a
    sentence saying what to do, or None when it stays. Only a plain
    Part::Feature keeps a shape given to it: its execute() leaves Shape
    alone. Writing Shape touches the object, and at the next recompute a
    PartDesign Body takes its tip's shape again (Body::execute), a
    primitive, a boolean or an extrusion its own (Part::Box::execute …):
    the cut was gone while the answer said it was made. An object without
    a TypeId (a test's stand-in) is taken as plain."""
    t = getattr(o, "TypeId", None)
    if t is None or t == "Part::Feature":
        return None
    if t == "PartDesign::Body":
        kind, source = "a PartDesign Body", "its features"
    else:
        kind, source = f"a parametric object ({t})", "its own properties"
    label = getattr(o, "Label", "it")
    return (f"{label} is {kind}: FreeCAD rebuilds its shape from {source} at the next recompute, so {what} written into it as a plain shape "
            f"would be gone again. Work on a plain copy: part_transform {{ body: \"{label}\", op: \"move\", by: [0, 0, 0], copy: true, name: \"{label} plain\" }} "
            f"makes one (a plain Part solid, no history), then this call again with body \"{label} plain\" — its setup, material and spec are per body: "
            f"setup set {{ id, add: [\"{label} plain\"] }}.")


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


def freecad_check(shape):
    """FreeCAD's own Part Check Geometry on shape (Part_CheckGeometry's
    check, Shape.check: BRepCheck_Analyzer, and the BOP check when FreeCAD's
    Check Geometry preference runs it). [its findings], [] when it passes,
    None when this FreeCAD cannot run it."""
    bop = False
    try:
        import FreeCAD

        bop = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Part/CheckGeometry").GetBool("RunBOPCheck", False)
    except Exception:  # noqa: BLE001
        bop = False
    if not hasattr(shape, "check"):
        return None
    try:
        shape.check(bool(bop))
        return []
    except Exception as e:  # noqa: BLE001 — its findings come as the error's text
        lines = [ln.strip() for ln in str(e).splitlines() if ln.strip()]
        return lines or [str(e) or "FreeCAD's Check Geometry found the shape invalid"]


def soundness(shape):
    """Sound for making: FreeCAD's own Check Geometry passes (the validity
    check is FreeCAD's, not Make's), then what a printed part also needs and
    Check Geometry does not judge: closed (an inside to print or weigh), one
    solid, no slivers a slicer chokes on."""
    shells = shape.Shells
    closed = bool(shells) and all(s.isClosed() for s in shells)
    narrow = narrow_faces(shape)
    short = short_edges(shape)
    problems = []
    found = freecad_check(shape)
    if found is None:  # an older FreeCAD: its validity flag alone
        found = [] if shape.isValid() else ["the shape is not valid"]
    if found:
        problems.append("FreeCAD's Check Geometry finds the shape broken (" + "; ".join(found[:3])
                        + (f"; and {len(found) - 3} more" if len(found) > 3 else "") + "): a boolean or loft left it so. Rebuild the last step.")
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
        "valid": not found,
        "checkedBy": "FreeCAD's Check Geometry",
        **({"checkGeometry": found[:10]} if found else {}),
        "closed": closed,
        "solids": len(shape.Solids),
        "narrow": narrow[:10],
        "shortEdges": short[:10],
        "problems": problems,
        "ok": not problems,
    }


def least_wall(shape, spacing=3.0, reach=12.0, cap=600):
    """The least wall, by rays: from points spread over every face, straight
    in along the face's normal to where the ray leaves the material. Gives
    the least, where, and how many samples read under each limit asked.
    Points within half a spacing of an edge are skipped: a ray there grazes
    the next face and reads its corner, not a wall."""
    solid = shape.Solids[0] if shape.Solids else shape
    samples = []
    faces = sorted(shape.Faces, key=lambda f: -f.Area)
    total_area = sum(f.Area for f in faces) or 1.0
    budget = cap
    for f in faces:
        n = max(1, min(budget, int(round(cap * f.Area / total_area))))
        if budget <= 0:
            break
        u0, u1, v0, v1 = f.ParameterRange
        k = max(1, int(math.sqrt(n)))
        # How far apart this face's points land: the run-joining in
        # thin_runs goes by it, since a big face is sampled sparsely.
        bb = f.BoundBox
        step = max(bb.XLength, bb.YLength, bb.ZLength) / k
        taken = 0
        for i in range(k):
            for j in range(k):
                u = u0 + (u1 - u0) * (i + 0.5) / k
                v = v0 + (v1 - v0) * (j + 0.5) / k
                try:
                    p = f.valueAt(u, v)
                    if not f.isInside(p, 1e-6, True):
                        continue
                    vx = Part.Vertex(p)
                    if min(w.distToShape(vx)[0] for w in f.Wires) < spacing / 2:
                        continue
                    nrm = f.normalAt(u, v)
                except Exception:
                    continue
                if nrm.Length < 1e-9:
                    continue
                nrm.normalize()
                # The ray goes into the material: a reversed face's normal
                # can point either way depending on the version, so test it.
                if not solid.isInside(p - nrm * 0.05, 1e-6, False):
                    nrm = nrm * -1
                    if not solid.isInside(p - nrm * 0.05, 1e-6, False):
                        continue
                samples.append((p, nrm, step))
                taken += 1
        budget -= taken
    least = None
    readings = []
    normals = []
    hits = _ray_hits(shape, [(p, nrm) for (p, nrm, _) in samples], reach)
    for (p, nrm, step), t in zip(samples, hits):
        if t is None:
            continue
        readings.append((t, vec(p), step))
        normals.append((nrm.x, nrm.y, nrm.z))
        if least is None or t < least[0]:
            least = (t, p)
    if least is None:
        return {"least": None, "samples": len(samples), "read": 0}
    return {"least": round(least[0], 3), "at": vec(least[1]), "samples": len(samples), "read": len(readings), "readings": readings, "normals": normals, "spacing": spacing}


def thin_runs(readings, limit, link):
    """The readings under `limit` joined into runs, one per thin place: two
    are one run when within 1.6 of their faces' sample spacing (or `link`,
    the least) of each other. Each run: its least and where,
    and how many readings it holds. A lip thin all the way round is one run,
    so one waiver covers it."""
    thin = [(t, p, st) for (t, p, st) in readings if t < limit]
    parent = list(range(len(thin)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(thin)):
        for j in range(i + 1, len(thin)):
            a, b = thin[i][1], thin[j][1]
            reach = max(link, 1.6 * max(thin[i][2], thin[j][2]))
            if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2 <= reach * reach:
                parent[root(i)] = root(j)
    runs = {}
    for i, (t, p, _) in enumerate(thin):
        r = runs.setdefault(root(i), {"least": t, "at": p, "count": 0, "points": []})
        r["count"] += 1
        r["points"].append(p)
        if t < r["least"]:
            r["least"], r["at"] = t, p
    return sorted(runs.values(), key=lambda r: r["least"])


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
