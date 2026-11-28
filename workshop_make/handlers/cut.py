# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts cut from sheet (laser, waterjet, plasma, router): is the body a
# sheet part — two parallel flat faces a constant thickness apart and every
# other face square to them — and can the setup's machine cut its profile:
# webs, slots and holes against the least feature for the machine, the
# material and the thickness; a router's inside corners against its
# cutter; plasma's holes against the thickness; the part against the
# sheet. Then the flat profiles, laid out in rows on the sheet, as DXF and
# SVG. The least features are rules of thumb, said as assumed: the cutting
# shop's own figures win.

import math
import os

import FreeCAD
import Part

from workshop_make import records as store

from .. import bimnest


def _window_up():
    try:
        import FreeCAD

        return bool(FreeCAD.GuiUp)
    except Exception:  # noqa: BLE001
        return False
from .. import sheetfile as sf


V = FreeCAD.Vector
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal

# The machines' kerfs and the materials are data (data/cut-machines.json,
# data/shop-materials.json); the person's own win. One list for setup and
# these tools (cutmachines.py): a machine's other names (fiber laser, CO2
# laser) are made into its key in one place.
from workshop_make import cutmachines as _cm

KERF = {k: v["kerf"] for k, v in _cm.machines().items()}
MACHINES = tuple(KERF)
METALS, OTHERS = _cm.cut_materials()
MAX_EDGES = 160


def rules(machine, material, t, kerf):
    """The least hole, web (material between cuts) and slot (gap cut out),
    and the hard floor under which it cannot be cut at all. Rules of thumb."""
    metal = material in METALS
    if machine == "laser":
        r = {"hole": max(0.5, t if metal else 0.5 * t), "web": max(0.5, t if metal else 0.5 * t), "slot": max(2 * kerf, 0.5 * t if metal else 0.0)}
        floor = {"hole": 2 * kerf, "slot": kerf}
    elif machine == "waterjet":
        r = {"hole": max(2 * kerf, 0.5 * t), "web": max(2 * kerf, 0.5 * t), "slot": max(1.5 * kerf, 0.0)}
        floor = {"hole": 1.5 * kerf, "slot": kerf}
    elif machine == "plasma":
        r = {"hole": max(1.5 * t, 3.0), "web": max(2 * kerf, t), "slot": max(2 * kerf, t)}
        floor = {"hole": t, "slot": kerf}
    else:  # router: the kerf is the cutter's diameter
        r = {"hole": kerf, "web": max(1.0 if metal else 1.5, 0.5 * t), "slot": kerf, "corner": kerf / 2}
        floor = {"hole": kerf, "slot": kerf}
    r = {k: round(v, 3) for k, v in r.items()}
    return r, {k: round(v, 3) for k, v in floor.items()}


# ---- reading a body as a sheet ------------------------------------------------------------

def _plane_normal(f):
    u0, u1, v0, v1 = f.ParameterRange
    n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
    n.normalize()
    return n


def _normals(f, k=3):
    u0, u1, v0, v1 = f.ParameterRange
    out = []
    for i in range(k):
        for j in range(k):
            u = u0 + (u1 - u0) * (i + 0.5) / k
            v = v0 + (v1 - v0) * (j + 0.5) / k
            try:
                n = f.normalAt(u, v)
            except Exception:
                continue
            if n.Length > 1e-9:
                n.normalize()
                out.append(n)
    return out


def sheet_of(shape):
    """{ sheet, thickness, normal, notSquare: [Face…], steps: [Face…] }."""
    planar = [(i, f) for i, f in enumerate(shape.Faces) if type(f.Surface).__name__ == "Plane"]
    if not planar:
        return {"sheet": False, "why": "no flat face to lie it on"}
    i0, big = max(planar, key=lambda x: x[1].Area)
    n = _plane_normal(big)
    offsets = {}
    not_square = []
    for i, f in enumerate(shape.Faces):
        ns = _normals(f)
        if type(f.Surface).__name__ == "Plane" and ns and abs(abs(ns[0].dot(n)) - 1) < 1e-6:
            d = round(f.CenterOfMass.dot(n), 4)
            key = next((k for k in offsets if abs(k - d) < 1e-3), d)
            offsets.setdefault(key, []).append(f"Face{i + 1}")
            continue
        if any(abs(m.dot(n)) > 1e-3 for m in ns):
            not_square.append(f"Face{i + 1}")
    ds = sorted(offsets)
    steps = []
    if len(ds) > 2:
        for d in ds[1:-1]:
            steps += offsets[d]
    t = ds[-1] - ds[0] if len(ds) >= 2 else 0.0
    ok = len(ds) == 2 and not not_square
    return {"sheet": ok, "thickness": round(t, 4), "normal": [round(n.x, 6), round(n.y, 6), round(n.z, 6)], "low": ds[0], "notSquare": not_square, "steps": steps}


