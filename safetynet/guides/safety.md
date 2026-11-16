# Keeping the work safe (SafetyNet)
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

## checkpoints
- `history_checkpoint { name }` before a risky change (a big boolean, a fillet that may fail, a run of many steps): a saved copy under `~/AgentLink/checkpoints`, kept past FreeCAD's 20-step undo and across restarts. Named ones are kept; the last 10 unnamed ones are.
- `history_restore { checkpoint }` goes back: by undo while the stack reaches it, else from the copy (the state before is checkpointed first). `history_diff { since: "cp3" }` says what changed since one.
- A copy is also saved every 5 minutes or 10 changes (`~/AgentLink/autosave`), and before a heavy job, a macro run and a window restart.

## after a crash or a hang
- `app_recover` lists each document's saved copies, newest first. `action auto` opens the newest that opens, beside the person's file as "<label> (recovered HH:MM)" — their file is untouched.
- Saving a recovered copy over the file is the person's call: `accept { document, confirm: "save over <file name>" }` with their own words.

## settings
- Every `pref_set`, `pref_reset`, `pref_pack` and `pref_import` is logged with a snapshot of the whole settings file before it. `pref_history` lists them; `pref_rollback { to }` restarts FreeCAD around the snapshot.

## macros
- `macro_save { name, from, params }` keeps this session's steps as a FreeCAD macro with its key sizes named at the top. It runs (`macro_run`) only after the person approves it (`macro_approve` with their typed confirm); a change to its file needs approving again. Never approve one yourself.
