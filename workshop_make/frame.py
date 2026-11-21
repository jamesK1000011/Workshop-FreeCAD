# SPDX-License-Identifier: LGPL-2.1-or-later
# A frame of straight members — beams, columns, braces, rafters, a truss —
# solved with CalculiX's three-node beam elements (B32, expanded into
# solids by CalculiX): members joined where their ends meet, supports pinned,
# fixed or on rollers, loads along members (N/mm), at joints (N), and the
# members' own weight. Answers each member's peak stress along it and von
# Mises, its largest deflection relative to its ends and overall, and the
# reaction at each support. Pure Python with the ccx binary; no FreeCAD.

import math
import os
import subprocess

from workshop_make import ccx as ccx_io

SECTIONS = ("rect", "circ", "pipe", "box")


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return [x / n for x in a]


# What each section kind takes (mm): d is always a diameter or a depth, never a radius.
SECTION_KEYS = {"rect": ("b", "d"), "circ": ("d",), "pipe": ("d", "t"), "box": ("b", "d", "t")}


def section_check(sec, where="section"):
    """A section's sizes, checked: each kind's own keys, all over 0 mm, a
    wall less than half the size. A radius (r, radius) is refused: d is the
    diameter (bicycle runs, 21 Nov: a "circ section half-size trap")."""
    k = sec.get("kind", "rect")
    if k not in SECTION_KEYS:
        raise ValueError(f"{where}.kind: {', '.join(SECTIONS)}")
    if any(x in sec for x in ("r", "radius", "ro", "ri")):
        raise ValueError(f"{where}: {k} takes d, the outside diameter in mm, not a radius (r).")
    out = {}
    for key in SECTION_KEYS[k]:
        v = sec.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ValueError(f"{where}.{key}: mm, more than 0 ({k}: {', '.join(SECTION_KEYS[k])}; d is a diameter or a depth).")
        out[key] = float(v)
    if k == "pipe" and 2 * out["t"] >= out["d"]:
        raise ValueError(f"{where}.t: less than half of d ({out['d'] / 2:g} mm): a pipe's wall; circ is a solid round.")
    if k == "box" and 2 * out["t"] >= min(out["b"], out["d"]):
        raise ValueError(f"{where}.t: less than half of the smaller of b and d: a box's wall; rect is a solid bar.")
    return out


def section_props(sec):
    """(area mm², I about the strong axis mm⁴, c the distance to the extreme
    fibre mm, ccx's section lines). CalculiX's lines as FreeCAD's own writer
    gives them (femsolver/calculix/write_femelement_geometry.py, 1.1): RECT
    the two sizes, CIRC the diameters (not the radius: the circle was made
    half size before 21 Nov), PIPE the outer radius and the wall, BOX the
    two sizes and the four walls."""
    k = sec.get("kind", "rect")
    z = section_check(sec)
    if k == "rect":
        b, d = z["b"], z["d"]
        return b * d, b * d ** 3 / 12, d / 2, ("RECT", f"{b:.6g}, {d:.6g}")
    if k == "circ":
        d = z["d"]
        r = d / 2
        return math.pi * r * r, math.pi * r ** 4 / 4, r, ("CIRC", f"{d:.6g}, {d:.6g}")
    if k == "pipe":
        d, t = z["d"], z["t"]
        ro, ri = d / 2, d / 2 - t
        return math.pi * (ro * ro - ri * ri), math.pi * (ro ** 4 - ri ** 4) / 4, ro, ("PIPE", f"{ro:.6g}, {t:.6g}")
    if k == "box":
        b, d, t = z["b"], z["d"], z["t"]
        I = (b * d ** 3 - (b - 2 * t) * (d - 2 * t) ** 3) / 12
        return b * d - (b - 2 * t) * (d - 2 * t), I, d / 2, ("BOX", f"{b:.6g}, {d:.6g}, {t:.6g}, {t:.6g}, {t:.6g}, {t:.6g}")
    raise ValueError(f"section kind: {', '.join(SECTIONS)}")


def orient(t):
    """The section's 1-direction for a member along t: horizontal across a
    sloped or level member (its depth then stands upright), x for a column."""
    up = [0.0, 0.0, 1.0]
    c = _cross(up, t)
    if _norm(c) < 1e-6:
        return [1.0, 0.0, 0.0]
    return _unit(c)


