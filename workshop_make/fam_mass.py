# SPDX-License-Identifier: LGPL-2.1-or-later
# Mass, centre of mass and inertia of each body in its material — as
# printed when it is in a print setup (walls and infill), else solid — with
# the parts encased in it (magnets from gen_make, ballast cut here) counted;
# how far a body is from a target; and ballast pockets that bring it there.
# Agent Link's binding: the handlers in handlers/mass.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.families import material as matfam
from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import mass as H
from .words import words as WORDS  # the window's words with the answer's figure (Agent Link's echo)

GROUP = "mass"
WORKBENCHES = {"mass_properties": "PartDesignWorkbench"}  # where its button is (Make Checks, beside Check Geometry)
COMMANDS = {"mass_properties": "Workshop_Make_MassProperties"}  # the button that does the same
INFO = "Mass, centre of mass and inertia (as printed or solid, encased parts counted), distance from a target, ballast pockets to reach it."

handlers.lend(H, matfam=matfam, ToolError=ToolError)


def tools(session):
    return tooldefs.build("mass", handlers.bound(session, H.HANDLERS))
