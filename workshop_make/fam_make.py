# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for the make loop: setup, part_spec, dfm_check,
# part_review and slice, the names they have always had — how each part is
# made, the limits it must meet, the printability check, the verdict, and
# slicing with PrusaSlicer. A thin layer over workshop_make.api; loaded by
# Agent Link only. Moved from Agent Link's tools.py on 14 Nov 2026.
# Agent Link's binding: the handlers in handlers/make.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import make as H

GROUP = "make"
WORKBENCHES = {"setup": "WorkshopMakeWorkbench", "dfm_check": "PartDesignWorkbench", "part_review": "PartDesignWorkbench", "slice": "WorkshopMakeWorkbench"}  # where the buttons are: the checks in Part Design (Make Checks), setups and slicing in Make
COMMANDS = {"setup": "Workshop_Make_NewSetup", "dfm_check": "Workshop_Make_DfmCheck", "part_review": "Workshop_Make_PartReview", "slice": "Workshop_Make_Slice"}  # the button that does the same
SHOWN = ("dfm_check", "part_review")
# What each call did and came to, in Agent Link's Activity and caption
# words (agentlink/activity.py templates: the first whose {fields} are all
# in the arguments or the answer wins). Heavy reads keep their own words, not
# an earlier change's (window review round 3: 1009, 1010, 2008).
PHRASES = {
    "dfm_check": ["Checked {body} for printing: {verdict}"],
    "part_review": ["Reviewed {body}: {verdict}"],
    "slice": ["Sliced {body} with {slicer}: {time}, {filamentG} g", "Sliced {body} with {slicer}: {gcode}"],
}
# What a read worked on, by its answer's key, to select in the window (an
# Agent Link that reads SELECTS; its echo selects a read's arguments only,
# and never a whole Part Design body).
SELECTS = {"dfm_check": "body", "part_review": "body", "slice": "body"}
# The bench while these run (Agent Link's echo; exact names, so
# part_review and part_spec are not taken for core's part_ → Part).
INFO = "How each part is made (setups), its limits and material, the printability check, the verdict, slicing (Workshop for FreeCAD · Make)."
LEAN = True

try:
    from agentlink import hooks
    from agentlink.families import material as matfam
except ImportError:  # an older Agent Link: no hooks or material family
    hooks = matfam = None
handlers.lend(H, ToolError=ToolError, hooks=hooks, matfam=matfam)


def tools(session):
    return tooldefs.build("make", handlers.bound(session, H.HANDLERS))


def command_for(name, args):
    """The button for a call whose button depends on what it asks."""
    act = (args or {}).get("action")
    if name == "setup" and act in ("set", "remove"):
        return "Workshop_Make_" + ("AddBody" if act == "set" else "RemoveSetup")
    return COMMANDS.get(name)
