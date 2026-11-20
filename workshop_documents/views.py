# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents (moved from Agent Link for FreeCAD on 14 Nov 2026).
# Views of shapes, as a drawing has them: Open CASCADE's exact hidden-line
# removal through Part.HLRBRep, the edges seen and the edges hidden, as 2D
# polylines in the view's own millimetres (x right, y up). The directions
# are TechDraw's: Z points from the part to the viewer.

import math

import FreeCAD
import Part

V = FreeCAD.Vector

# name: (towards the viewer, the view's x on the paper)
VIEWS = {
    "front": ((0, -1, 0), (1, 0, 0)),
    "back": ((0, 1, 0), (-1, 0, 0)),
    "top": ((0, 0, 1), (1, 0, 0)),
    "bottom": ((0, 0, -1), (1, 0, 0)),
    "right": ((1, 0, 0), (0, 1, 0)),
    "left": ((-1, 0, 0), (0, -1, 0)),
    "iso": ((1, -1, 1), (1, 1, 0)),
}
# Which model axes a view's horizontal and vertical show (orthographic only).
AXES = {"front": ("x", "z"), "back": ("x", "z"), "top": ("x", "y"), "bottom": ("x", "y"), "right": ("y", "z"), "left": ("y", "z")}
WORDS = {
    "front": "a front elevation view",
    "back": "a rear elevation view",
    "top": "a top plan view",
    "bottom": "a bottom plan view",
    "right": "a right side elevation view",
    "left": "a left side elevation view",
    "iso": "an isometric view",
}


def frame(view):
    z, x = VIEWS[view]
    Z, X = V(*z), V(*x)
    Z.normalize()
    X.normalize()
    Y = Z.cross(X)
    Y.normalize()
    return Z, X, Y


def point(p, view):
    """A 3D point's place in a view, (x, y) mm."""
    _, X, Y = frame(view)
    return (p.dot(X), p.dot(Y))


def fit_circle(pts, tol=0.01, share=0.003):
    """The circle through 2D points, when they lie on one: (cx, cy, r,
    turn), turn the angle the points cover (radians), else None. Within tol
    mm or share of the radius, whichever is more. A hole that enters a round
    face (a pin through a forked round post) meets it in a 3D curve, not a
    circle; seen along the hole's axis that curve lies on the circle of the
    hole, but HLR gives it as a B-spline. Plain Python (Kasa's least squares)."""
    pts = [(float(x), float(y)) for x, y in pts]
    n = len(pts)
    if n < 5:
        return None
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    q = [(x - mx, y - my) for x, y in pts]
    suu = sum(u * u for u, _ in q)
    svv = sum(v * v for _, v in q)
    suv = sum(u * v for u, v in q)
    suuu = sum(u ** 3 for u, _ in q)
    svvv = sum(v ** 3 for _, v in q)
    suvv = sum(u * v * v for u, v in q)
    svuu = sum(v * u * u for u, v in q)
    det = suu * svv - suv * suv
    if abs(det) < 1e-12:
        return None
    bu, bv = 0.5 * (suuu + suvv), 0.5 * (svvv + svuu)
    uc, vc = (bu * svv - bv * suv) / det, (bv * suu - bu * suv) / det
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    if r < 0.05:
        return None
    cx, cy = uc + mx, vc + my
    if max(abs(math.hypot(x - cx, y - cy) - r) for x, y in pts) > max(tol, share * r):
        return None
    ang = sorted(math.atan2(y - cy, x - cx) for x, y in pts)
    gaps = [b - a for a, b in zip(ang, ang[1:])] + [ang[0] + 2 * math.pi - ang[-1]]
    turn = 2 * math.pi - max(gaps)
    # A nearly straight run fits a huge circle: a curve must turn.
    if turn < 0.3:
        return None
    if max(gaps) < 0.35:  # the points go all the way round
        turn = 2 * math.pi
    return cx, cy, r, turn


def _polys(comp, kind, out, deflection, circles=None):
    if comp is None or comp.isNull():
        return
    for e in comp.Edges:
        try:
            pts = e.discretize(Deflection=deflection)
        except Exception:  # a degenerate edge HLR left: nothing to draw
            pts = []
        if circles is not None:
            # A round edge drawn (a hole seen end on, or an arc of one):
            # its centre and radius in the view, for callouts to land on.
            try:
                cu = e.Curve
                c = None
                if type(cu).__name__ == "Circle" or isinstance(cu, Part.Circle):
                    c = (round(cu.Center.x, 4), round(cu.Center.y, 4), round(cu.Radius, 4))
                elif type(cu).__name__ not in ("Line", "LineSegment") and len(pts) >= 5:
                    # Drawn round but not a circle in the model (a hole's
                    # rim on a round face): the circle its points lie on.
                    f = fit_circle([(p.x, p.y) for p in e.discretize(Number=max(24, len(pts)))])
                    if f is not None:
                        c = (round(f[0], 4), round(f[1], 4), round(f[2], 4))
                if c is not None and c not in circles:
                    circles.append(c)
            except Exception:  # noqa: BLE001
                pass
        if len(pts) >= 2:
            out.append((kind, [(p.x, p.y) for p in pts]))


