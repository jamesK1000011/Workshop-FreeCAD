# SPDX-License-Identifier: LGPL-2.1-or-later
# The wall-thickness map in Agent Link's view_render { map: "wall" }: the
# wall at each spot of the parts, straight in from the surface to where the
# material ends (red thin). Registered with Agent Link's renderer by
# agentlink_families; its ray casting is Agent Link's (render.wall_map).


def _bodies(s, a):
    refs = a.get("objects")
    if refs is None:
        return s.bodies() if s.doc else []
    if isinstance(refs, str):
        refs = [refs]
    return [s.body(r) for r in refs]


def wall(s, a):
    import numpy as np
    from agentlink import render

    reach = float(a.get("reach", 12.0))
    layers = []
    for i, o in enumerate(_bodies(s, a)):
        L = render.body_layer(o, i, tol=float(a.get("tolerance", 0.05)))
        V, F, vals = render.wall_map(L["V"], L["F"], reach=reach, cap=int(a.get("detail", 16000)))
        layers.append({"name": o.Label, "V": V, "F": F, "values": vals, "creases": True})
    # Colours spent on the thin end: up to twice the typical wall.
    allv = np.concatenate([l["values"] for l in layers]) if layers else np.zeros(0)
    fin = allv[np.isfinite(allv)]
    hi = min(reach, max(2.0, 2 * float(np.median(fin)))) if len(fin) else reach
    return {"layers": layers, "unit": "mm", "cmap": "jet_r", "worst": "min", "label": "WALL", "range": [0.0, round(hi, 1)],
            "note": f"The wall at each spot: straight in from the surface to where the material ends; {reach:g} mm or more reads {reach:g}. Red is thin."}


ABOUT = "The wall thickness at each spot of the parts (red thin)."
