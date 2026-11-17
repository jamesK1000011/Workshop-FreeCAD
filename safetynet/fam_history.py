# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's history tools for Agent Link: checkpoints as saved copies, to
# come back to past FreeCAD's undo stack and across restarts. They join
# Agent Link's core group beside history_undo, history_redo and
# history_diff. The answers are safetynet.handlers'; this layer only names,
# describes and binds them.
from agentlink.protocol import Tool, ToolError

from . import handlers
from .refusal import Refused

GROUP = "core"
INFO = "The session, groups, guides, batches, undo, soundness, export. Always listed."
# For Agent Link's echo: the Activity list's name; no WORKBENCHES — a safety
# call never moves the person's bench.
AREAS = {"history_": "History"}


def obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


def plain(fn):
    """SafetyNet's refusal as Agent Link's."""
    def run(a):
        try:
            return fn(a)
        except Refused as e:
            raise ToolError(e.code, e.message) from None
    return run


def tools(session):
    h = handlers.bound(session)

    return [
        Tool("history_checkpoint", "Save a copy of the document now. name: optional; named copies are kept. Come back to the copy with history_restore, or measure from it with history_diff { since }. This works past the 20-step undo of FreeCAD, and across restarts. list: true lists the checkpoints of this document. The file of the person is never touched.",
             obj({"name": {"type": "string"}, "list": {"type": "boolean"}}), plain(h["history_checkpoint"])),
        Tool("history_restore", "Go back to a checkpoint: its id (cp3), or its name. While the undo stack reaches the checkpoint, it goes back by undo. Else it reopens the saved copy of the checkpoint. The state before is checkpointed first, so you can undo a restore the same way.",
             obj({"checkpoint": {"type": "string"}}, ["checkpoint"]), plain(h["history_restore"])),
    ]
