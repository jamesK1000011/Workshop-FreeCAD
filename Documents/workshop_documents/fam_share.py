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


# With ScanRuler-FreeCAD installed (it offers the library_pack service),
# its pack_setup, pack_plan and pack_write are the agent's library-pack
# tools: Documents' library_pack is left off the tool list then, still
# callable by name and still routed to the service (handlers/share.py), and
# the Library Pack command keeps working through it. Alone, it is listed.
SERVICE_TOOL = "library_pack"
INSTEAD = "pack_write"


def unlist_when_offered(tool, offered=None):
    """tool left off Agent Link's list while the library_pack service is
    offered: its alias_of (what Agent Link's listing reads to keep a name
    callable but unlisted) names ScanRuler's pack_write then, else None.
    Asked at each listing, so the order the add-ons load in does not
    matter."""
    offered = offered or (lambda: H.service() is not None)
    base = type(tool)

    class Deferring(base):
        @property
        def alias_of(self):
            return self.__dict__.get("_alias_of") or (INSTEAD if offered() else None)

        @alias_of.setter
        def alias_of(self, v):
            self.__dict__["_alias_of"] = v

    Deferring.__name__ = base.__name__
    tool.__class__ = Deferring
    return tool


def tools(session):
    out = tooldefs.build(DATA, GROUP, handlers.bound(session, H.HANDLERS), "Documents")
    for t in out:
        if t.name == SERVICE_TOOL:
            unlist_when_offered(t)
    return out
