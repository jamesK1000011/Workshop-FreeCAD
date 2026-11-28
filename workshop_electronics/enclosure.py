# SPDX-License-Identifier: LGPL-2.1-or-later
# The enclosure round a board: standoffs under its mounting holes, openings
# for its connectors, a lid. Electronics' own copy of the board box Workshop
# Parts also makes (Parts' boxes.py), so Electronics installs alone.
import FreeCAD
import Part  # noqa: F401

from . import geo as g

V = FreeCAD.Vector
EPS = 0.01

# Bosses and standoffs for self-tapping screws into printed plastic:
# (outer diameter, pilot hole as modelled before calibration).
BOSS = {"M2": (5.0, 1.6), "M2.5": (6.0, 2.1), "M3": (7.0, 2.5), "M4": (9.0, 3.3)}
# Clearance holes (close, normal, loose), mm: ISO 273.
CLEAR = {"M2": (2.2, 2.4, 2.6), "M2.5": (2.7, 2.9, 3.1), "M3": (3.2, 3.4, 3.6), "M4": (4.3, 4.5, 4.8)}


def check(table, given):
    """The parameters, defaults filled in, each checked: a ValueError names
    the first one wrong and what it takes."""
    unknown = sorted(set(given) - set(table))
    if unknown:
        raise ValueError(f"params: {', '.join(unknown)} not known — the keys: {', '.join(table)}.")
    out = {}
    for k, spec in table.items():
        v = given.get(k, spec.get("default"))
        kind = spec["kind"]
        if v is None and spec.get("optional"):
            out[k] = None
            continue
        if kind == "bool":
            if not isinstance(v, bool):
                raise ValueError(f"{k}: true or false.")
        elif kind == "enum":
            if v not in spec["values"]:
                raise ValueError(f"{k}: one of {', '.join(spec['values'])}.")
        elif kind in ("int", "num"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(f"{k}: a number, {spec['min']} to {spec['max']}.")
            if kind == "int" and int(v) != v:
                raise ValueError(f"{k}: a whole number, {spec['min']} to {spec['max']}.")
            if not (spec["min"] <= v <= spec["max"]):
                raise ValueError(f"{k}: {spec['min']} to {spec['max']}, not {v}.")
        elif kind == "points":
            if not isinstance(v, list) or not all(isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(c, (int, float)) for c in p) for p in v):
                raise ValueError(f"{k}: a list of [x, y] points, mm.")
        elif kind == "list":
            if not isinstance(v, list):
                raise ValueError(f"{k}: a list.")
        out[k] = v
    return out



def lid_shape(L, D, r, w, lid, lip, cl, notches=(), holes=(), at=(0.0, 0.0)):
    """A lid laid top down beside the box: a plate L x D x lid and a lip
    ring standing up from it that goes into the box at cl all round.
    notches: [(x, y, radius)] cut from the lip round corner bosses: square,
    from radius beyond the boss out past the corner;
    holes: [(x, y, diameter)] through the plate. Both in the box's own
    X and Y: the lid turns over about X to go on, so y is mirrored here."""
    ax, ay = at
    plate = g.prism(ax, ay, L, D, r, 0, lid)
    parts = [plate]
    if lip > 0:
        t = min(1.6, w)
        ow, od = L - 2 * w - 2 * cl, D - 2 * w - 2 * cl
        ro = max(0.0, r - w - cl)
        ring = g.prism(ax, ay, ow, od, ro, lid - 0.5, lid + lip)
        ring = ring.cut(g.prism(ax, ay, ow - 2 * t, od - 2 * t, max(0.0, ro - t), lid - 0.5 - EPS, lid + lip + EPS))
        # A round notch crossed the lip at a slant and left a wedge 0.7 mm
        # thin at each end. The lip is cut square instead: from the far side
        # of the boss (radius rad) out past the corner, so its ends stand
        # straight across and the boss still clears by rad.
        h = lip + 0.5 + 2 * EPS
        cuts = []
        for (x, y, rad) in notches:
            sx, sy = (1 if x >= 0 else -1), (1 if y >= 0 else -1)
            x0, x1 = sorted((x - sx * rad, sx * (L / 2 + 1)))
            y0, y1 = sorted((y - sy * rad, sy * (D / 2 + 1)))
            cuts.append(g.prism(ax + (x0 + x1) / 2, ay - (y0 + y1) / 2, x1 - x0, y1 - y0, 0, lid - 0.5 - EPS, lid - 0.5 - EPS + h))
        ring = g.cut_all(ring, cuts)
        parts.append(ring)
    shape = g.fuse_all(parts)
    if holes:
        shape = g.cut_all(shape, [g.cylinder(dia / 2.0, lid + 2 * EPS, ax + x, ay - y, -EPS) for (x, y, dia) in holes])
    return shape



