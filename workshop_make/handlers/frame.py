# SPDX-License-Identifier: LGPL-2.1-or-later
# The handler for frames of straight members (fea_frame): beam elements
# solved by CalculiX — beams, rafters, portal frames, trusses, shelving.
# Its own deck (frame.py), not FreeCAD's FEM, so it is Make's; it sits in
# the strength group beside FreeCAD's FEM tools. Moved from Agent Link's
# strength family on 14 Nov 2026.
import os

import FreeCAD

from workshop_make import ccx as ccx_io

from .. import frame as FR
from ..api import frame_verdict
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
matfam = None
ToolError = Refusal


V = FreeCAD.Vector
G = 9810.0  # mm/s², gravity (as Agent Link's strength family had it before the move)


def fea_frame(s, a):
    """A frame of straight members by beam elements: from members given
    (from, to, section, material) or from bodies (box-like BIM members:
    their centre line and their own width and depth)."""

    ccx = ccx_io.find_binary("ccx", "Ccx", "ccxBinaryPath", "AGENTLINK_CCX")
    if not ccx:
        raise ToolError("unavailable", "CalculiX (ccx) not found: install it, or set its path in FreeCAD's FEM preferences or AGENTLINK_CCX.")
    members, cards = [], {}
    default_mat = a.get("material")

    def mat_of(mid, label=None):
        if mid:
            c = matfam.card(s.doc, mid) or matfam.card(s.doc, str(mid).lower())
            if c is None:
                raise ToolError("not_found", f"material {mid!r}: material_list finds one.")
        elif label:
            c, _ = matfam.of_body(s.doc, label)
        else:
            raise ToolError("invalid_input", "material: an id (material_list) for the members, or on each member.")
        if not c.get("E"):
            raise ToolError("invalid_state", f"{c['name']} has no Young's modulus.")
        return c

    for k, m in enumerate(a.get("members") or []):
        sec = m.get("section") or {}
        if sec.get("kind", "rect") not in FR.SECTIONS:
            raise ToolError("invalid_input", f"members[{k}].section.kind: {', '.join(FR.SECTIONS)}.")
        for end in ("from", "to"):
            v = m.get(end)
            if not (isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)):
                raise ToolError("invalid_input", f"members[{k}].{end}: [x, y, z] mm — the member's {'start' if end == 'from' else 'end'}.")
        c = mat_of(m.get("material") or default_mat)
        name = m.get("name") or f"M{k + 1}"
        cards[name] = c
        members.append({"name": name, "from": m["from"], "to": m["to"], "section": sec, "E": float(c["E"]), "nu": float(c.get("nu") or 0.3),
                        "rho": float(c.get("density") or 0) * 1000})
    for ref in a.get("bodies") or []:
        o = s.body(ref) if not isinstance(ref, str) or not s.doc.getObjectsByLabel(ref) else s.doc.getObjectsByLabel(ref)[0]
        sh = o.Shape
        if not sh.Solids:
            raise ToolError("invalid_state", f"{o.Label} has no solid.")
        rot = o.Placement.Rotation
        loc = sh.copy()
        loc.transformShape(o.Placement.inverse().toMatrix(), True)
        bb = loc.BoundBox
        dims = sorted([(bb.XLength, rot.multVec(V(1, 0, 0))), (bb.YLength, rot.multVec(V(0, 1, 0))), (bb.ZLength, rot.multVec(V(0, 0, 1)))], key=lambda t_: -t_[0])
        run, axis = dims[0]
        rest = sorted(dims[1:], key=lambda t_: -abs(t_[1].z))
        depth, width = rest[0][0], rest[1][0]
        if abs(axis.z) > 0.95:
            depth, width = max(depth, width), min(depth, width)
        cen = sh.BoundBox.Center
        p0, p1 = cen - axis * (run / 2), cen + axis * (run / 2)
        c = mat_of(default_mat, o.Label)
        cards[o.Label] = c
        members.append({"name": o.Label, "from": [p0.x, p0.y, p0.z], "to": [p1.x, p1.y, p1.z], "section": {"kind": "rect", "b": width, "d": depth},
                        "E": float(c["E"]), "nu": float(c.get("nu") or 0.3), "rho": float(c.get("density") or 0) * 1000})
    if not members:
        raise ToolError("invalid_input", "members [{ name, from, to, section { kind rect (b, d) | circ (d) | pipe (d, t) | box (b, d, t) }, material }] or bodies [labels].")
    loads = []
    for ld in a.get("loads") or []:
        if ld.get("member") and ld.get("kPa") is not None:
            w = -float(ld["kPa"]) * 1e-3 * float(ld.get("width", 1000))
            loads.append({"member": ld["member"], "w": [0, 0, w]})
        elif ld.get("member"):
            w = ld.get("w")
            loads.append({"member": ld["member"], "w": [0, 0, -float(w)] if isinstance(w, (int, float)) else w})
        else:
            loads.append(ld)
    tol = float(a.get("tolerance", 1.0 if not a.get("bodies") else max(max(m["section"].get("b", 0), m["section"].get("d", 0)) for m in members)))
    g = [0, 0, -G] if a.get("gravity") else None
    wd = os.path.join(s.out_dir, "frame_" + "".join(ch if ch.isalnum() else "_" for ch in (a.get("name") or "study")))
    try:
        text, _ = FR.build(members, a.get("supports") or [], loads, g, int(a.get("elements", 8)), tol)
    except (ValueError, KeyError) as e:
        raise ToolError("invalid_input", str(e))
    if not a.get("supports"):
        raise ToolError("invalid_input", "supports [{ at [x,y,z] a member's end, kind pinned | fixed | roller }]: a frame with none flies off.")
    try:
        res = FR.solve(ccx, wd, members, a.get("supports"), loads, g, int(a.get("elements", 8)), float(a.get("timeout", 300)), tol)
    except (ValueError, KeyError) as e:
        raise ToolError("invalid_input", str(e))
    except RuntimeError as e:
        raise ToolError("failed", str(e))
    limit = float(a.get("deflectionLimit", 0) or 0)
    # Bicycle runs (21 Nov), finding 4c: a card with no yield (Steel-Generic)
    # gave no safety; yieldMPa in the call judges every member (a member's
    # own yieldMPa first), and overrides the cards.
    y_all = _yield_arg(a.get("yieldMPa"), "yieldMPa")
    y_own = {}
    for k, m in enumerate(a.get("members") or []):
        if m.get("yieldMPa") is not None:
            y_own[m.get("name") or f"M{k + 1}"] = _yield_arg(m["yieldMPa"], f"members[{k}].yieldMPa")
    no_yield = []
    for row in res["members"]:
        c = cards.get(row["member"])
        y = y_own.get(row["member"]) or y_all or (c.get("yield") if c else None)
        if y:
            row["yieldMPa"] = y
            row["yieldFrom"] = "the member's yieldMPa" if row["member"] in y_own else ("the call's yieldMPa" if y_all else "the material card")
        elif c:
            no_yield.append(c.get("name") or row["member"])
        if y and row.get("vonMisesMPa"):
            row["safety"] = round(y / row["vonMisesMPa"], 2) if row["vonMisesMPa"] > 0 else None
        if limit and row.get("spanOverDeflection"):
            row["deflectionOk"] = row["spanOverDeflection"] >= limit
    worst = min((r for r in res["members"] if r.get("safety")), key=lambda r: r["safety"], default=None)
    out = {**res, "members": res["members"], "elements": "B32 beams, expanded to solids by CalculiX", "worst": worst["member"] if worst else None,
           "note": "Joints between members are rigid; pinned and roller supports are held about the member's own axis. A frame model is a sizing look, not the connection design."}
    # For the window's words and selection (Agent Link's echo: PHRASES,
    # SELECTS): the load as one number, the verdict, the bodies it was made of.
    tot = out.get("loadTotalN")
    if isinstance(tot, (list, tuple)) and tot:
        out["loadN"] = round(sum(float(x) ** 2 for x in tot) ** 0.5, 1)
    out["verdict"] = frame_verdict(res["members"])
    if no_yield:
        out["yieldNote"] = (f"No yield on the card of {', '.join(sorted(set(no_yield))[:5])}: no safety for those members. "
                            "yieldMPa: the yield in MPa (the supplier's figure) judges them.")
    if a.get("bodies"):
        out["bodies"] = [m["name"] for m in members[len(a.get("members") or []):]]
    sag = [r["deflectionMm"] for r in res["members"] if isinstance(r.get("deflectionMm"), (int, float))]
    if sag:
        out["deflectionMaxMm"] = max(sag)
    out["sceneMarks"] = scene_marks(members, res["members"], a.get("supports") or [])
    return out


