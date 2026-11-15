# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for Workshop Electronics: kicad_import, board_enclosure,
# pcb_order_package and printed_channel, the names they have always had —
# the handlers in handlers.py (no Agent Link import there) bound to the
# session. Their definitions are data (data/tools.json); loaded by Agent
# Link only.

from workshop_electronics import tooldata as tooldefs

from . import handlers, pcb

GROUP = "electronics"
INFO = "Boards and wiring (Workshop for FreeCAD · Electronics): KiCad boards read in, enclosures round them, PCB order packages, channels for wire or conductive traces with their resistance."
DATA = tooldefs.here(__file__)


def tools(session):
    made = tooldefs.build(DATA, GROUP, handlers.bound(session), "Electronics")
    for t in made:
        # The board houses offered are the data file's (the person's own added).
        if t.name == "pcb_order_package":
            t.schema["properties"]["vendor"]["enum"] = list(pcb.vendors())
    return made
