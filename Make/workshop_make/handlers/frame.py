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
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
matfam = None
ToolError = Refusal


V = FreeCAD.Vector


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
    for row in res["members"]:
        c = cards.get(row["member"])
        y = c.get("yield") if c else None
        if y and row.get("vonMisesMPa"):
            row["safety"] = round(y / row["vonMisesMPa"], 2) if row["vonMisesMPa"] > 0 else None
        if limit and row.get("spanOverDeflection"):
            row["deflectionOk"] = row["spanOverDeflection"] >= limit
    worst = min((r for r in res["members"] if r.get("safety")), key=lambda r: r["safety"], default=None)
    out = {**res, "members": res["members"], "elements": "B32 beams, expanded to solids by CalculiX", "worst": worst["member"] if worst else None,
           "note": "Joints between members are rigid; pinned and roller supports are held about the member's own axis. A frame model is a sizing look, not the connection design."}
    return out


HANDLERS = {
    "fea_frame": fea_frame,
}