def _screw(name, cal):
    if name not in BOSS:
        raise ValueError(f"screw: one of {', '.join(BOSS)}.")
    boss, pilot = BOSS[name]
    clear = CLEAR[name][1] + cal["hole"]
    return boss, pilot + cal["hole"], clear


BOARD_BOX = {
    "board": {"kind": "list", "default": [50.0, 30.0], "tip": "The board's size [x, y], mm; board coordinates start at its lower-left corner."},
    "thickness": {"kind": "num", "min": 0.4, "max": 4, "default": 1.6, "tip": "The board, mm."},
    "holes": {"kind": "points", "default": [], "tip": "Mounting holes [[x, y] …] in board coordinates: a standoff under each."},
    "screw": {"kind": "enum", "values": list(BOSS), "default": "M3", "tip": "The screws through the board's holes."},
    "standoff": {"kind": "num", "min": 1, "max": 40, "default": 5, "tip": "Floor to the board's underside, mm."},
    "headroom": {"kind": "num", "min": 1, "max": 150, "default": 15, "tip": "The board's top to the rim, mm: the tallest part, and a margin."},
    "gap": {"kind": "num", "min": 0.2, "max": 20, "default": 1.0, "tip": "The board's edge to the walls, mm."},
    "wall": {"kind": "num", "min": 1.2, "max": 6, "default": 2.0, "tip": "Walls, mm."},
    "floor": {"kind": "num", "min": 0.8, "max": 6, "default": 2.0, "tip": "Floor, mm."},
    "radius": {"kind": "num", "min": 0, "max": 20, "default": 2.0, "tip": "Outside corner radius, mm."},
    "lid": {"kind": "num", "min": 0.8, "max": 6, "default": 2.0, "tip": "The lid's plate, mm."},
    "lip": {"kind": "num", "min": 0, "max": 15, "default": 2.0, "tip": "How far the lid's lip goes in, mm; 0 for a flat lid."},
    "clearance": {"kind": "num", "min": 0.05, "max": 1, "default": 0.2, "tip": "Lip to walls, each side, mm."},
    "openings": {"kind": "list", "default": [], "tip": "Openings for edge connectors: [{ side: front|back|left|right, at: from the board's corner along that side (x for front/back, y for left/right) to the connector's middle, width, height, z: its bottom over the board's top (0) }], mm."},
    "margin": {"kind": "num", "min": 0, "max": 3, "default": 0.5, "tip": "Added round each opening, mm."},
    "gapLid": {"kind": "num", "min": 2, "max": 50, "default": 10, "tip": "Between the box and the lid laid beside it, mm."},
}

SIDES = ("front", "back", "left", "right")