def build(members, supports, loads, gravity=None, n=8, tol=1.0):
    """The input deck and the bookkeeping to read it: members [{name, from,
    to, section {kind …}, E, nu, rho (kg/m³)}], supports [{at, kind pinned
    | fixed | roller}], loads [{member, w [wx,wy,wz] N/mm} | {at, force
    [fx,fy,fz] N}], gravity [gx,gy,gz] mm/s² or None."""
    joints = []

    def joint(p):
        for i, q in enumerate(joints):
            if _norm(_sub(p, q)) <= tol:
                return i
        joints.append(list(p))
        return len(joints) - 1

    node_xyz = {}
    nid = [0]

    def new_node(p):
        nid[0] += 1
        node_xyz[nid[0]] = p
        return nid[0]

    jnode = {}
    mem = []
    eid = 0
    lines_el, lines_sec, loads_c = [], [], {}
    mats = {}
    for k, m in enumerate(members):
        a, b = [float(x) for x in m["from"]], [float(x) for x in m["to"]]
        L = _norm(_sub(b, a))
        if L < tol:
            raise ValueError(f"member {m.get('name', k)}: its ends are the same point")
        ja, jb = joint(a), joint(b)
        for j, p in ((ja, a), (jb, b)):
            if j not in jnode:
                jnode[j] = new_node(joints[j])
        t = _unit(_sub(b, a))
        ids = [jnode[ja]]
        for i in range(1, 2 * n):
            ids.append(new_node([a[c] + t[c] * L * i / (2 * n) for c in range(3)]))
        ids.append(jnode[jb])
        A, I, cmax, (stype, sline) = section_props(m["section"])
        es = []
        for e in range(n):
            eid += 1
            es.append(eid)
            lines_el.append(f"{eid}, {ids[2 * e]}, {ids[2 * e + 1]}, {ids[2 * e + 2]}")
        mkey = (float(m["E"]), float(m.get("nu", 0.3)), float(m.get("rho", 0)))
        mname = mats.setdefault(mkey, f"M{len(mats) + 1}")
        n1 = orient(t)
        lines_sec += [f"*ELSET, ELSET=B{k + 1}", ccx_io._rows(es), f"*BEAM SECTION, ELSET=B{k + 1}, MATERIAL={mname}, SECTION={stype}", sline, f"{n1[0]:.6f}, {n1[1]:.6f}, {n1[2]:.6f}"]
        mem.append({"name": m.get("name") or f"M{k + 1}", "nodes": ids, "a": a, "b": b, "t": t, "L": L, "A": A, "I": I, "c": cmax, "elements": es,
                    "rho": float(m.get("rho", 0)), "E": float(m["E"]), "nu": float(m.get("nu", 0.3)), "section": dict(m["section"]), "n1": n1,
                    "w": [0.0, 0.0, 0.0]})
    byname = {m["name"]: m for m in mem}

    def addload(node, f):
        acc = loads_c.setdefault(node, [0.0, 0.0, 0.0])
        for c in range(3):
            acc[c] += f[c]

    points = {}

    def along(m, w):
        for c in range(3):
            m["w"][c] += w[c]
        le = m["L"] / n
        for e in range(n):
            a_, mid, c_ = m["nodes"][2 * e], m["nodes"][2 * e + 1], m["nodes"][2 * e + 2]
            addload(a_, [x * le / 6 for x in w])
            addload(mid, [x * 2 * le / 3 for x in w])
            addload(c_, [x * le / 6 for x in w])

    applied = 0.0
    for ld in loads or []:
        if ld.get("member"):
            m = byname.get(ld["member"])
            if m is None:
                raise ValueError(f"load on member {ld['member']!r}: no such member")
            w = [float(x) for x in ld["w"]]
            along(m, w)
            applied += _norm(w) * m["L"]
        else:
            p = [float(x) for x in ld["at"]]
            j = next((i for i, q in enumerate(joints) if _norm(_sub(p, q)) <= tol), None)
            if j is None:
                raise ValueError(f"load at {p}: no joint there (loads go on member ends or along members)")
            addload(jnode[j], [float(x) for x in ld["force"]])
            acc = points.setdefault(jnode[j], [0.0, 0.0, 0.0])
            for c in range(3):
                acc[c] += float(ld["force"][c])
            applied += _norm(ld["force"])
    if gravity is not None:
        for m in mem:
            if m["rho"] > 0:
                q = m["rho"] * 1e-12 * m["A"]  # t/mm per mm length … N/mm per (mm/s²)
                along(m, [g * q for g in gravity])
    sup_lines, sup_sets = [], []
    for k, sp in enumerate(supports or []):
        p = [float(x) for x in sp["at"]]
        j = next((i for i, q in enumerate(joints) if _norm(_sub(p, q)) <= tol), None)
        if j is None:
            raise ValueError(f"support at {p}: no member end there")
        node = jnode[j]
        kind = sp.get("kind", "pinned")
        if kind == "fixed":
            sup_lines += [f"{node}, 1, 6"]
        elif kind == "pinned":
            sup_lines += [f"{node}, 1, 3"]
        elif kind == "roller":
            # held up and sideways, free to slide along the member it carries
            att = next((m for m in mem if node in (m["nodes"][0], m["nodes"][-1])), None)
            side = 1 if att is None or abs(att["t"][0]) >= abs(att["t"][1]) else 0
            sup_lines += [f"{node}, 3, 3", f"{node}, {side + 1}, {side + 1}"]
        else:
            raise ValueError("support kind: pinned | fixed | roller")
        sup_sets.append((f"S{k + 1}", node, p, kind))
    # torsion: a beam on pins is free to roll about its own axis; at each
    # pinned or roller support it is held about the axis nearest its own,
    # as a real seat holds it (joints between members are rigid already)
    held_rot = set()
    for _, node, _, kind in sup_sets:
        if kind == "fixed":
            continue
        for m in mem:
            if node in (m["nodes"][0], m["nodes"][-1]):
                ax = max(range(3), key=lambda c: abs(m["t"][c]))
                if (node, ax) not in held_rot:
                    held_rot.add((node, ax))
                    sup_lines.append(f"{node}, {4 + ax}, {4 + ax}")
    out = ["*NODE, NSET=NALL"] + [f"{i}, {p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f}" for i, p in sorted(node_xyz.items())]
    out += ["*ELEMENT, TYPE=B32R, ELSET=EALL"] + lines_el
    for (E, nu, rho), name in mats.items():
        out += [f"*MATERIAL, NAME={name}", "*ELASTIC", f"{E:.6g}, {nu:.6g}"] + (["*DENSITY", f"{rho * 1e-12:.6g}"] if rho else [])
    out += lines_sec
    for name, node, _, _ in sup_sets:
        out += [f"*NSET, NSET={name}", str(node)]
    out += ["*STEP", "*STATIC", "*BOUNDARY"] + sup_lines
    if loads_c:
        out += ["*CLOAD"] + [f"{nd}, {c + 1}, {v[c]:.9g}" for nd, v in sorted(loads_c.items()) for c in range(3) if abs(v[c]) > 1e-12]
    out += ["*NODE FILE", "U", "*EL FILE", "S"]
    for name, _, _, _ in sup_sets:
        out += [f"*NODE PRINT, NSET={name}, TOTALS=ONLY", "RF"]
    out += ["*END STEP", ""]
    held = []
    for ln in sup_lines:
        nd, d0, d1 = (int(x) for x in ln.split(","))
        held += [(nd, d) for d in range(d0, d1 + 1)]
    return "\n".join(out), {"members": mem, "supports": sup_sets, "applied": applied, "nodal": loads_c, "points": points, "held": held, "xyz": node_xyz}