def _diagonal(shapes):
    try:
        bb = shapes[0].BoundBox
        for sh in shapes[1:]:
            bb.add(sh.BoundBox)
        return float(bb.DiagonalLength)
    except Exception:  # noqa: BLE001
        return 0.0


def deflection_for(shapes, least=0.02, share=1e-4):
    """How far a drawn polyline may stray from its curve, mm: 0.02 mm, or
    a ten-thousandth of the shapes' diagonal when that is more. Found live
    (the bicycle, 1.7 m): at 0.02 mm every curve of a large assembly was
    cut into many thousands of points, which is far finer than the paper
    shows at the scale such a part is drawn."""
    return max(least, share * _diagonal(shapes))


def edge_count(shapes):
    """The edges of the shapes together: how much a view has to work out."""
    n = 0
    for sh in shapes:
        try:
            n += len(sh.Edges)
        except Exception:  # noqa: BLE001
            pass
    return n


def extents(shapes, names, tol=None):
    """{view: box (xmin, ymin, xmax, ymax)} of the shapes in each view,
    from their tessellation (and their vertices), without hidden-line
    removal: what the layout needs, in a small part of the time. Within
    tol (a two-thousandth of the diagonal when not given) of the box that
    project gives. The corners of the shapes' boxes when there is no
    tessellation."""
    tol = tol or max(0.05, _diagonal(shapes) / 2000.0)
    pts = []
    for sh in shapes:
        got = []
        try:
            got = list(sh.tessellate(tol)[0])
        except Exception:  # noqa: BLE001
            got = []
        try:
            got += [x.Point for x in sh.Vertexes]
        except Exception:  # noqa: BLE001
            pass
        if not got:
            b = sh.BoundBox
            got = [V(x, y, z) for x in (b.XMin, b.XMax) for y in (b.YMin, b.YMax) for z in (b.ZMin, b.ZMax)]
        pts += got
    out = {}
    for name in names:
        _, X, Y = frame(name)
        xs = [p.dot(X) for p in pts]
        ys = [p.dot(Y) for p in pts]
        out[name] = (min(xs), min(ys), max(xs), max(ys))
    return out


def project(shapes, view, hidden=False, deflection=None):
    """The view of shapes, each hiding the others: {lines: [(kind, [(x, y)
    …])], box: (xmin, ymin, xmax, ymax), circles: [(cx, cy, r)] the round
    edges drawn visible (whole or arcs)}. Kinds: visible, hidden (when
    asked), thin (the seams where faces meet smoothly). deflection: left
    out, deflection_for(shapes)."""
    if deflection is None:
        deflection = deflection_for(shapes)
    Z, X, _ = frame(view)
    algo = Part.HLRBRep.Algo()
    for sh in shapes:
        algo.add(sh)
    algo.setProjector(Origin=V(0, 0, 0), ZDir=Z, XDir=X)
    algo.update()
    algo.hide()
    hs = Part.HLRBRep.HLRToShape(algo)
    lines, circles = [], []
    _polys(hs.vCompound(), "visible", lines, deflection, circles)
    _polys(hs.outLineVCompound(), "visible", lines, deflection, circles)
    _polys(hs.Rg1LineVCompound(), "thin", lines, deflection)
    if hidden:
        _polys(hs.hCompound(), "hidden", lines, deflection)
        _polys(hs.outLineHCompound(), "hidden", lines, deflection)
    xs = [x for (_, pts) in lines for (x, _) in pts]
    ys = [y for (_, pts) in lines for (_, y) in pts]
    if not xs:
        # Nothing came back: the corners of the shapes' boxes give the extent.
        pts = []
        for sh in shapes:
            b = sh.BoundBox
            pts += [point(V(x, y, z), view) for x in (b.XMin, b.XMax) for y in (b.YMin, b.YMax) for z in (b.ZMin, b.ZMax)]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return {"lines": lines, "box": (min(xs), min(ys), max(xs), max(ys)), "circles": circles}


