# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents: Agent Link's tools, their definitions in data/tools.json
# (moved from Agent Link for FreeCAD on 14 Nov 2026). Loaded by Agent Link only.
# Drawings and documents from the bodies: a dimensioned sheet of standard
# views (a TechDraw page in the document, and SVG, PDF and DXF files), an
# assembly manual with exploded steps and a bill of materials, and patent
# figures with reference numerals and a draft to start a patent attorney's
# work from. The views are Open CASCADE's exact hidden-line removal (what
# TechDraw itself uses), written by sheets.py, so the files come out the same
# with or without the GUI.
# Agent Link's binding: the handlers in handlers/drawing.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.families import measure as M
from agentlink.families import picks
from agentlink.protocol import ToolError

from workshop_documents import tooldata as tooldefs

from . import handlers
from .handlers import drawing as H

DATA = tooldefs.here(__file__)
GROUP = "drawing"
WORKBENCHES = {"drawing_": "TechDrawWorkbench"}
PAGES = ("drawing_",)
INFO = "Drawings and documents: dimensioned views as a TechDraw page with SVG, PDF and DXF; assembly manuals with exploded steps and a bill of materials; patent figures and a draft."

handlers.lend(H, ToolError=ToolError, M=M, picks=picks)


def tools(session):
    return tooldefs.build(DATA, GROUP, handlers.bound(session, H.HANDLERS), "Documents")