def read_coords(frd):
    xyz, on = {}, False
    for line in frd.splitlines():
        if line.startswith("    2C"):
            on = True
            continue
        if on:
            if line.startswith(" -3"):
                break
            if line.startswith(" -1"):
                xyz[int(line[3:13])] = (float(line[13:25]), float(line[25:37]), float(line[37:49]))
    return xyz


def read_reactions(dat):
    """{set name: [fx, fy, fz]} from *NODE PRINT TOTALS=ONLY."""
    out, cur = {}, None
    for line in dat.splitlines():
        low = line.lower()
        if "force (fx,fy,fz)" in low and "set" in low:
            cur = line.split("set")[-1].split()[0].strip().upper()
            continue
        if cur and line.strip():
            try:
                vals = [float(x) for x in line.split()]
            except ValueError:
                continue
            if len(vals) >= 3:
                out[cur] = vals[-3:]
                cur = None
    return out


def solve(ccx, workdir, members, supports, loads, gravity=None, n=8, timeout=300, tol=1.0):
    text, book = build(members, supports, loads, gravity, n, tol)
    os.makedirs(workdir, exist_ok=True)
    for f in os.listdir(workdir):
        if f.startswith("frame."):
            os.remove(os.path.join(workdir, f))
    with open(os.path.join(workdir, "frame.inp"), "w") as f:
        f.write(text)
    env = dict(os.environ)
    env.setdefault("OMP_NUM_THREADS", "2")
    r = subprocess.run([ccx, "-i", "frame"], cwd=workdir, capture_output=True, text=True, timeout=timeout, env=env)
    frd_p = os.path.join(workdir, "frame.frd")
    log = (r.stdout or "") + (r.stderr or "")
    if "*ERROR" in log or not os.path.isfile(frd_p):
        err = [ln.strip() for ln in log.splitlines() if "ERROR" in ln][:2] or log.strip().splitlines()[-2:]
        singular = any("singular" in ln.lower() or "zero pivot" in ln.lower() for ln in log.splitlines())
        raise RuntimeError("CalculiX refused the frame: " + " | ".join(err) + (" — it can move as a mechanism: more supports, or fixed ones." if singular else ""))
    with open(frd_p) as f:
        frd = f.read()
    dat = ""
    if os.path.isfile(os.path.join(workdir, "frame.dat")):
        with open(os.path.join(workdir, "frame.dat")) as f:
            dat = f.read()
    return read_results(book, frd, dat, workdir, gravity)


