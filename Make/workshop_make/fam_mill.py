# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts milled from stock: can the setup's tool directions reach every face
# (one not reachable from any is an undercut), are the inside vertical
# corners as round as the least tool, are holes and pockets within the
# tool's reach and not too deep for their width, are the walls thick enough
# for the material, does the part fit the stock. Then STEP and a setup
# sheet. A face lying on the stock's own outside counts as the stock's.
# Rules of thumb, said as assumed: the machinist's own figures win.
# Agent Link's binding: the handlers in handlers/mill.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import mill as H

GROUP = "mill"
INFO = "Milled parts: reach from the setup's tool directions (undercuts), inside corners, deep holes and pockets, thin walls, stock; STEP and a setup sheet."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("mill", handlers.bound(session, H.HANDLERS))
