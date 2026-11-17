# SPDX-License-Identifier: LGPL-2.1-or-later
# Slicing with the slicer the person uses: PrusaSlicer, OrcaSlicer or Bambu
# Studio by their command lines, with their own profiles by path or minimal
# ones written from the print setup; the pauses for parts encased mid-print
# (hw_embed, gen_make's magnets) written into the G-code.
# Agent Link's binding: the handlers in handlers/slicing.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import slicing as H

GROUP = "slice"
AREAS = {"slice": "Slice"}
# Activity and caption words (agentlink/activity.py templates; see fam_make).
PHRASES = {
    "slice_with": ["Sliced {body} with {slicer} into a project and G-code: {time}, {filamentG} g if {project}",
                   "Sliced {body} with {slicer}: {time}, {filamentG} g", "Sliced {body} with {slicer}: {gcode}"],
    "slicer_presets": ["Put {slicer} presets on {setup}", "Exported the presets to {exported}", "Kept the presets bundle {imported}",
                       "Listed {slicer} presets"],
}
SELECTS = {"slice_with": "body"}
INFO = "Slicing with PrusaSlicer, OrcaSlicer or Bambu Studio, profiles by path, the encased parts' pauses written in."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("slice", handlers.bound(session, H.HANDLERS))
