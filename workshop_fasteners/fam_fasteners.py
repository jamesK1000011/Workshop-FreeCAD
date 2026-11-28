# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's binding of the fasteners tools (handlers.py, no Agent Link
# import there), loaded only when Fasteners Workbench is installed
# (families.py). Fasteners Workbench is Shai Seger's add-on; its
# screw_maker is Ulrich Brammer's. Its code runs; none of it is copied.
# Also: Hole for Hardware (hw_hole) gains screw: the matching screw from
# Fasteners put in the hole — an extension, so without Fasteners hw_hole
# carries no word of it.
from agentlink.protocol import ToolError

from workshop import tooldata

from . import api, detect, handlers
from . import fs

GROUP = "fasteners"
INFO = "Bolts, screws, nuts, washers, inserts and pins from Fasteners Workbench, attached to holes; their sizes, lengths, BOM and 3D-print thread settings (" + detect.CREDIT + ")."
CREDIT = detect.CREDIT
# The live echo in the window: Fasteners' workbench comes up (its class
# name, from its InitGui.py) and the button that does the same lights.
WORKBENCHES = {"fastener_": detect.CLASSNAME}
COMMANDS = {
    "fastener_types": "Fasteners_Search",
    "fastener_set": "Fasteners_ChangeParameters",
    "fastener_list": "Fasteners_BOM",
    "fastener_print": "Fasteners_3dPrintSettings",
}
AREAS = {"fastener_": "Fasteners"}

handlers.ToolError = ToolError

SCREW = {
    "description": "The matching screw from Fasteners Workbench put in the hole: true, or {type (ISO4762 …), length (mm; else from the hole), thread simple|real}.",
    "anyOf": [{"type": "boolean"}, {"type": "object", "properties": {"type": {"type": "string"}, "length": {"type": "number"}, "thread": {"type": "string", "enum": ["simple", "real"]}}, "additionalProperties": False}],
}


def command_for(name, args):
    """The button for a call whose button depends on what it asks."""
    a = args or {}
    if name == "fastener_add" and a.get("type"):
        return "FS" + str(a["type"])  # Fasteners' own Add command for that type
    if name == "fastener_set":
        if a.get("restore") and not a.get("objects"):
            return "Fasteners_RestoreProperties"
        keys = {k for k in a if k not in ("objects", "object")}
        if keys == {"invert"}:
            return "Fasteners_Flip"
        if keys == {"edge"}:
            return "Fasteners_Move"
    if name == "fastener_list" and not a.get("sheet"):
        return None
    return COMMANDS.get(name)


def WORDS(name, args, body):
    """The window's words for fastener_add (Agent Link's echo): what was put
    where, not only "Added Fasteners" (window review round 6, 5011). None
    for another call. Never raises."""
    if name != "fastener_add" or not isinstance(body, dict) or body.get("error"):
        return None
    try:
        made = [m for m in (body.get("made") or []) if isinstance(m, dict)]
        if not made:
            return None
        m = made[0]
        s = "Added " + str(m.get("type") or "a fastener")
        if m.get("size"):
            s += " " + str(m["size"])
        if m.get("length") is not None:
            s += " x " + str(m["length"])
        if m.get("attachedTo"):
            s += " in " + str(m["attachedTo"])
        if len(made) > 1:
            s += f" and {len(made) - 1} more"
        return s[:120]
    except Exception:  # noqa: BLE001
        return None


def tools(session):
    return tooldata.build(tooldata.here(__file__), GROUP, {k: (lambda a, fn=fn: fn(session, a)) for k, fn in handlers.HANDLERS.items()}, "Workshop · Fasteners bridge")


def hole_after(a, out, session):
    """hw_hole's answer with the screw added, when one was asked for."""
    spec = a.get("screw")
    if not spec or not isinstance(out, dict) or "body" not in out:
        return None
    try:
        out.update(api.hole_screw(session.doc, a, out, spec))
    except fs.Missing as e:
        out["screwNote"] = {"reason": "missing", "error": e.message}
    return out


def _extend():
    from agentlink import hooks

    if hasattr(hooks, "extend_tool"):
        hooks.extend_tool("hw_hole", {"screw": SCREW}, after=hole_after,
                          describe="screw: the matching screw from Fasteners Workbench in the hole (true or {type, length}).")


try:
    _extend()
except Exception:  # noqa: BLE001 — an Agent Link without the hook: the tools still load
    pass