def read_elements(frd):
    """{element: [nodes]} of the .frd's element block: CalculiX writes each
    beam element expanded into a solid (C3D20R) under the beam's own number."""
    els, on, cur = {}, False, None
    for line in frd.splitlines():
        if line.startswith("    3C"):
            on = True
            continue
        if not on:
            continue
        if line.startswith(" -3"):
            break
        if line.startswith(" -1"):
            cur = int(line[3:13])
            els[cur] = []
        elif line.startswith(" -2") and cur is not None:
            els[cur] += [int(x) for x in line[3:].split()]
    return els


def member_nodes(m, els, xyz):
    """The expanded nodes of a member: those of its own elements (finding
    4a of the bicycle runs, 21 Nov). Before, every node within 1.6 c of the
    member's axis counted: at a joint a short member took its neighbours'
    nodes, whose von Mises (any direction) is not this member's stress
    along it — a 35 mm member read 214 MPa against -9.9 … 5.4 MPa along it.
    [(node, distance along the member)]; by the old reach when the .frd
    has no elements."""
    def along(p):
        return _dot(_sub(p, m["a"]), m["t"])

    if els:
        seen, out = set(), []
        for e in m["elements"]:
            for nd in els.get(e, ()):
                if nd not in seen and nd in xyz:
                    seen.add(nd)
                    out.append((nd, along(xyz[nd])))
        if out:
            return out
    reach = m["c"] * 1.6 + 1.0
    out = []
    for nd, p in xyz.items():
        v = _sub(p, m["a"])
        s_ = _dot(v, m["t"])
        if -1e-6 <= s_ <= m["L"] + 1e-6 and _norm([v[c] - m["t"][c] * s_ for c in range(3)]) <= reach:
            out.append((nd, s_))
    return out