def visible_point(shape, others, view, tries=8):
    """A point on a shape's face that the viewer sees in this view, other
    shapes in front counted: the faces turned most to the viewer, biggest
    first. None when every face tried is hidden."""
    from workshop_documents.geo import _ray_hits

    Z, _, _ = frame(view)
    solid = shape.Solids[0] if shape.Solids else None
    faces = []
    for f in shape.Faces:
        try:
            u0, u1, v0, v1 = f.ParameterRange
            u, v = (u0 + u1) / 2, (v0 + v1) / 2
            n = f.normalAt(u, v)
            p = f.valueAt(u, v)
        except Exception:
            continue
        if n.Length < 1e-9:
            continue
        n.normalize()
        # Outward: which way a reversed face's normal points varies by
        # version, so test it against the solid.
        if solid is not None and solid.isInside(p + n * 0.05, 1e-6, False):
            n = n * -1
        facing = n.dot(Z)
        if facing > 0.15:
            faces.append((f.Area * facing, f))
    faces.sort(key=lambda t: -t[0])
    blockers = [shape] + list(others)
    comp = Part.makeCompound(blockers)
    for _, f in faces[:tries]:
        u0, u1, v0, v1 = f.ParameterRange
        for (fu, fv) in ((0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3)):
            u, v = u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv
            try:
                p = f.valueAt(u, v)
                if not f.isInside(p, 1e-6, True):
                    continue
            except Exception:
                continue
            # A ray from just off the face towards the viewer: nothing hit, seen.
            start = p + Z * 0.02
            hit = _ray_hits(comp, [(start, Z * -1)], 1e5, tol=0.05)[0]
            if hit is None:
                return p
    return None


# ---- a full section --------------------------------------------------------------------

def section(shapes, view, at=0.0, hidden=False, deflection=None):
    """The view as a full section: the parts cut by a plane square to the
    view, through their middle moved `at` mm towards the viewer, and the
    material between the plane and the viewer taken away. As project, plus
    cut: the cut faces as closed 2D polygons (to hatch), and plane: the
    plane's depth along the view's Z."""
    if deflection is None:
        deflection = deflection_for(shapes)
    Z, X, Y = frame(view)
    bb = shapes[0].BoundBox
    for sh in shapes[1:]:
        bb.add(sh.BoundBox)
    d = bb.Center.dot(Z) + float(at)
    L = 4 * bb.DiagonalLength + 10
    # A block covering everything on the viewer's side of the plane.
    m = FreeCAD.Matrix(X.x, Y.x, Z.x, 0, X.y, Y.y, Z.y, 0, X.z, Y.z, Z.z, 0, 0, 0, 0, 1)
    block = Part.makeBox(2 * L, 2 * L, L, V(-L, -L, 0))
    block.transformShape(m)
    block.translate(Z * d + (bb.Center - Z * bb.Center.dot(Z)))
    kept, cut = [], []
    for sh in shapes:
        try:
            k = sh.cut(block)
        except Exception:
            k = sh
        if not k.isNull() and k.Solids:
            kept.append(k)
        for w in sh.slice(Z, d):
            if not w.isClosed():
                continue
            pts = [point(p, view) for p in w.discretize(Deflection=deflection)]
            if len(pts) >= 3:
                cut.append(pts)
    if not kept:
        raise ValueError("the plane misses the parts")
    out = project(kept, view, hidden, deflection)
    out["cut"] = cut
    out["plane"] = d
    return out


def hatch(polys, spacing, angle=45.0):
    """Hatch lines across closed polygons (even-odd, so holes stay clear):
    [((x0, y0), (x1, y1))], `spacing` apart at `angle` degrees."""
    if not polys or spacing <= 0:
        return []
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)      # along the lines
    nx, ny = -uy, ux                        # across them
    edges = []
    for poly in polys:
        n = len(poly)
        for i in range(n):
            p, q = poly[i], poly[(i + 1) % n]
            edges.append((p, q))
    s = [p[0] * nx + p[1] * ny for poly in polys for p in poly]
    lo, hi = min(s), max(s)
    out = []
    k = math.floor(lo / spacing) + 1
    while k * spacing < hi:
        c = k * spacing
        ts = []
        for p, q in edges:
            sp, sq = p[0] * nx + p[1] * ny - c, q[0] * nx + q[1] * ny - c
            if (sp < 0) != (sq < 0):
                t = sp / (sp - sq)
                x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
                ts.append(x * ux + y * uy)
        ts.sort()
        for i in range(0, len(ts) - 1, 2):
            t0, t1 = ts[i], ts[i + 1]
            out.append(((c * nx + t0 * ux, c * ny + t0 * uy), (c * nx + t1 * ux, c * ny + t1 * uy)))
        k += 1
    return out