def flatten(shape, info):
    """The body turned to lie flat, its low face on z = 0, its lower left at
    the origin; and its profile at mid-thickness: (flat solid, outer wire,
    hole wires)."""
    n = V(*info["normal"])
    rot = FreeCAD.Rotation(n, V(0, 0, 1))
    flat = shape.copy()
    flat.transformShape(FreeCAD.Placement(V(0, 0, 0), rot).toMatrix())
    bb = flat.BoundBox
    flat.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
    t = info["thickness"]
    wires = flat.slice(V(0, 0, 1), t / 2)
    if not wires:
        raise ToolError("failed", "The profile could not be read at mid-thickness.")
    wires = sorted(wires, key=lambda w: -w.BoundBox.DiagonalLength)
    return flat, wires[0], wires[1:]


def _ang(c, p):
    return math.degrees(math.atan2(p.y - c.y, p.x - c.x))


def primitives(wire, layer):
    out = []
    for e in wire.Edges:
        cname = type(e.Curve).__name__
        if cname in ("Line", "LineSegment"):
            a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
            out.append((layer, ("line", a.x, a.y, b.x, b.y)))
        elif cname == "Circle":
            c, r = e.Curve.Center, e.Curve.Radius
            if e.isClosed():
                out.append((layer, ("circle", c.x, c.y, r)))
            else:
                pa, pb = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
                if e.Curve.Axis.z > 0:
                    out.append((layer, ("arc", c.x, c.y, r, _ang(c, pa), _ang(c, pb))))
                else:
                    out.append((layer, ("arc", c.x, c.y, r, _ang(c, pb), _ang(c, pa))))
        else:
            pts = e.discretize(Deflection=0.01)
            out.append((layer, ("poly", [(p.x, p.y) for p in pts], e.isClosed())))
    return out


# ---- the checks on the profile ------------------------------------------------------------

def _tangent(e, p):
    try:
        t = e.tangentAt(e.Curve.parameter(p))
        t.normalize()
        return t
    except Exception:
        return None


def _in(flat, t, x, y):
    return flat.isInside(V(x, y, t / 2), 1e-6, True)


def narrows(flat, t, wires):
    """The narrowest places between the profile's edges: webs (material
    between two cuts) and gaps (cut-out slots), each { width, at }."""
    edges = [(wi, e) for wi, w in enumerate(wires) for e in w.Edges]
    if len(edges) > MAX_EDGES:
        return None, None
    webs, gaps = [], []
    for i in range(len(edges)):
        wi, ei = edges[i]
        for j in range(i + 1, len(edges)):
            wj, ej = edges[j]
            if wi == wj and any(a.Point.distanceToPoint(b.Point) < 1e-6 for a in ei.Vertexes for b in ej.Vertexes):
                continue
            d, pts, _ = ei.distToShape(ej)
            if d < 1e-6:
                continue
            p, q = pts[0]
            if wi == wj:
                seg = q - p
                seg.normalize()
                ti, tj = _tangent(ei, p), _tangent(ej, q)
                if ti is None or tj is None or abs(seg.dot(ti)) > 0.2 or abs(seg.dot(tj)) > 0.2:
                    continue  # reaching round a corner, not across
            mx, my = (p.x + q.x) / 2, (p.y + q.y) / 2
            (webs if _in(flat, t, mx, my) else gaps).append({"width": round(d, 3), "at": [round(mx, 2), round(my, 2)]})
    return sorted(webs, key=lambda x: x["width"]), sorted(gaps, key=lambda x: x["width"])