def read_results(book, frd, dat, workdir="", gravity=None):
    """The answer from CalculiX's files: each member's stress along it, von
    Mises, deflection; each support's reaction. The stresses come from the
    section forces (section_forces) where the beams solve here; else from
    the expanded solids' nodes."""
    disp, stress = ccx_io.read_frd(frd)
    xyz = read_coords(frd)
    els = read_elements(frd)
    reac = read_reactions(dat)
    sf = section_forces(book, gravity) if book.get("xyz") else None
    rows = []
    for m in book["members"]:
        ns = member_nodes(m, els, xyz)
        if not ns:
            rows.append({"member": m["name"], "note": "no results found along it"})
            continue
        sig = [ccx_io.normal_stress(stress[nd], m["t"]) for nd, _ in ns if nd in stress]
        vm = [ccx_io.von_mises(stress[nd]) for nd, _ in ns if nd in stress]
        # deflection across the member, relative to the line between its ends
        ua = disp.get(m["nodes"][0], (0, 0, 0))[:3]
        ub = disp.get(m["nodes"][-1], (0, 0, 0))[:3]
        rel, tot = 0.0, 0.0
        for nd, s_ in ns:
            if nd not in disp:
                continue
            u = disp[nd][:3]
            f = min(max(s_ / m["L"], 0.0), 1.0)
            base = [ua[c] + (ub[c] - ua[c]) * f for c in range(3)]
            d = [u[c] - base[c] for c in range(3)]
            d = [d[c] - m["t"][c] * _dot(d, m["t"]) for c in range(3)]
            rel = max(rel, _norm(d))
            tot = max(tot, _norm(u))
        row = {"member": m["name"], "length": round(m["L"], 1), "axialBendingMPa": [round(min(sig), 3), round(max(sig), 3)] if sig else None,
               "vonMisesMPa": round(max(vm), 3) if vm else None, "deflectionMm": round(rel, 3), "spanOverDeflection": round(m["L"] / rel) if rel > 1e-9 else None,
               "movesMm": round(tot, 3), "stressFrom": "solid nodes"}
        got = (sf or {}).get(m["name"])
        if got:
            f = got["forces"]
            if sig or vm:
                row["solidNodesMPa"] = {"axialBending": row["axialBendingMPa"], "vonMises": row["vonMisesMPa"]}
            row.update({"axialBendingMPa": [round(got["lo"], 3), round(got["hi"], 3)], "vonMisesMPa": round(got["vm"], 3), "stressFrom": "section forces",
                        "sectionForces": {"atMm": round(got["at"], 2), "axialN": round(f["N"], 2), "shearN": round(math.hypot(f["Vy"], f["Vz"]), 2),
                                          "torqueNmm": round(f["T"], 1), "momentNmm": round(math.hypot(f["My"], f["Mz"]), 1)}})
        rows.append(row)
    # what the support gives: CalculiX's reaction, plus the load laid right on
    # the supported node (it goes straight into the support)
    sups = []
    for name, node, p, kind in book["supports"]:
        rf = reac.get(name.upper())
        on = book["nodal"].get(node, [0.0, 0.0, 0.0])
        sups.append({"at": [round(c, 2) for c in p], "kind": kind, "reactionN": [round(rf[c] - on[c], 2) for c in range(3)] if rf else None})
    out = {"members": rows, "supports": sups, "files": workdir}
    # the reactions must carry the whole load: CalculiX reads them low on some
    # beam supports (a point load on a column) — said, not hidden
    tot = [sum(v[c] for v in book["nodal"].values()) for c in range(3)]
    got = [sum((sp["reactionN"] or [0, 0, 0])[c] for sp in sups) for c in range(3)]
    if any(abs(got[c] + tot[c]) > 0.02 * max(1.0, max(abs(x) for x in tot)) for c in range(3)):
        out["reactionsNote"] = (f"the reactions add to {[round(x, 1) for x in got]} N against {[round(-x, 1) for x in tot]} N of load: "
                                "CalculiX reads beam supports short here — use the load total, and member stresses, which are sound")
    out["loadTotalN"] = [round(x, 1) for x in tot]
    return out


# ---- section forces by the beam solution (bicycle runs, 21 Nov 2026) -------------------
# A cantilever L 47, circ d 26, 500 N at the tip: M·c/I is 13.62 MPa at the
# root, but the expanded solids' nodes read 12.78 along it and 10.61 von
# Mises. CalculiX expands a round section into a block of 20-node solids,
# so its nodes are not on the outer fibre, and its own SECTION FORCES output
# replaces the stresses and is said to be unsound. Thus the frame is solved
# again here as beams (Euler-Bernoulli, 6 freedoms a node, the same nodes,
# supports and loads as the deck) for the forces in each section, and the
# stress is N/A ± M/W with the section's own W.

def section_stiffness(sec):
    """{A, Iy, Iz, J} in mm, mm⁴ about the section's own axes: y is the
    1-direction (across, the width b), z the 2-direction (the depth d)."""
    k = sec.get("kind", "rect")
    z = section_check(sec)
    if k == "circ":
        d = z["d"]
        i = math.pi * d ** 4 / 64
        return {"A": math.pi * d * d / 4, "Iy": i, "Iz": i, "J": 2 * i}
    if k == "pipe":
        do, di = z["d"], z["d"] - 2 * z["t"]
        i = math.pi * (do ** 4 - di ** 4) / 64
        return {"A": math.pi * (do * do - di * di) / 4, "Iy": i, "Iz": i, "J": 2 * i}
    if k == "rect":
        b, d = z["b"], z["d"]
        a_, c_ = max(b, d), min(b, d)
        j = a_ * c_ ** 3 * (1 / 3 - 0.21 * (c_ / a_) * (1 - c_ ** 4 / (12 * a_ ** 4)))
        return {"A": b * d, "Iy": b * d ** 3 / 12, "Iz": d * b ** 3 / 12, "J": j}
    b, d, t = z["b"], z["d"], z["t"]
    am = (b - t) * (d - t)
    return {"A": b * d - (b - 2 * t) * (d - 2 * t), "Iy": (b * d ** 3 - (b - 2 * t) * (d - 2 * t) ** 3) / 12,
            "Iz": (d * b ** 3 - (d - 2 * t) * (b - 2 * t) ** 3) / 12, "J": 4 * am * am * t / (2 * ((b - t) + (d - t)))}


