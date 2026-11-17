# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents: Agent Link's tools, their definitions in data/tools.json
# (moved from Agent Link for FreeCAD on 14 Nov 2026). Loaded by Agent Link only.
# Drawings and documents from the bodies: a TechDraw page of standard views
# (TechDraw's template, title block, views and dimensions, editable there;
# exported as SVG, PDF and DXF by TechDraw where it can), an
# assembly manual with exploded steps and a bill of materials, and patent
# figures with reference numerals and a draft to start a patent attorney's
# work from. Where TechDraw cannot export (PDF and SVG with no window), the
# files are written by sheets.py from Open CASCADE's exact hidden-line
# removal (what TechDraw itself uses).
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
# TechDraw while these run (the page opens there); a button lit only where
# TechDraw has one that does the same (drawing_exploded and the patent tools
# have none there; their buttons are on the Workshop Documents bench).
WORKBENCHES = {"drawing_": "TechDrawWorkbench"}
COMMANDS = {"drawing_make": "TechDraw_ProjectionGroup"}
PAGES = ("drawing_",)
# drawing_make's file is written (an absolute one too): Agent Link checks it
# as it checks every writer's path (the home folder or the session's, never a
# hidden folder or a script).
WRITERS = {"drawing_make"}


def WORDS(name, args, body):
    """The window's words for drawing_exploded (Agent Link's echo): the
    steps, the bill of materials and what the page shows, not only
    "Drawing exploded" (window round 8; 15-021 had no counts). None for
    another call. Never raises."""
    if name != "drawing_exploded" or not isinstance(body, dict) or not isinstance(body.get("steps"), list):
        return None
    try:
        n, items = len(body["steps"]), len(body.get("bom") or [])
        title = (args or {}).get("title") or (args or {}).get("name") or "the assembly"
        s = f"Drew the manual of {title}: {n} step{'' if n == 1 else 's'}, {items} BOM item{'' if items == 1 else 's'}"
        if isinstance(body.get("explode"), (int, float)):
            s += f", parts lifted {body['explode']:g} mm"
        if body.get("explodedView"):
            s += f"; Assembly view {body['explodedView']}"
        elif body.get("page"):
            s += f"; page {body['page']} shows step {n}"
        return s[:160]
    except Exception:  # noqa: BLE001
        return None


INFO = "Drawings and documents: dimensioned views as a TechDraw page with SVG, PDF and DXF; assembly manuals with exploded steps and a bill of materials; patent figures and a draft."

handlers.lend(H, ToolError=ToolError, M=M, picks=picks)


def tools(session):
    return tooldefs.build(DATA, GROUP, handlers.bound(session, H.HANDLERS), "Documents")
