<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# SafetyNet for FreeCAD

> **Written before the combine (15 Nov 2026).** This part is now inside the one Workshop add-on. Where each command sits now (FreeCAD's own workbenches, the Make workbench, Tools ▸ SafetyNet) is in the [README](../README.md#where-things-are). The install and uninstall notes below are out of date; the README has the current ones. What the part does, its Python API and its agent tools are the same.


> Not affiliated with or endorsed by the FreeCAD project or the FPA; FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

SafetyNet keeps your FreeCAD work safe, even when nobody is at the computer.
It saves checkpoints you can go back to. It keeps auto-save copies. It brings
your documents back after a crash or a hang. It logs changes to FreeCAD's
settings so you can roll them back. And it only runs a recorded macro after
you have approved it.

<!-- screenshot: the SafetyNet workbench with its toolbar and the Session panel beside the model tree -->

## Who it is for

- Anyone who has lost work to a crash and wants copies kept for them.
- People who let an AI agent work in FreeCAD through
  [Agent Link for FreeCAD](https://github.com/jamesK1000011/AgentLink-FreeCAD),
  and want every step it takes to be undoable.

You do not need to know Python. You do not need an agent.

## Install

You need FreeCAD 1.1 or newer.

**With the Addon Manager (custom repository).**

1. Open **Edit ▸ Preferences ▸ Addon Manager**.
2. Under **Custom repositories**, add
   `https://github.com/jamesK1000011/SafetyNet-FreeCAD` with branch `main`.
3. Open **Tools ▸ Addon manager**, find **SafetyNet**, and click **Install**.
4. Restart FreeCAD.

**As part of Agent Link.** The Agent Link extension for Claude Desktop
installs SafetyNet for you, beside Agent Link, in FreeCAD's `Mod` folder.
Nothing else to do.

**By hand.** Put this folder in FreeCAD's `Mod` folder as `SafetyNet` and
restart FreeCAD.

## What you see in FreeCAD

**The SafetyNet workbench.** Pick it from the workbench list. Its toolbar and
its **SafetyNet** menu have:

- **Checkpoint Now**: save a copy of the document to come back to.
- **Restore Checkpoint…**: go back to one.
- **Recovered Copies…**: after a crash, open the newest good copy beside your
  file. It is saved over your file only after you type the confirm.
- **Clean Up Copies…**: see how many old copies would go (and how many MB),
  then move them to the Trash if you say yes.
- **Settings History…** and **Roll Back Setting…**: see and undo changes to
  FreeCAD's settings. A setting read only at start applies when FreeCAD next
  opens. With Agent Link, FreeCAD restarts around the file for you.
- **Macros…**: the macros in FreeCAD's macro folder, the same ones
  Macro ▸ Macros… lists. Show one, approve it (you type the confirm), run it
  as FreeCAD does with a checkpoint before, or take the approval back. It
  also opens FreeCAD's own Macro dialog.
- **SafetyNet Panel**: the Session panel.

<!-- screenshot: the SafetyNet menu open, showing all eight commands -->

**Tools ▸ SafetyNet in every workbench.** The same commands are in the Tools
menu wherever you are, so recovery is always one click away.

**The Session panel.** Alone, it is SafetyNet's own dock, tabbed beside the
model tree. With Agent Link, it is the Session tab in Agent Link's panel.

<!-- screenshot: the Session panel with a list of checkpoints -->

Each command runs the same code an agent's tool does, as one undo step.
Panels take their colours from your FreeCAD theme.

## Where it keeps things

Everything goes under `~/AgentLink` (or the folder in `$AGENTLINK_HOME`):

- `checkpoints/` and `autosave/`: saved copies. Your own file is never touched.
- `settings/` and `settings-log.jsonl`: settings snapshots and the change log.
- `macros-approved.json`: the macros you approved.
- `hidden.json` and `reopen.json`: what to reopen after a restart.
- `safetynet/`: the copies you used lately and the copies the last crash
  brought back, so the clean-up keeps them.

Auto-save runs every 5 minutes or every 10 changes and keeps the newest 5
copies. FreeCAD's own AutoSave stays on too.

Old copies are cleaned up when SafetyNet starts and at most once a day after.
Each document keeps its newest 3 copies, and none older than 7 days. A
document that was never saved keeps its copies for 1 day. A copy is always
kept if it is the newest of its document, if the document is open, if it came
back after the last crash, if you used it in the last week, or if it is a
named checkpoint. Removed copies go to the Trash. FreeCAD's own recovery
files are left to FreeCAD. To change the numbers, set `CopiesKeep`,
`CopiesMaxAgeDays` and `ScratchMaxAgeDays` under
`BaseApp/Preferences/Mod/SafetyNet` (Tools ▸ Edit parameters).

## What an agent can do with it

When Agent Link for FreeCAD is installed, an agent gets these tools. The list
is generated from the tool definitions by `tools/gen_readme_tools.py`.

<!-- tool list as it was; the README has the current one -->
| Tool | Group | What it does |
|---|---|---|
| `history_checkpoint` | core | Save a copy of the document now, to come back to with history_restore or measure from with history_diff. |
| `history_restore` | core | Go back to a checkpoint. |
| `macro_save` | safety | Save this session's changing calls as a FreeCAD macro. |
| `macro_list` | safety | The macros in FreeCAD's macro folder, each approved, changed or not approved. |
| `macro_show` | safety | One macro's text, its named sizes and how many calls it makes, and whether it is approved. |
| `macro_approve` | safety | The person approves a macro to be run by Agent Link. |
| `macro_unapprove` | safety | Take a macro off the approved list. |
| `macro_run` | safety | Run an approved macro as FreeCAD's Macro dialog runs it. |
| `app_recover` | safety | Documents back after a crash or a hang. |
| `pref_history` | safety | The settings changes Agent Link made, newest first. |
| `pref_rollback` | safety | Put FreeCAD's settings back as they were before a change. |


The agent can never approve a macro or save over your file for you. Both
need your own typed words.

## Alone or with Agent Link

| | Alone | With Agent Link |
|---|---|---|
| Workbench, menus, Tools ▸ SafetyNet | Yes | Yes |
| Checkpoints, auto-save, recovery | Yes | Yes, and auto-save after each of the agent's changes |
| Settings rollback | Read back into the running FreeCAD | FreeCAD restarts around the file |
| Session panel | Its own dock | A tab in Agent Link's panel |
| Agent tools above | No | Yes |

SafetyNet never imports Agent Link. Only `safetynet/agentlink_families.py`
and the `fam_*` modules it loads do, and only Agent Link loads them. Without
SafetyNet, Agent Link has FreeCAD's undo only.

## Uninstall

- **Addon Manager**: Tools ▸ Addon manager ▸ SafetyNet ▸ Uninstall, then
  restart FreeCAD.
- **By hand, or installed by the Agent Link extension**: delete the
  `SafetyNet` folder from FreeCAD's `Mod` folder, and restart FreeCAD.
- **Your files**: the saved copies, settings snapshots and approvals under
  `~/AgentLink` (see [Where it keeps things](#where-it-keeps-things)) are
  yours to keep or delete. Your own documents were never changed.

## Privacy

SafetyNet has no telemetry and makes no network connection. Everything it
keeps stays on your computer under `~/AgentLink`. A macro runs only after you
approved it yourself. With Agent Link, what the agent reads goes to the AI
provider your MCP client uses, under that provider's terms.

## For developers

```
AGENTLINK_HOME=$(mktemp -d) python3 -m unittest discover -s tests
python3 tools/gen_readme_tools.py   # refresh the tool list above
```

## Licence

LGPL-2.1-or-later (`LICENSE`). Split out of Agent Link for FreeCAD, under the
same licence. Each file's licence is stated in its header or in `REUSE.toml`.

## Credits

- Icons are hand-drawn in FreeCAD's icon style. Their designs follow glyphs
  from [Tabler Icons](https://tabler.io/icons) (MIT) and
  [Pictogrammers Material Design Icons](https://pictogrammers.com) (Apache-2.0).
  See `safetynet/icons/CREDITS.md` and the texts in `LICENSES/`.
- FreeCAD's own icons are used by name from FreeCAD.