def section_stress(sec, f):
    """(σ min, σ max, von Mises) in MPa for the section forces f { N, Vy, Vz,
    T, My, Mz } (N, N·mm). σ = N/A ± M/W at the outer fibre (a round:
    the resultant moment; a rect or box: the corner). von Mises: the outer
    fibre with the torsion shear, or the neutral axis with the torsion and
    the transverse shear, the larger."""
    k = sec.get("kind", "rect")
    z = section_check(sec)
    p = section_stiffness(sec)
    a = p["A"]
    n_a = f["N"] / a
    v = math.hypot(f["Vy"], f["Vz"])
    t_ = abs(f["T"])
    if k in ("circ", "pipe"):
        r = z["d"] / 2
        bend = math.hypot(f["My"], f["Mz"]) * r / p["Iy"]
        tau_t = t_ * r / p["J"]
        tau_v = (4 * v / (3 * a)) if k == "circ" else 2 * v / a
    elif k == "rect":
        b, d = z["b"], z["d"]
        bend = abs(f["My"]) * (d / 2) / p["Iy"] + abs(f["Mz"]) * (b / 2) / p["Iz"]
        a_, c_ = max(b, d), min(b, d)
        tau_t = t_ * (3 * a_ + 1.8 * c_) / (a_ * a_ * c_ * c_)
        tau_v = 1.5 * v / a
    else:
        b, d, t = z["b"], z["d"], z["t"]
        bend = abs(f["My"]) * (d / 2) / p["Iy"] + abs(f["Mz"]) * (b / 2) / p["Iz"]
        tau_t = t_ / (2 * t * (b - t) * (d - t))
        tau_v = abs(f["Vz"]) / (2 * t * d) + abs(f["Vy"]) / (2 * t * b)
    lo, hi = n_a - bend, n_a + bend
    vm = max(math.sqrt(max(abs(lo), abs(hi)) ** 2 + 3 * tau_t ** 2), math.sqrt(n_a ** 2 + 3 * (tau_t + tau_v) ** 2))
    return lo, hi, vm


def _local_k(E, G, s, L):
    import numpy as np

    k = np.zeros((12, 12))
    ea, gj = E * s["A"] / L, G * s["J"] / L
    k[0, 0] = k[6, 6] = ea
    k[0, 6] = k[6, 0] = -ea
    k[3, 3] = k[9, 9] = gj
    k[3, 9] = k[9, 3] = -gj
    for (v1, r1, v2, r2, i, sg) in ((1, 5, 7, 11, s["Iz"], 1.0), (2, 4, 8, 10, s["Iy"], -1.0)):
        a12, a6, a4, a2 = 12 * E * i / L ** 3, 6 * E * i / L ** 2, 4 * E * i / L, 2 * E * i / L
        ent = {(v1, v1): a12, (v1, r1): sg * a6, (v1, v2): -a12, (v1, r2): sg * a6,
               (r1, r1): a4, (r1, v2): -sg * a6, (r1, r2): a2,
               (v2, v2): a12, (v2, r2): -sg * a6, (r2, r2): a4}
        for (p_, q), val in ent.items():
            k[p_, q] = k[q, p_] = val
    return k


def _fixed_end(q, L):
    """The equivalent nodal loads (local) of a load q [qx, qy, qz] N/mm along the element."""
    qx, qy, qz = q
    return [qx * L / 2, qy * L / 2, qz * L / 2, 0.0, -qz * L * L / 12, qy * L * L / 12,
            qx * L / 2, qy * L / 2, qz * L / 2, 0.0, qz * L * L / 12, -qy * L * L / 12]


SECTION_DOF_LIMIT = 30000


