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
SHOWN = ("dfm_check", "part_review")
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
