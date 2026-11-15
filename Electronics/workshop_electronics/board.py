# SPDX-License-Identifier: LGPL-2.1-or-later
# A KiCad board as FreeCAD shapes: the board solid from its outline (cut-outs
# and mounting holes through it), component heights from their STEP models,
# wire sizes and resistivities. Needs FreeCAD; no agent.
# Moved from Agent Link for FreeCAD's electronics family on 14 Nov 2026.

import math
import os
import re

import FreeCAD
import Part

from workshop_electronics import geo

# Volume resistivity, Ω·cm, typical published figures for printed parts —
# the maker's sheet is the authority.
RESISTIVITY = {"carbon-pla": 30.0, "electrifi": 0.006}
CU = 1.724e-6  # Ω·cm, annealed copper at 20 °C
# Opening heights for edge connectors whose height the file does not give.
GUESS_H = 5.0

V = FreeCAD.Vector

# Volume resistivity, Ω·cm, typical published figures for printed parts —
# the maker's sheet is the authority.
RESISTIVITY = {"carbon-pla": 30.0, "electrifi": 0.006}
CU = 1.724e-6  # Ω·cm, annealed copper at 20 °C
# Opening heights for edge connectors whose height the file does not give.
GUESS_H = 5.0


def awg_mm(n):
    """The diameter of AWG n solid wire, mm (ASTM B258's formula)."""
    return 0.127 * 92 ** ((36 - n) / 39.0)


def _edge(seg):
    if seg["type"] == "line":
        return Part.LineSegment(V(*seg["a"], 0), V(*seg["b"], 0)).toShape()
    if seg["type"] == "arc":
        return Part.Arc(V(*seg["a"], 0), V(*seg["m"], 0), V(*seg["b"], 0)).toShape()
    return Part.makeCircle(seg["r"], V(*seg["c"], 0))


def _face(loop):
    edges = [_edge(s) for s in loop if not (s["type"] == "line" and math.hypot(s["a"][0] - s["b"][0], s["a"][1] - s["b"][1]) < 1e-6)]
    w = Part.Wire(Part.__sortEdges__(edges))
    if not w.isClosed():
        raise ValueError("an outline loop that does not close")
    return Part.Face(w)


def board_shape(b):
    """The board as one solid on z = 0 up to its thickness: the outer
    outline, cut-outs and mounting holes through it."""
    t = b["thickness"]
    lps = b["outline"]["loops"]
    outer = _face(lps[b["outline"]["outer"]]).extrude(V(0, 0, t))
    cuts = []
    for i, lp in enumerate(lps):
        if i != b["outline"]["outer"]:
            try:
                f = _face(lp)
            except Exception:  # an inner loop FreeCAD cannot face: left solid
                continue
            f.translate(V(0, 0, -1))
            cuts.append(f.extrude(V(0, 0, t + 2)))
    for h in b["holes"]:
        cuts.append(Part.makeCylinder(h["d"] / 2, t + 2, V(h["at"][0], h["at"][1], -1)))
    return geo.cut_all(outer, cuts)


def _model_height(path, scale_z, base_dir):
    """A component's height from its 3D model, where the model is a STEP
    file this computer has: None otherwise."""
    p = re.sub(r"\$\{([^}]+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), path)
    if not os.path.isabs(p) and base_dir:
        p = os.path.join(base_dir, p)
    cands = [p] + [os.path.splitext(p)[0] + e for e in (".step", ".stp", ".STEP")]
    for c in cands:
        if os.path.isfile(c) and c.lower().endswith((".step", ".stp")):
            try:
                sh = Part.read(c)
                return sh.BoundBox.ZMax * scale_z if sh.BoundBox.ZMax > 0 else sh.BoundBox.ZLength * scale_z
            except Exception:  # a model FreeCAD cannot read: no height from it
                return None
    return None