def section_forces(book, gravity=None):
    """{member: {"lo", "hi", "vm", "at", "forces"}}: the frame solved as
    beams on the deck's own end and mid nodes, the forces at each element
    end, and the section's worst point along the member. None when it cannot
    be solved here (no numpy, too many freedoms, a mechanism)."""
    try:
        import numpy as np
    except ImportError:
        return None
    mem = book["members"]
    nodes = []
    for m in mem:
        for nd in m["nodes"]:
            if nd not in nodes:
                nodes.append(nd)
    idx = {nd: i for i, nd in enumerate(nodes)}
    ndof = 6 * len(nodes)
    if ndof > SECTION_DOF_LIMIT:
        return None
    try:
        from scipy import sparse
        from scipy.sparse.linalg import spsolve
    except ImportError:
        sparse = None
        if ndof > 6000:
            return None
    rows, cols, vals = [], [], []
    F = np.zeros(ndof)
    elems = []
    for m in mem:
        s = section_stiffness(m["section"])
        G = m["E"] / (2 * (1 + m.get("nu", 0.3)))
        x = np.array(m["t"])
        y = np.array(m["n1"])
        zz = np.cross(x, y)
        R = np.vstack([x, y, zz])
        T = np.zeros((12, 12))
        for b in range(4):
            T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
        w = list(m.get("w") or [0.0, 0.0, 0.0])
        if gravity is not None and m.get("rho"):
            q = m["rho"] * 1e-12 * m["A"]
            w = [w[c] + gravity[c] * q for c in range(3)]
        ql = list(R @ np.array(w))
        for e in range(len(m["nodes"]) - 1):
            a_, b_ = m["nodes"][e], m["nodes"][e + 1]
            pa, pb = book["xyz"][a_], book["xyz"][b_]
            L = _norm(_sub(pb, pa))
            kl = _local_k(m["E"], G, s, L)
            kg = T.T @ kl @ T
            fe = np.array(_fixed_end(ql, L))
            dofs = [6 * idx[a_] + i for i in range(6)] + [6 * idx[b_] + i for i in range(6)]
            F[dofs] += T.T @ fe
            for i in range(12):
                for j in range(12):
                    if kg[i, j] != 0.0:
                        rows.append(dofs[i])
                        cols.append(dofs[j])
                        vals.append(kg[i, j])
            elems.append((m["name"], kl, T, fe, dofs, sum(_norm(_sub(book["xyz"][m["nodes"][i + 1]], book["xyz"][m["nodes"][i]])) for i in range(e)), L))
    for nd, f in (book.get("points") or {}).items():
        if nd in idx:
            F[6 * idx[nd]:6 * idx[nd] + 3] += np.array(f)
    held = {6 * idx[nd] + d - 1 for nd, d in book.get("held") or () if nd in idx}
    free = np.array([i for i in range(ndof) if i not in held])
    U = np.zeros(ndof)
    try:
        if sparse is not None:
            K = sparse.coo_matrix((vals, (rows, cols)), shape=(ndof, ndof)).tocsr()
            kf = K[free][:, free]
            U[free] = spsolve(kf.tocsc(), F[free])
        else:
            K = np.zeros((ndof, ndof))
            np.add.at(K, (np.array(rows), np.array(cols)), np.array(vals))
            U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
    except Exception:  # noqa: BLE001 - a mechanism, or the solver failed: the expanded nodes answer
        return None
    if not np.all(np.isfinite(U)):
        return None
    out = {}
    for name, kl, T, fe, dofs, s0, L in elems:
        fl = kl @ (T @ U[dofs]) - fe
        sec = next(m["section"] for m in mem if m["name"] == name)
        for end, at in ((0, s0), (1, s0 + L)):
            o = 6 * end
            sg = -1.0 if end == 0 else 1.0  # the force of the far side on the section, as N + along the member
            f = {"N": float(sg * fl[o]), "Vy": float(fl[o + 1]), "Vz": float(fl[o + 2]), "T": float(fl[o + 3]), "My": float(fl[o + 4]), "Mz": float(fl[o + 5])}
            lo, hi, vm = section_stress(sec, f)
            r = out.setdefault(name, {"lo": lo, "hi": hi, "vm": vm, "at": at, "forces": f})
            r["lo"], r["hi"] = min(r["lo"], lo), max(r["hi"], hi)
            if vm > r["vm"] or (vm == r["vm"] and at == 0):
                r["vm"], r["at"], r["forces"] = vm, at, f
    return out
