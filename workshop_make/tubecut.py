# SPDX-License-Identifier: LGPL-2.1-or-later
"""A cut list for a weldment of round tubes: each tube's centre-line
length, the length to cut from stock (between its long points), and each
coped (fish-mouthed) end's cope against the tube it meets: the included
angle, the notcher's angle, how deep the cope is, and the phase angle
between the two copes of one tube (the turn about the tube's own axis from
one cope to the other). Members meet where an end lies on another tube
(within its outside radius plus tol), or as each end says. Plain Python, no
FreeCAD.

A member: {name, from: [x, y, z], to: [x, y, z], od, wall, ends?: {from, to}}
mm; an end's value is the name of the tube it meets, or "square" (a plain
cut)."""

import csv
import io
import math

STEPS = 720  # points around the tube where the cope is found


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _add(a, b):
    return [a[i] + b[i] for i in range(3)]


def _mul(a, k):
    return [x * k for x in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    return [x / n for x in a]


class CutError(ValueError):
    pass


def check(members):
    """The members, checked and made plain: [{name, p0, p1, od, wall, ends}]."""
    if not isinstance(members, list) or not members:
        raise CutError("members: a list of tubes { name, from, to, od, wall }.")
    out, seen = [], set()
    for k, m in enumerate(members):
        if not isinstance(m, dict):
            raise CutError(f"members[{k}]: {{ name, from, to, od, wall }}.")
        name = str(m.get("name") or f"T{k + 1}")
        if name in seen:
            raise CutError(f"members[{k}].name {name!r}: each tube needs its own name.")
        seen.add(name)
        pts = []
        for end in ("from", "to"):
            v = m.get(end)
            if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
                raise CutError(f"members[{k}].{end}: [x, y, z] mm, a point on the centre line.")
            pts.append([float(x) for x in v])
        try:
            od, wall = float(m.get("od")), float(m.get("wall"))
        except (TypeError, ValueError):
            raise CutError(f"members[{k}] ({name}): od and wall in mm.")
        if not (od > 0 and 0 < wall < od / 2):
            raise CutError(f"members[{k}] ({name}): od over 0, and wall over 0 and under od / 2.")
        if _len(_sub(pts[1], pts[0])) < 1e-6:
            raise CutError(f"members[{k}] ({name}): from and to are the same point.")
        ends = m.get("ends") or {}
        if not isinstance(ends, dict) or any(e not in ("from", "to") for e in ends):
            raise CutError(f"members[{k}].ends: {{ from, to }}, each the name of the tube it meets or \"square\".")
        out.append({"name": name, "p0": pts[0], "p1": pts[1], "od": od, "wall": wall, "ends": dict(ends)})
    names = {m["name"] for m in out}
    for m in out:
        for e, v in m["ends"].items():
            if v != "square" and v not in names:
                raise CutError(f"{m['name']}.ends.{e} {v!r}: the name of another tube, or \"square\".")
            if v == m["name"]:
                raise CutError(f"{m['name']}.ends.{e}: a tube cannot meet itself.")
    return out


def _seg_dist(p, a, b):
    """(distance from p to segment ab, where along it 0..1)."""
    d = _sub(b, a)
    t = max(0.0, min(1.0, _dot(_sub(p, a), d) / _dot(d, d)))
    return _len(_sub(p, _add(a, _mul(d, t)))), t


def receiver(m, end, members, tol):
    """The tube an end of m meets, or None (a square cut). Said by the end,
    else the tube whose centre line passes within its outside radius plus
    tol of the end point: one the end lies along wins over one whose end it
    shares; then the larger tube; then the first listed."""
    said = m["ends"].get(end)
    if said == "square":
        return None
    if said:
        return next(x for x in members if x["name"] == said)
    p = m["p0"] if end == "from" else m["p1"]
    best = None
    for x in members:
        if x is m:
            continue
        d, t = _seg_dist(p, x["p0"], x["p1"])
        if d > x["od"] / 2 + tol:
            continue
        # A tube met at its own end, by a tube no smaller, takes the cope itself.
        at_end = t < 1e-6 or t > 1 - 1e-6
        if at_end and x["od"] < m["od"] - 1e-9:
            continue
        if at_end and abs(x["od"] - m["od"]) <= 1e-9 and members.index(x) > members.index(m):
            continue
        key = (at_end, -x["od"], members.index(x))
        if best is None or key < best[0]:
            best = (key, x)
    return best[1] if best else None


def cope(node, into, r, recv):
    """The cope of a tube end at node, running along into (unit), outside
    radius r, on the tube recv. Returns {tMin, tMax, angle, ref, full}: how
    far along the tube from node its cut surface starts at the long point
    (tMin) and at the short point (tMax), the included angle (degrees), the
    reference direction of the cope about the tube's axis (unit, square to
    into), and whether every line along the tube meets recv."""
    a0, a = recv["p0"], _unit(_sub(recv["p1"], recv["p0"]))
    R = recv["od"] / 2
    ca = _dot(into, a)
    theta = math.degrees(math.acos(min(1.0, abs(ca))))
    # Two directions square to the tube's axis: n1 in the plane of the two
    # axes (towards the receiving tube's axis turned), n2 square to both.
    side = _sub(a, _mul(into, ca))
    if _len(side) < 1e-9:
        raise CutError("a tube along the tube it meets has no cope: give that end \"square\".")
    a_side = a if ca >= 0 else _mul(a, -1)
    n1 = _unit(_sub(a_side, _mul(into, _dot(a_side, into))))
    n2 = _cross(into, n1)
    A = 1 - ca * ca
    ts, full = [], True
    for k in range(STEPS):
        ph = 2 * math.pi * k / STEPS
        c = _add(_mul(n1, r * math.cos(ph)), _mul(n2, r * math.sin(ph)))
        q = _add(_sub(node, a0), c)
        qa = _dot(q, a)
        B = 2 * (_dot(q, into) - qa * ca)
        C = _dot(q, q) - qa * qa - R * R
        disc = B * B - 4 * A * C
        if disc < 0:
            full = False
            continue
        ts.append((-B + math.sqrt(disc)) / (2 * A))
    if not ts:
        raise CutError("the tube misses the tube it meets (its end is off that tube's axis by more than both radii).")
    return {"tMin": min(ts), "tMax": max(ts), "angle": theta, "ref": n1, "full": full and r <= R + 1e-9}


def _phase(u, v, axis):
    """The turn from u to v about axis, 0 to 180 degrees (a cope's way round is the same both ways)."""
    x = _dot(u, v)
    y = _dot(_cross(u, v), axis)
    return abs(math.degrees(math.atan2(y, x)))


def cut_list(members, tol=1.0):
    """Each tube's row of the cut list (see the module's text) and the
    warnings."""
    ms = check(members)
    rows, warn = [], []
    for m in ms:
        L = _len(_sub(m["p1"], m["p0"]))
        ax = _unit(_sub(m["p1"], m["p0"]))
        r = m["od"] / 2
        row = {"name": m["name"], "od": m["od"], "wall": m["wall"], "centreLength": round(L, 1)}
        cuts, refs = {}, {}
        for end, node, into in (("from", m["p0"], ax), ("to", m["p1"], _mul(ax, -1))):
            x = receiver(m, end, ms, tol)
            if x is None:
                cuts[end] = {"meets": None, "cut": "square", "trim": 0.0}
                continue
            try:
                c = cope(node, into, r, x)
            except CutError as e:
                raise CutError(f"{m['name']} {end} end on {x['name']}: {e}")
            if not c["full"]:
                warn.append(f"{m['name']} {end} end: wider than {x['name']} or off its axis; part of the end does not meet it (check the joint).")
            cuts[end] = {"meets": x["name"], "meetsOd": x["od"], "cut": "cope", "includedAngle": round(c["angle"], 1),
                         "notcherAngle": round(90 - c["angle"], 1), "copeDepth": round(c["tMax"] - c["tMin"], 1), "trim": c["tMin"]}
            refs[end] = c["ref"]
        cut_len = L - cuts["from"]["trim"] - cuts["to"]["trim"]
        if cut_len <= 0:
            raise CutError(f"{m['name']}: nothing is left after its copes ({L:.1f} mm between the axes it meets): check from and to.")
        row["cutLength"] = round(cut_len, 1)
        for end in ("from", "to"):
            c = cuts[end]
            c["trim"] = round(c["trim"], 1)
            row[end] = c
        if len(refs) == 2:
            row["phase"] = round(_phase(refs["from"], refs["to"], ax), 1)
        rows.append(row)
    return rows, warn


def _end_text(c):
    if c["cut"] == "square":
        return "square"
    return f"cope on {c['meets']} (OD {c['meetsOd']:g}) at {c['includedAngle']:g}° (notcher {c['notcherAngle']:g}°), {c['copeDepth']:g} deep"


def markdown(rows, title="Tube cut list", warnings=()):
    out = [f"# {title}", "", "Lengths in mm. Cut length: between the long points of the copes. "
           "Phase: the turn of the to-end cope from the from-end cope about the tube's axis. "
           "Notcher angle: 0 for a tube square to the one it meets.", "",
           "| Tube | OD | Wall | Centre line | Cut length | From end | To end | Phase |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['name']} | {r['od']:g} | {r['wall']:g} | {r['centreLength']:g} | {r['cutLength']:g} | {_end_text(r['from'])} | {_end_text(r['to'])} | "
                   + (f"{r['phase']:g}°" if "phase" in r else "—") + " |")
    if warnings:
        out += ["", "Warnings:", ""] + [f"- {w}" for w in warnings]
    return "\n".join(out) + "\n"


CSV_COLUMNS = ("tube", "od_mm", "wall_mm", "centre_length_mm", "cut_length_mm", "from_meets", "from_included_deg", "from_notcher_deg",
               "from_cope_depth_mm", "to_meets", "to_included_deg", "to_notcher_deg", "to_cope_depth_mm", "phase_deg")


def csv_text(rows):
    f = io.StringIO()
    w = csv.writer(f, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in rows:
        line = [r["name"], r["od"], r["wall"], r["centreLength"], r["cutLength"]]
        for end in ("from", "to"):
            c = r[end]
            line += [c.get("meets") or "square", c.get("includedAngle", ""), c.get("notcherAngle", ""), c.get("copeDepth", "")]
        line.append(r.get("phase", ""))
        w.writerow(line)
    return f.getvalue()
