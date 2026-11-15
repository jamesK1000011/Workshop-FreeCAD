# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts cut from sheet (laser, waterjet, plasma, router): is the body a
# sheet part — two parallel flat faces a constant thickness apart and every
# other face square to them — and can the setup's machine cut its profile:
# webs, slots and holes against the least feature for the machine, the
# material and the thickness; a router's inside corners against its
# cutter; plasma's holes against the thickness; the part against the
# sheet. Then the flat profiles, laid out in rows on the sheet, as DXF and
# SVG. The least features are rules of thumb, said as assumed: the cutting
# shop's own figures win.
# Agent Link's binding: the handlers in handlers/cut.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import cut as H

GROUP = "cut"
INFO = "Sheet parts for laser, waterjet, plasma and router: the cut check, and DXF/SVG profiles laid out on the sheet."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("cut", handlers.bound(session, H.HANDLERS))
