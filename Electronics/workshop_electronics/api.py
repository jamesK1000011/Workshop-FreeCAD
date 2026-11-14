# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics with no agent: a macro or a command calls these. Never imports
# Agent Link.
import os

import addonkit
from addonkit import Refused

from . import kicad, pcb

addonkit.require(">=1.4,<2", "Workshop Electronics")

classify = pcb.classify
gerber_box = pcb.gerber_box
order_sheet = pcb.order_sheet
vendors = pcb.vendors
screw_for = kicad.screw_for


def read_board(path):
    """A .kicad_pcb read without KiCad: outline, thickness, layers, holes,
    footprints with their side, place and courtyard (mm, y up)."""
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise Refused(f"{path!r} is not a file — the .kicad_pcb's full path.", "not_found")
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        return kicad.read_board(text, path)
    except ValueError as e:
        raise Refused(f"{os.path.basename(path)}: {e}")


def add_board(doc, board, name=None):
    """The board as a solid in doc (outline, cut-outs and mounting holes);
    the new object."""
    from . import board as B

    o = doc.addObject("Part::Feature", "Board")
    o.Label = name or board.get("title") or "Board"
    o.Shape = B.board_shape(board)
    doc.recompute()
    return o
