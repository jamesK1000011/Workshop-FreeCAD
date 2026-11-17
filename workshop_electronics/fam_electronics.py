# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for Workshop Electronics: kicad_import, board_enclosure,
# pcb_order_package and printed_channel, the names they have always had —
# the handlers in handlers.py (no Agent Link import there) bound to the
# session. Their definitions are data (data/tools.json); loaded by Agent
# Link only.

import os

from workshop_electronics import tooldata as tooldefs

from . import handlers, pcb

GROUP = "electronics"
INFO = "Boards and wiring (Workshop for FreeCAD · Electronics): KiCad boards read in, enclosures round them, PCB order packages, channels for wire or conductive traces with their resistance."
DATA = tooldefs.here(__file__)

# What the window shows while these run (Agent Link's echo): the Workshop
# Electronics bench, and the KiCad board button for kicad_import.
# kicad_ has none: KiCad Board… is in File ▸ Import, in every workbench.
WORKBENCHES = {"board_": "PartDesignWorkbench", "pcb_": "WorkshopMakeWorkbench", "printed_channel": "PartDesignWorkbench"}
COMMANDS = {"kicad_import": "Workshop_Electronics_ImportBoard"}
# printed_channel cuts inside the body: the echo makes that body see-through
# for the call, so the channel (and a printed trace in it) shows (window
# round 8, 03-015: the block stayed solid green, no channel seen).
SEE_THROUGH = {"printed_channel": "body"}


def _name(p):
    return os.path.basename(p) if isinstance(p, str) and p else None


def WORDS(name, args, body):
    """The window's words for pcb_order_package (Agent Link's echo): the
    board house, the files packed and the zip, not only the tool's name
    (window round 8, 07-018). None for another call. Never raises."""
    if name != "pcb_order_package" or not isinstance(body, dict) or not body.get("package"):
        return None
    try:
        files = body.get("files") if isinstance(body.get("files"), dict) else {}
        kinds = [(files.get("gerbers"), "Gerber", "Gerbers"), (files.get("drill"), "drill file", "drill files"),
                 (files.get("bom"), "BOM", "BOMs"), (files.get("cpl"), "placement", "placements")]
        said = [f"{n} {one if n == 1 else many}" for n, one, many in kinds if isinstance(n, int) and n > 0]
        s = f"Packed the PCB order for {body.get('vendor') or 'the board house'}: {_name(body['package'])}"
        if said:
            s += " (" + ", ".join(said) + ")"
        board = body.get("board") if isinstance(body.get("board"), dict) else {}
        size = board.get("size")
        if isinstance(size, list) and len(size) == 2:
            s += f", board {size[0]:g} x {size[1]:g} mm"
            if board.get("layers"):
                s += f", {board['layers']} layers"
        if body.get("warnings"):
            s += f", {len(body['warnings'])} warning(s)"
        return s[:160]
    except Exception:  # noqa: BLE001
        return None


def SELECTS_FOR(name, args, body, doc):
    """pcb_order_package selects the board it packed (board: its label), not
    the last change's body left selected (07-018: Block plain). None for
    another call, or with no board given."""
    if name != "pcb_order_package":
        return None
    ref = (args or {}).get("board")
    return [ref] if isinstance(ref, str) and ref else None


def tools(session):
    made = tooldefs.build(DATA, GROUP, handlers.bound(session), "Electronics")
    for t in made:
        # The board houses offered are the data file's (the person's own added).
        if t.name == "pcb_order_package":
            t.schema["properties"]["vendor"]["enum"] = list(pcb.vendors())
    return made
