# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts encased mid-print: a pocket for a nut, magnet, bearing, insert,
# weight or any box or cylinder, sized with the printer's fit calibration,
# its top on the print setup's layer grid and a roof over it; the print
# pauses after the layer at the pocket's top, the part goes in, and the
# next layers close over it. The records are kept in the session's
# meta[label]["embeds"] (what slicing reads for its pauses) and in the
# document, so they are saved with it.
# Agent Link's binding: the handlers in handlers/embed.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import embed as H

GROUP = "embed"
INFO = "Parts encased mid-print: nut, magnet, bearing, insert and weight pockets with a roof, and the pauses to drop them in."

handlers.lend(H, ToolError=ToolError)


pauses_for = H.pauses_for  # Agent Link's "print_pauses" service (agentlink_families)


def tools(session):
    # Slicing asks for the pauses through Agent Link's services; offered on
    # every server built, so it is there whatever ran before.
    try:
        from agentlink import hooks

        hooks.provide("print_pauses", pauses_for)
    except ImportError:
        pass
    return tooldefs.build("embed", handlers.bound(session, H.HANDLERS))
