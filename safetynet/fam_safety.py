# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's tools for Agent Link: documents back after a crash or a hang
# (app_recover), FreeCAD's settings history and rollback, and macros the
# person approved. The answers are safetynet.handlers'; this layer only
# names, describes and binds them.
#
# The person's calls stay the person's: saving over their file and approving
# a macro each need their own words in chat (a typed confirm), never the
# agent's.
from agentlink.protocol import Tool

from . import handlers
from .fam_history import obj, plain

GROUP = "safety"
INFO = "SafetyNet: documents back after a crash or a hang (app_recover), FreeCAD's settings history and rollback, and macros the person approved (save, list, show, approve, run)."
# For Agent Link's echo: the Activity list's names; no WORKBENCHES — a
# safety call never moves the person's bench.
AREAS = {"app_recover": "Recovery", "pref_": "Settings", "macro_": "Macros"}
# Answered even after the person closed the document the agent worked in (as
# Agent Link's doc_open and session_state are): recovery is for exactly then.
# Agent Link's window link learns it from here (families.PINNED_FREE).
PINNED_FREE = {"app_recover"}


def tools(s):
    h = handlers.bound(s)
    st = {"type": "string"}
    return [
        Tool("macro_save", "Save this session's changing calls as a FreeCAD macro (.FCMacro in the person's macro folder): name, from / to (a checkpoint or step; the whole session by default), params { wall: 2.0, length: 60 } — the key sizes, named at the top of the macro and put in place of each value in the calls. It runs (macro_run) only once the person approves it.",
             obj({"name": st, "from": {"type": ["string", "integer"]}, "to": {"type": ["string", "integer"]}, "params": {"type": "object"}, "overwrite": {"type": "boolean"}}, ["name"]), plain(h["macro_save"])),
        Tool("macro_list", "The macros in FreeCAD's macro folder (what Macro › Macros… lists: .FCMacro and .py), each approved, changed (its code moved since the OK) or not approved. Changes nothing.", obj({}), plain(h["macro_list"])),
        Tool("macro_show", "One macro's text, its named sizes and how many calls it makes, and whether it is approved. Changes nothing.", obj({"name": st}, ["name"]), plain(h["macro_show"])),
        Tool("macro_approve", "The person approves a macro to be run by Agent Link: confirm: \"approve <name>\" typed by them, never by the agent — a macro is Python with the Mac's full reach. Approval holds until its file changes.",
             obj({"name": st, "confirm": st}, ["name", "confirm"]), plain(h["macro_approve"])),
        Tool("macro_unapprove", "Take a macro off the approved list.", obj({"name": st}, ["name"]), plain(h["macro_unapprove"])),
        Tool("macro_run", "Run an approved macro as FreeCAD's Macro dialog runs it: params { CONSTANT: value } changes its named sizes for this run. One checkpoint before; a failure part way rolls the whole run back. An unapproved or changed macro is refused.",
             obj({"name": st, "params": {"type": "object"}}, ["name"]), plain(h["macro_run"])),
        Tool("app_recover", "Documents back after a crash or a hang: action list (each document's saved copies: auto-saves, checkpoints, FreeCAD's recovery files; the document with the newest copy first) | auto { documents [{ name, label, file }], since } (the newest copy that opens, beside the file as \"<label> (recovered HH:MM)\"; one per original, a recovered copy never recovered again beside it) | accept { document, confirm: \"save over <file name>\" typed by the person } (the recovered copy saved over their file, the old one kept).",
             obj({"action": {"type": "string", "enum": ["list", "auto", "accept"]}, "documents": {"type": "array", "items": {"type": "object"}}, "since": {"type": "number"}, "document": st, "confirm": st}), plain(h["app_recover"])),
        Tool("pref_history", "The settings changes Agent Link made, newest first: change number, time, tool, path, name, from, to, and whether a restart is needed (limit, 20 by default). Changes nothing.",
             obj({"limit": {"type": "integer"}}), plain(h["pref_history"])),
        Tool("pref_rollback", "Put FreeCAD's settings back as they were before a change (to: its number from pref_history, or a time YYYYMMDD-HHMMSS): the whole settings file from its snapshot, written while FreeCAD is down — the window restarts around it in the background (save as app_restart's); the state before is snapshotted too.",
             obj({"to": {"type": ["integer", "string"]}, "save": {"type": "string", "enum": ["agent", "none"]}}, ["to"]), plain(h["pref_rollback"])),
    ]

