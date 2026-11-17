# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tool for frames of straight members (fea_frame): beam
# elements solved by CalculiX — beams, rafters, portal frames, trusses,
# shelving. Its own deck (frame.py), not FreeCAD's FEM, so it is Make's;
# it sits in the strength group beside FreeCAD's FEM tools. A thin layer;
# loaded by Agent Link only. Moved from Agent Link's strength family on
# 14 Nov 2026.
# Agent Link's binding: the handlers in handlers/frame.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.families import material as matfam
from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import frame as H

GROUP = "strength"
# Activity and caption words (agentlink/activity.py templates; see fam_make).
PHRASES = {"fea_frame": ["Solving the frame in the background if {job}",
                         "Solved the frame of {bodies} under {loadN} N: {verdict}; sags {deflectionMaxMm} mm",
                         "Solved the frame of {bodies} under {loadN} N: {verdict}",
                         "Solved the frame under {loadN} N: {verdict}; sags {deflectionMaxMm} mm",
                         "Solved the frame under {loadN} N: {verdict}",
                         "Solved the frame under {loadTotalN} N: least safe member {worst}", "Solved the frame under {loadTotalN} N"]}
# What the frame was made of (its bodies' labels, when made from bodies), to
# select in the window (Agent Link's echo: SELECTS, the answer's key).
SELECTS = {"fea_frame": "bodies"}
INFO = "Strength by finite elements (Gmsh and CalculiX): set up a body, hold faces, load them, solve for stress, displacement and safety factor."

handlers.lend(H, matfam=matfam, ToolError=ToolError)


def tools(session):
    return tooldefs.build("strength", handlers.bound(session, H.HANDLERS))
