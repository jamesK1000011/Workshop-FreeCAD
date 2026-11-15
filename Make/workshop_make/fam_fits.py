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

GROUP = "fits"
INFO = "Fits, printer calibration, tolerance stacks and holes for hardware (Workshop for FreeCAD · Make)."
LEAN = True

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("fits", handlers.bound(session, H.HANDLERS))