def inside_corners(flat, t, wires, radius):
    """Corners a round cutter cannot reach: sharp corners with material
    round more than half of them, and concave arcs tighter than its radius."""
    out = []
    for w in wires:
        es = w.OrderedEdges if hasattr(w, "OrderedEdges") else w.Edges
        for k, e in enumerate(es):
            nx = es[(k + 1) % len(es)]
            p = next((a.Point for a in e.Vertexes for b in nx.Vertexes if a.Point.distanceToPoint(b.Point) < 1e-6), None)
            if p is not None and len(es) > 1:
                ta, tb = _tangent(e, p), _tangent(nx, p)
                if ta is not None and tb is not None and abs(ta.dot(tb)) < math.cos(math.radians(5)):
                    eps = 0.05
                    share = sum(1 for i in range(24) if _in(flat, t, p.x + eps * math.cos(i * math.pi / 12), p.y + eps * math.sin(i * math.pi / 12))) / 24
                    if share > 0.55:
                        out.append({"radius": 0.0, "at": [round(p.x, 2), round(p.y, 2)]})
            if type(e.Curve).__name__ == "Circle" and not e.isClosed() and e.Curve.Radius < radius - 1e-6:
                c = e.Curve.Center
                if not _in(flat, t, c.x, c.y):
                    m = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
                    out.append({"radius": round(e.Curve.Radius, 3), "at": [round(m.x, 2), round(m.y, 2)]})
    return out


def hole_sizes(holes):
    out = []
    for h in holes:
        if len(h.Edges) == 1 and type(h.Edges[0].Curve).__name__ == "Circle":
            c = h.Edges[0].Curve
            out.append({"d": round(2 * c.Radius, 3), "at": [round(c.Location.x, 2), round(c.Location.y, 2)], "round": True})
        else:
            bb = h.BoundBox
            out.append({"d": round(min(bb.XLength, bb.YLength), 3), "at": [round(bb.Center.x, 2), round(bb.Center.y, 2)], "round": False})
    return out


# ---- the tools ----------------------------------------------------------------------------


def cut_setup(s, o):
    setup = store.setup_of(s.doc, o.Label, "cut")
    if not setup:
        raise ToolError("invalid_state", f"{o.Label} is in no cut setup: setup add {{ type: \"cut\", bodies: [\"{o.Label}\"], settings: {{ machine, thickness, kerf }} }} once the person says it is cut from sheet.")
    return setup


def machine_of(s, setup, a, assumed):
    said = a.get("machine") or setup.get("machine") or ""
    if not said:
        m = "laser"
        assumed["machine"] = "laser"
    else:
        m = _cm.machine(said)
        if m is None:
            raise ToolError("invalid_input", _cm.machine_refusal(said))
    said = a.get("material") or setup.get("material") or ""
    if not said:
        mat = "plywood" if m == "router" else "steel"
        assumed["material"] = mat
    else:
        mat = _cm.material(said)
        if mat is None:
            raise ToolError("invalid_input", _cm.material_refusal(said))
    if setup.get("kerf") is not None:
        kerf = float(setup["kerf"])
    else:
        kerf = KERF[m]
        assumed["kerf"] = kerf
    return m, mat, kerf


def sheet_part(s, o):
    info = sheet_of(o.Shape)
    if info["sheet"]:
        return info
    if info.get("why"):
        raise ToolError("invalid_input", f"{o.Label} is not a sheet part: {info['why']}.")
    bits = []
    if info["notSquare"]:
        bits.append(f"faces not square to the sheet: {', '.join(info['notSquare'][:12])}")
    if info["steps"]:
        bits.append(f"flat faces between the two sides (steps or pockets): {', '.join(info['steps'][:12])}")
    return {**info, "problem": "; ".join(bits) or "fewer than two parallel flat faces"}


