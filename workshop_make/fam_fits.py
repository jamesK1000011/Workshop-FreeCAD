# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for fits and hardware holes (fit, hw_hole), the names
# they have always had: a thin layer over workshop_make.api. Loaded by Agent
# Link only.
# Agent Link's binding: the handlers in handlers/fits.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import fits as H
from .words import words as WORDS  # the window's words with the answer's figure (Agent Link's echo)

GROUP = "fits"
WORKBENCHES = {"fit": "WorkshopMakeWorkbench", "hw_hole": "PartDesignWorkbench"}  # where their buttons are (Hole for hardware after PartDesign_Hole)
COMMANDS = {"fit": "Workshop_Make_FitSize", "hw_hole": "Workshop_Make_Hole"}  # the button that does the same
INFO = "Fits, printer calibration, tolerance stacks and holes for hardware (Workshop for FreeCAD · Make)."
LEAN = True

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("fits", handlers.bound(session, H.HANDLERS))


def command_for(name, args):
    """The button for a call whose button depends on what it asks."""
    if name == "fit" and (args or {}).get("action") == "calibrate":
        return "Workshop_Make_Calibrate"
    return COMMANDS.get(name)