def _yield_arg(v, what):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        raise ToolError("invalid_input", f"{what}: the yield strength in MPa, more than 0 (the supplier's figure).")
    return float(v)


def scene_marks(members, rows, supports):
    """What the window draws for a frame (Agent Link's echo: an answer's
    sceneMarks, round 7, make 04-085): the frame is only in the deck, so the
    view kept the last bodies. Each member's centre line, a word at its middle
    (name and sag), a mark at each support. Plain Python."""
    sag = {r.get("member"): r.get("deflectionMm") for r in rows or () if isinstance(r, dict)}

    def p3(v):
        return [round(float(c), 3) for c in v]

    lines, labels = [], []
    for m in members[:200]:
        a, b = p3(m["from"]), p3(m["to"])
        lines.append([a, b])
        d = sag.get(m["name"])
        word = m["name"] + (f": sags {d:g} mm" if isinstance(d, (int, float)) else "")
        labels.append([[round((a[i] + b[i]) / 2, 3) for i in range(3)], word])
    points = [p3(sp["at"]) for sp in supports[:200] if isinstance(sp, dict) and isinstance(sp.get("at"), (list, tuple)) and len(sp["at"]) == 3]
    return {"lines": lines, "points": points, "labels": labels}


HANDLERS = {
    "fea_frame": fea_frame,
}