def cut_check(s, a):
    o = s.body(a.get("body"))
    setup = cut_setup(s, o)
    assumed = {}
    m, mat, kerf = machine_of(s, setup, a, assumed)
    info = sheet_part(s, o)
    findings = []

    def find(rule, severity, value=None, limit=None, at=None, **more):
        findings.append({"rule": rule, "severity": severity, **({"value": value} if value is not None else {}), **({"limit": limit} if limit is not None else {}), **({"at": at} if at else {}), **more})

    if not info["sheet"]:
        find("not-sheet", "error")
        return {"body": o.Label, "verdict": "fix", "machine": m, "findings": findings, "sheet": {k: info[k] for k in ("thickness", "normal", "notSquare", "steps")}}
    t = info["thickness"]
    if setup.get("thickness") is not None and abs(float(setup["thickness"]) - t) > 0.02:
        find("thickness", "error", t, float(setup["thickness"]))
    elif setup.get("thickness") is None:
        assumed["thickness"] = t
    r, floor = rules(m, mat, t, kerf)
    flat, outer, holes = flatten(o.Shape, info)
    for h in hole_sizes(holes):
        if h["d"] < floor["hole"] - 1e-6:
            find("small-hole", "error", h["d"], floor["hole"], h["at"])
        elif h["d"] < r["hole"] - 1e-6:
            find("small-hole", "warning", h["d"], r["hole"], h["at"])
    webs, gaps = narrows(flat, t, [outer] + holes)
    if webs is None:
        assumed["webs"] = {"read": False, "overEdges": MAX_EDGES}
    else:
        for w in webs[:3]:
            if w["width"] < r["web"] - 1e-6:
                find("thin-web", "error" if w["width"] < kerf else "warning", w["width"], r["web"], w["at"])
        for g in gaps[:3]:
            if g["width"] < floor["slot"] - 1e-6:
                find("narrow-slot", "error", g["width"], floor["slot"], g["at"])
            elif g["width"] < r["slot"] - 1e-6:
                find("narrow-slot", "warning", g["width"], r["slot"], g["at"])
    if m == "router":
        for c in inside_corners(flat, t, [outer] + holes, kerf / 2)[:6]:
            find("inside-corner", "warning", c["radius"], round(kerf / 2, 3), c["at"])
    bb = flat.BoundBox
    size = [round(bb.XLength, 2), round(bb.YLength, 2)]
    sheet = a.get("sheet") or setup.get("sheet")  # the cut setup's sheet when none is given
    if sheet:
        sw, sh = float(sheet[0]), float(sheet[1])
        if not ((size[0] <= sw and size[1] <= sh) or (size[0] <= sh and size[1] <= sw)):
            find("sheet-size", "error", max(size), max(sw, sh), size=size, sheet=[sw, sh])
    order = {"error": 0, "warning": 1}
    findings.sort(key=lambda f: order[f["severity"]])
    verdict = "fix" if any(f["severity"] == "error" for f in findings) else ("pass" if not findings else "pass with warnings")
    out = {
        "body": o.Label, "verdict": verdict, "machine": m, "material": mat, "kerf": kerf,
        "sheet": {"thickness": t, "normal": info["normal"]},
        "profile": {"size": size, "holes": len(holes), "edges": sum(len(w.Edges) for w in [outer] + holes), **({"leastWeb": webs[0]["width"]} if webs else {}), **({"leastGap": gaps[0]["width"]} if gaps else {})},
        "least": r, "findings": findings[:10],
        "setup": f"{setup['name']} ({setup['id']})",
    }
    if not sheet:
        out["unjudged"] = [{"what": "sheetSize", "reason": "noSheet"}]
    if assumed:
        out["assumed"] = assumed
    return out


