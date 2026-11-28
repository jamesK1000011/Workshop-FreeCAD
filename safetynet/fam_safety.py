# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's tools for Agent Link: documents back after a crash or a hang
# (app_recover), FreeCAD's settings history and rollback, and macros the
# person approved. The answers are safetynet.handlers'; this layer only
# names, describes and binds them.
#
# The person's calls stay the person's: saving a recovered copy over their
# file and approving a macro need the person's approval, approve_file or
# approve_code, which they set in the client's tool permissions (Agent
# Link's hooks.person_ok; the owner, 18 Nov 2026).
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
    try:
        from agentlink import hooks

        for n in ("macro_approve", "macro_unapprove", "macro_run", "app_recover"):
            getattr(hooks, "keep_unextended", lambda _n: None)(n)  # no other add-on wraps these
        handlers.PERSON_OK = getattr(hooks, "person_ok", None)
        handlers.APPROVAL_IN_WINDOW = getattr(hooks, "approval_in_window", None)
    except ImportError:
        pass
    st = {"type": "string"}
    return [
        Tool("macro_save", "Save the changing calls of this session as a FreeCAD macro (.FCMacro in the macro folder of the person). name: the name of the macro. from / to: a checkpoint or step; the whole session by default. params { wall: 2.0, length: 60 }: the key sizes. They are named at the top of the macro and put in place of each value in the calls. It runs (macro_run) only after the person approves it. Macro › Macros… of FreeCAD runs it by hand too.",
             obj({"name": st, "from": {"type": ["string", "integer"]}, "to": {"type": ["string", "integer"]}, "params": {"type": "object"}, "overwrite": {"type": "boolean"}}, ["name"]), plain(h["macro_save"])),
        Tool("macro_list", "List the macros in the macro folder of FreeCAD: .FCMacro and .py, as Macro › Macros… lists them. Each one is approved, changed (its code moved since the OK) or not approved. Changes nothing.", obj({}), plain(h["macro_list"])),
        Tool("macro_show", "Show the text of one macro, its named sizes, how many calls it makes, and whether it is approved. Changes nothing.", obj({"name": st}, ["name"]), plain(h["macro_show"])),
        Tool("macro_approve", "Ask for the person's approval to run a macro. name: the name of the macro. A macro is Python with the full reach of the Mac. Show macro_show to the person first. The tool never approves by itself. The first call answers pending with the approve_code arguments: name, source, version (the sha256) and author. Call approve_code with them. The person sets approve_code in the client's tool permissions. A typed confirm is not taken. After the approval, macro_list shows the macro approved. The approval holds until its file changes. Without Agent Link, the tool refuses.",
             obj({"name": st}, ["name"]), plain(h["macro_approve"])),
        Tool("macro_unapprove", "Take a macro off the approved list.", obj({"name": st}, ["name"]), plain(h["macro_unapprove"])),
        Tool("macro_run", "Run an approved macro as the Macro dialog of FreeCAD runs it. params { CONSTANT: value } changes its named sizes for this run. One checkpoint is made before: history_restore { checkpoint } goes back to before the run. A failure part way rolls the whole run back. An unapproved or changed macro is refused.",
             obj({"name": st, "params": {"type": "object"}}, ["name"]), plain(h["macro_run"])),
        Tool("app_recover", "Get documents back after a crash or a hang. action list: the saved copies of each document (auto-saves, checkpoints, FreeCAD's recovery files). The document with the newest copy comes first. limit: how many documents (10; 0 gives all). document: only the documents whose name or label holds this text. total: how many documents have copies; matched: how many hold the text; more: how many are not shown. A recovered copy is listed only with changes of its own. action auto { documents [{ name, label, file }], since }: only the documents open at the crash. For each, the newest copy that opens comes back, beside the file, as \"<label> (recovered HH:MM)\". There is one per original, and a recovered copy is never recovered again beside it. A recovered copy that was open comes back only from changes made in it after it opened. One with no such changes (or modified: false) is named in notRecoveredAgain. It is never a copy of a copy. A saved file of the person that was unchanged at the crash is not recovered. That is: file given, and modified false or not said. It opens again from its own file as itself, once, and is named in reopened. It is left alone when it is open already. It comes back from a copy only in two cases. A copy newer than its file holds more, or the file will not open. Temporary recovered copies older than the crash (since), that FreeCAD opened again unchanged, are closed. Copies opened are marked unchanged, so they are not read as changed or recovered again. action accept { document }: it saves the recovered copy over their file, and the old one is kept. It needs the person's approval: the first call answers pending with the approve_file arguments. Call approve_file with them, then call again. confirm is only for SafetyNet without Agent Link. A recovered copy opens beside the files of the person, which stay untouched. more: how many older documents are not shown; limit 0 gives all. lostMinutes: the minutes of changes after the copy, when since is given. why in reopened: savedUnchanged, alreadyOpen or besideCopy (the file as saved opened beside its recovered copy, which holds the changes after the save). why in failed: noSavedCopy, or openFailed with errors { source, time, error }. accept keeps the old file at previousFile.",
             obj({"action": {"type": "string", "enum": ["list", "auto", "accept"]}, "documents": {"type": "array", "items": {"type": "object"}}, "since": {"type": "number"}, "document": st, "confirm": st, "limit": {"type": "integer"}}), plain(h["app_recover"])),
        Tool("pref_history", "List the settings changes that Agent Link made, newest first. Each holds: change number, time, tool, path, name, from, to, and whether a restart is needed. limit: 20 by default. pref_rollback { to: change } puts the settings back as before that change. Changes nothing.",
             obj({"limit": {"type": "integer"}}), plain(h["pref_history"])),
        Tool("pref_rollback", "Put the settings of FreeCAD back as they were before a change. to: its number from pref_history, or a time YYYYMMDD-HHMMSS. The whole settings file comes back from its snapshot, written while FreeCAD is down. The window restarts around it in the background. save: as app_restart's. The state before is snapshotted too, so rolling back to the newest change undoes a rollback. With SafetyNet alone in the window (no restart), the snapshot is read into the running settings (inPlace: true) and a setting read only at start takes effect when FreeCAD next opens. Without a window, restarting: hidden means the hidden FreeCAD restarts at once and reads the settings when it next opens.",
             obj({"to": {"type": ["integer", "string"]}, "save": {"type": "string", "enum": ["agent", "none"]}}, ["to"]), plain(h["pref_rollback"])),
    ]