def board_box(p, cal):
    """(box, lid, what they are): the box centred on the origin, floor on
    z = 0; boardAt is where the board's lower-left underside corner sits."""
    try:
        bw, bd = (float(v) for v in p["board"])
    except (TypeError, ValueError):
        raise ValueError("board: [x, y], the board's size, mm.")
    if not (5 <= bw <= 400 and 5 <= bd <= 400):
        raise ValueError("board: each side 5 to 400 mm.")
    w, fl, r, gap = p["wall"], p["floor"], p["radius"], p["gap"]
    iw, idp = bw + 2 * gap, bd + 2 * gap
    L, D = iw + 2 * w, idp + 2 * w
    zb = fl + p["standoff"]  # the board's underside
    zt = zb + p["thickness"]
    H = zt + p["headroom"]
    if p["lip"] > p["headroom"] - 0.5:
        raise ValueError(f"lip: at most {p['headroom'] - 0.5:.1f} mm, so it stays clear of the board — or more headroom.")
    if r >= min(L, D) / 2 - 1:
        raise ValueError(f"radius: under {min(L, D) / 2 - 1:.1f} mm for a box this size.")
    r_in = max(0.0, r - w)
    x0, y0 = -bw / 2.0, -bd / 2.0  # the board's corner in the box
    box = g.cut_all(g.prism(0, 0, L, D, r, 0, H), [g.prism(0, 0, iw, idp, r_in, fl, H + EPS)])
    info = {"outside": [round(L, 3), round(D, 3), round(H, 3)], "inside": [round(iw, 3), round(idp, 3), round(H - fl, 3)], "boardAt": [round(x0, 3), round(y0, 3), round(zb, 3)]}

    adds, cuts = [], []
    if p["holes"]:
        bdia, pilot, _ = _screw(p["screw"], cal)
        rad = bdia / 2.0
        depth = min(p["standoff"] + fl - 0.8, 3.5 * float(p["screw"][1:]))
        made = []
        for (hx, hy) in p["holes"]:
            if not (0 <= hx <= bw and 0 <= hy <= bd):
                raise ValueError(f"holes: [{hx}, {hy}] is off the board (0..{bw}, 0..{bd}).")
            x, y = x0 + hx, y0 + hy
            # A standoff that only just reaches a wall would meet it on a
            # tangent: shrink it a little instead.
            near = min(x - (-iw / 2), iw / 2 - x, y - (-idp / 2), idp / 2 - y)
            if rad - near > w - 0.8:
                raise ValueError(f"holes: [{hx}, {hy}] is so near the edge its standoff would come through the wall — gap {rad - near - w + 0.8 + gap:.1f} mm or more.")
            rr = rad - 0.1 if abs(near - rad) < 0.1 else rad
            adds.append(g.cylinder(rr, p["standoff"] + 0.5, x, y, fl - 0.5))
            cuts.append(g.cylinder(pilot / 2.0, depth + EPS, x, y, zb - depth))
            made.append([round(x, 3), round(y, 3)])
        info["standoffs"] = {"screw": p["screw"], "at": made, "diameter": bdia, "pilot": round(pilot, 3), "pilotDepth": round(depth, 3)}
    if adds:
        box = g.fuse_all([box] + adds)

    opened = []
    m = p["margin"]
    for i, o in enumerate(p["openings"]):
        if not isinstance(o, dict) or o.get("side") not in SIDES:
            raise ValueError(f"openings.{i}.side: one of {', '.join(SIDES)}.")
        try:
            at, wd, ht, z = float(o["at"]), float(o["width"]), float(o["height"]), float(o.get("z", 0))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"openings.{i}: at, width and height, mm (z optional).")
        if wd <= 0 or ht <= 0:
            raise ValueError(f"openings.{i}: width and height above 0.")
        z0 = zt + z - m
        z1 = zt + z + ht + m
        if z0 < fl + 0.4:
            raise ValueError(f"openings.{i}: its bottom is {z0 - fl:.1f} mm over the floor — a taller standoff, or z higher.")
        if z1 > H - 0.8:
            z1 = H + 1  # into the rim: a notch open at the top
        side = o["side"]
        if side in ("front", "back"):
            c = x0 + at
            lo, hi = c - wd / 2 - m, c + wd / 2 + m
            if lo < -iw / 2 + 0.4 or hi > iw / 2 - 0.4:
                raise ValueError(f"openings.{i}: runs into the corner — at and width keep it inside the {side} wall.")
            ys = (-D / 2 - 1, -idp / 2 + 1) if side == "front" else (idp / 2 - 1, D / 2 + 1)
            cuts.append(Part.makeBox(hi - lo, ys[1] - ys[0], z1 - z0, V(lo, ys[0], z0)))
        else:
            c = y0 + at
            lo, hi = c - wd / 2 - m, c + wd / 2 + m
            if lo < -idp / 2 + 0.4 or hi > idp / 2 - 0.4:
                raise ValueError(f"openings.{i}: runs into the corner — at and width keep it inside the {side} wall.")
            xs = (-L / 2 - 1, -iw / 2 + 1) if side == "left" else (iw / 2 - 1, L / 2 + 1)
            cuts.append(Part.makeBox(xs[1] - xs[0], hi - lo, z1 - z0, V(xs[0], lo, z0)))
        opened.append({"side": side, "from": round(lo, 3), "to": round(hi, 3), "z": [round(z0, 3), round(min(z1, H), 3)], **({"openAtRim": True} if z1 > H else {})})
    if cuts:
        box = g.cut_all(box, cuts)
    if opened:
        info["openings"] = opened
    lid = lid_shape(L, D, r, w, p["lid"], p["lip"], p["clearance"], at=(L + p["gapLid"], 0.0))
    info["lid"] = {"plate": p["lid"], "lip": p["lip"], "clearance": p["clearance"], "at": [round(L + p["gapLid"], 3), 0.0]}
    return box, lid, info
