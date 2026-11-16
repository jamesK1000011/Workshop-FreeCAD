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
INFO = "Slicing with PrusaSlicer, OrcaSlicer or Bambu Studio, profiles by path, the encased parts' pauses written in."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("slice", handlers.bound(session, H.HANDLERS))
