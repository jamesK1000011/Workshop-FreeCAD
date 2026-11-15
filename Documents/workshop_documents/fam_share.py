# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents: Agent Link's tools, their definitions in data/tools.json
# (moved from Agent Link for FreeCAD on 14 Nov 2026). Loaded by Agent Link only.
# Sharing parts: a library pack of bodies as STEP and STL, with a README of
# their sizes and how to print them, a licence, and credits for the parts
# remixed — with the computer's paths and the user's name kept out of the
# files.
# Agent Link's binding: the handlers in handlers/share.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from workshop_documents import tooldata as tooldefs

from . import handlers
from .handlers import share as H

DATA = tooldefs.here(__file__)
GROUP = "share"
INFO = "Sharing: library packs of bodies as STEP and STL with a README, a licence and credits, nothing personal in the files."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build(DATA, GROUP, handlers.bound(session, H.HANDLERS), "Documents")
