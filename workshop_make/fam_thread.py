# SPDX-License-Identifier: LGPL-2.1-or-later
# Screw threads: the standards' sizes, what size a cylindrical face is, and
# a thread on a hole through FreeCAD's own PartDesign Hole (a cosmetic
# thread — the hole at its tapping size, the thread recorded — or a
# modelled one, cut into the part).
# Agent Link's binding: the handlers in handlers/thread.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink import facepick
from agentlink import hooks as _hooks
from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import thread as H

GROUP = "thread"
WORKBENCHES = {"thread_lookup": "PartDesignWorkbench"}  # where its menu item is (after Hole for hardware)
COMMANDS = {"thread_lookup": "Workshop_Make_ThreadLookup"}  # the button that does the same
INFO = "Screw threads: metric and Unified sizes from the standards, what size a hole or shaft is, and threads cut on holes."

# Add-ons that read a thread off a scan register a reader of kind
# "thread_scan" with Agent Link: f(session, args) -> its reading.
# thread_identify { scan } asks the first, so a CAD face and a scanned
# thread are named by one tool.
SCAN_READERS = _hooks.readers("thread_scan")
handlers.lend(H, facepick=facepick, SCAN_READERS=SCAN_READERS, ToolError=ToolError)


def tools(session):
    return tooldefs.build("thread", handlers.bound(session, H.HANDLERS))