def cut_export(s, a):
    names = a.get("bodies") or ([a["body"]] if a.get("body") else None)
    objs = [s.body(n) for n in names] if names else [s.body(None)]
    copies = a.get("copies", 1)
    setups = {o.Label: cut_setup(s, o) for o in objs}
    first = setups[objs[0].Label]
    kerf = float(first.get("kerf") if first.get("kerf") is not None else KERF.get(_cm.machine(first.get("machine") or "laser") or "laser", 0.2))
    comp = bool(a.get("compensate", False))
    gap = float(a.get("gap", max(3.0, 2 * kerf)))
    sheet = a.get("sheet") or first.get("sheet")  # the cut setup's sheet when none is given
    parts = []
    thick = None
    for o in objs:
        info = sheet_part(s, o)
        if not info["sheet"]:
            raise ToolError("invalid_input", f"{o.Label} is not a sheet part — {info['problem']}: cut_check says more.")
        if thick is not None and abs(info["thickness"] - thick) > 0.02:
            raise ToolError("invalid_input", f"{o.Label} is {info['thickness']:g} mm, the others {thick:g} mm: one sheet per file — export them apart.")
        thick = info["thickness"]
        flat, outer, holes = flatten(o.Shape, info)
        loops = [[p for _, p in primitives(w, None)] for w in [outer] + holes]
        if comp:
            # Each loop moved off the material by half the kerf: the
            # outside out, the holes in.
            try:
                loops = [sf.offset_loop(loops[0], kerf / 2)] + [sf.offset_loop(h, -kerf / 2) for h in loops[1:]]
            except ValueError as e:
                raise ToolError("failed", f"The kerf offset on {o.Label}: {e} — export with compensate: false and let the cutter's software take off the kerf.")
        prims = [(sf.OUTER, p) for p in loops[0]] + [(sf.HOLES, p) for h in loops[1:] for p in h]
        bb = sf.bbox(loops[0])
        n = int(copies.get(o.Label, 1)) if isinstance(copies, dict) else int(copies)
        if n < 1 or n > 500:
            raise ToolError("invalid_input", "copies: 1 to 500 (a number, or { body: n }).")
        try:
            face = Part.Face(Part.Wire(outer.Edges)) if not holes else Part.Face([Part.Wire(w.Edges) for w in [outer] + holes])
            face.translate(V(0, 0, -face.BoundBox.ZMin))  # on the sheet's plane
        except Exception:  # noqa: BLE001 — no face for BIM Nest: the rows take it
            face = None
        for _ in range(n):
            # A face of its own a copy: BIM Nest keys pieces by hashCode.
            parts.append((o.Label, prims, bb, face.copy() if face is not None else None))
    sw, sh = (float(sheet[0]), float(sheet[1])) if sheet else (None, None)
    # Laid out by FreeCAD's BIM Nest where it is here and there is a sheet
    # to nest in; else in rows, and the answer says which.
    at, layout = None, None
    if not a.get("nest", True):
        layout = "rows (nest: false)"
    elif not sheet:
        layout = "rows: give sheet [w, h], or set the cut setup's sheet, for BIM Nest to nest in"
    elif any(p[3] is None for p in parts):
        layout = "rows: a profile could not be made a face for BIM Nest"
    elif not _window_up():
        # BIM Nest stopped headless FreeCAD 1.1.3 (Linux CI, exit 139, in
        # cut_export); with the window it works (live, Mac, 19 Nov 2026).
        layout = "rows: BIM Nest runs with the FreeCAD window only"
    else:
        moves, why = bimnest.nest([p[3] for p in parts], sw, sh, gap)
        if moves is None:
            layout = f"rows: {why}"
        else:
            at = [None if m is None else (bb[0] + m[0], bb[1] + m[1]) for (_, _, bb, _), m in zip(parts, moves)]
            layout = "FreeCAD's BIM Nest"
    if at is None:
        at = sf.shelf([(bb[2] - bb[0], bb[3] - bb[1]) for _, _, bb, _ in parts], sw, sh, gap)
    parts = [p[:3] for p in parts]
    items, placed, left = [], {}, {}
    for (label, prims, bb), pos in zip(parts, at):
        if pos is None:
            left[label] = left.get(label, 0) + 1
            continue
        dx, dy = pos[0] - bb[0], pos[1] - bb[1]
        items += [(layer, sf.shift(p, dx, dy)) for layer, p in prims]
        placed[label] = placed.get(label, 0) + 1
    if not items:
        raise ToolError("invalid_input", f"Nothing fits the {sw:g} x {sh:g} mm sheet with a {gap:g} mm gap: a bigger sheet, or split the part.")
    if sheet:
        W, H = sw, sh
    else:
        W = max(pos[0] + bb[2] - bb[0] for (_, _, bb), pos in zip(parts, at) if pos) + gap
        H = max(pos[1] + bb[3] - bb[1] for (_, _, bb), pos in zip(parts, at) if pos) + gap
    base = os.path.join(s.out_dir, a.get("name") or (objs[0].Label.replace(" ", "_") + "-cut"))
    os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
    wrote = {}
    want = {}
    for _, p in items:
        k = {"line": "LINE", "arc": "ARC", "circle": "CIRCLE", "poly": "POLYLINE"}[p[0]]
        want[k] = want.get(k, 0) + 1
    fmts = [f.lower() for f in (a.get("formats") or ["dxf", "svg"])]
    for f in fmts:
        if f not in ("dxf", "svg"):
            raise ToolError("invalid_input", "formats: dxf and/or svg.")
    if "dxf" in fmts:
        p = base + ".dxf"
        with open(p, "w", encoding="ascii", newline="\r\n") as fh:
            fh.write(sf.dxf(items, (0, 0, W, H)))
        with open(p, encoding="ascii") as fh:
            back = sf.read_dxf(fh.read())
        wrote["dxf"] = {"path": p, "bytes": os.path.getsize(p), "readBack": back["entities"], "layers": back["layers"], "matches": back["entities"] == want}
    if "svg" in fmts:
        p = base + ".svg"
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(sf.svg(items, W, H))
        with open(p, encoding="utf-8") as fh:
            back = sf.read_svg(fh.read())
        wrote["svg"] = {"path": p, "bytes": os.path.getsize(p), "readBack": {k: v for k, v in back.items() if v}}
    out = {"files": wrote, "placed": placed, "sheet": [round(W, 2), round(H, 2)], "thickness": thick, "kerf": kerf, "compensated": comp, "gap": gap, "entities": want,
           "layout": layout}
    if left:
        out["left"] = {"bodies": left}
    return out


def tube_of(o):
    """A straight round tube body as a cut-list member: its axis (the
    largest cylindrical face's), outside and inside diameters (the largest
    and least radius of the faces on that axis), and its centre line between
    the farthest points of the body along the axis. A tube modelled node to
    node (a plain pipe, not yet coped) gives the node points."""
    sh = o.Shape
    cyl = []
    for f in sh.Faces:
        srf = f.Surface
        if "Cylinder" in type(srf).__name__ or getattr(srf, "TypeId", "") == "Part::GeomCylinder":
            cyl.append((f.Area, srf))
    if not cyl:
        raise ToolError("invalid_input", f"{o.Label}: no round face; a tube body is a straight round pipe (PartDesign pipe or pad of a ring). Give members instead.")
    big = max(cyl, key=lambda x: x[0])[1]
    ax = big.Axis.normalize() if hasattr(big.Axis, "normalize") else big.Axis
    c0 = big.Center
    radii = []
    for _, srf in cyl:
        d = srf.Axis
        cross = d.cross(ax)
        off = (srf.Center - c0).cross(ax)
        if cross.Length < 1e-6 and off.Length < 1e-3:
            radii.append(srf.Radius)
    od, idia = 2 * max(radii), 2 * min(radii)
    if idia >= od - 1e-6:
        raise ToolError("invalid_input", f"{o.Label}: one round face only on its axis (a rod, not a tube); give members with wall for it.")
    ts = [(v.Point - c0).dot(ax) for v in sh.Vertexes]
    t0, t1 = min(ts), max(ts)
    p0, p1 = c0 + ax * t0, c0 + ax * t1
    return {"name": o.Label, "from": [p0.x, p0.y, p0.z], "to": [p1.x, p1.y, p1.z], "od": round(od, 3), "wall": round((od - idia) / 2, 3)}


def tube_cutlist(s, a):
    from .. import tubecut as TC

    members = list(a.get("members") or [])
    for ref in a.get("bodies") or []:
        members.append(tube_of(s.body(ref)))
    if not members:
        raise ToolError("invalid_input", "members [{ name, from, to, od, wall }] or bodies (straight round tube bodies): the tubes of the weldment.")
    ends = a.get("ends") or {}
    if ends:
        if not isinstance(ends, dict):
            raise ToolError("invalid_input", "ends: { tube name: { from, to } }, each the tube it meets or \"square\".")
        for m in members:
            if m.get("name") in ends:
                m["ends"] = {**(m.get("ends") or {}), **ends[m["name"]]}
    try:
        tol = float(a.get("tol", 1.0))
        rows, warnings = TC.cut_list(members, tol=tol)
    except (TC.CutError, TypeError, ValueError) as e:
        raise ToolError("invalid_input", str(e))
    base = os.path.join(s.out_dir, a.get("name") or "tube-cut-list")
    os.makedirs(os.path.dirname(base) or ".", exist_ok=True)
    with open(base + ".md", "w", encoding="utf-8") as fh:
        fh.write(TC.markdown(rows, a.get("title") or "Tube cut list", warnings))
    with open(base + ".csv", "w", encoding="utf-8", newline="") as fh:
        fh.write(TC.csv_text(rows))
    stock = {}
    for r in rows:
        k = f"{r['od']:g} x {r['wall']:g}"
        stock[k] = round(stock.get(k, 0) + r["cutLength"], 1)
    out = {"tubes": rows, "stock": stock, "files": {"markdown": base + ".md", "csv": base + ".csv"}}
    if warnings:
        out["warnings"] = warnings
    return out


HANDLERS = {
    "cut_check": cut_check,
    "cut_export": cut_export,
    "tube_cutlist": tube_cutlist,
}
