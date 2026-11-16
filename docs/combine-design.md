<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# One add-on: Workshop and SafetyNet combined

Roadmap v19, items 9–13. Workshop's four add-ons (Parts, Make, Electronics,
Documents) and SafetyNet become **one** add-on, *Workshop*. Agent Link stays
the separate thin hub; ScanRuler-FreeCAD and Texturizer-FreeCAD stay
separate. Each feature moves into the FreeCAD workbench it belongs in through
`Gui.addWorkbenchManipulator`. Only what has no home in FreeCAD keeps a
workbench of its own: one small **Make** workbench.

Rule: **fold first, icon second.** Where a feature's controls can join a
FreeCAD command and its task pane, they go there with no new icon. Where
they can't, the feature gets its own icon right after the FreeCAD tool it
builds on, and opens its own panel. Few injected icons; menus carry the rest.

## 1. Package layout

The repository root is the Mod folder: one `package.xml`, one `Init.py`, one
`InitGui.py`, installed as `Mod/Workshop`.

```
package.xml  Init.py  InitGui.py  README.md  CHANGELOG.md  FILES
LICENSE  LICENSE-DATA  LICENSES/  REUSE.toml
workshop/              the add-on's own layer: VERSION, the Make workbench,
  workbench.py           the placement table and manipulator, the one
  placement.py           agentlink_families (all tools), the shared helper
  agentlink_families.py  files Agent Link vendors (layout.py)
  layout.py  icons/
workshop_parts/        moved as they were (from Parts/, Make/, Electronics/,
workshop_make/         Documents/): same package names, so imports, the
workshop_electronics/  data-override folders (~/.config/<package>) and
workshop_documents/    pickled tool data keep working
safetynet/             SafetyNet's package, brought in from SafetyNet-FreeCAD
tests/                 tests/test_*.py for the add-on as a whole;
  parts/ make/ electronics/ documents/ safetynet/   each feature's own tests, moved
tools/gen_readme_tools.py   one README tool list for all families
docs/
```

Package names are kept on purpose (move, don't rewrite). No document stores a
Python proxy from these packages (records are plain `App::FeaturePython`
holders), so even a later rename wouldn't break saved files. Keeping the names
just avoids touching 30 k lines.

**Shared helpers.** Agent Link vendors `layout.py` (the list is
`scripts/sync_shared.py` in Agent Link). After the combine there is one copy,
`workshop/layout.py`, kept equal to Agent Link's. The old
`workshop_make/layout.py`, `workshop_documents/layout.py` and
`safetynet/layout.py` become three-line aliases (`sys.modules[__name__] =
workshop.layout`), so `from . import layout` still works and there is still
one module object. `tooldata.py`, identical in three packages, gets the same
treatment. Files that only share a name and have since diverged (`geo`,
`records`, `refusal`, `theme`, `datafiles`, …) stay where they are. Merging
them would be rewriting, and that's for later.
`tests/test_shared.py` fails when a vendored file differs from Agent Link's
copy (skipped when Agent Link isn't checked out beside this repo).

## 2. What moves where

Anchors are FreeCAD 1.1 command names. A manipulator can only *insert before*
an item or *append* to a menu or toolbar, so "after X" is written as "before
the item that follows X". If an anchor isn't in a workbench, nothing is added
there, and that is how each entry stays in its own workbench.

| Current command | New home | How |
|---|---|---|
| Workshop_Parts_GridfinityBin, …GridfinityBaseplate, …ProjectBox, …BoardBox | Part and Part Design | One dropdown, *Standard parts* (`Workshop_Parts_Group`): own icon before Part_Primitives (Part) and before PartDesign_CompPrimitiveAdditive (Part Design); menu items before Part_Primitives |
| Workshop_Make_Hole (Hole for hardware) | Part Design | Own icon after PartDesign_Hole (before PartDesign_Groove), toolbar and menu. **Not folded** (see 2.1) |
| Workshop_Make_ThreadLookup | Part Design | Menu only, after Hole for hardware |
| Workshop_Make_DfmCheck, …PartReview, …MassProperties | Part Design / beside Measure | One dropdown, *Checks* (`Workshop_Make_Checks`), own icon before Part_CheckGeometry; Mass properties also in the menu before Std_Measure |
| Workshop_Electronics_ImportBoard (KiCad Board…) | File ▸ Import area | Menu only, before Std_Export, so it sits after Import |
| Workshop_Documents_Drawing | TechDraw | Own icon before TechDraw_RedrawPage (after the page commands); menu too |
| Workshop_Documents_Exploded, …PatentFigures, …PatentDraft | TechDraw | Menu only, after Drawing |
| Workshop_Documents_LibraryPack | File ▸ Export area | Menu only, before Std_MergeProjects (after Export). Behaviour unchanged: ScanRuler's pack first |
| Workshop_Documents_Panel (Manual) | Make workbench | Toolbar *Panels* and menu |
| Materials | Make workbench | Not a command: the Materials tab stays in the Make panel; mass and material services unchanged |
| SafetyNet_Checkpoint, _Restore, _Recover, _SettingsHistory, _Rollback, _Macros, _CleanUp, _Panel | Tools ▸ SafetyNet | The submenu `SafetyNet_Menu` appended to &Tools in every workbench, as before. Recovered Copies also before Std_Import (File) |
| Workshop_Make_NewSetup, _AddBody, _RemoveSetup, _FitSize, _Calibrate, _Embed, _Pauses, _Slice, _CutExport, _MillExport, _PrinterStatus, _PrinterSend, _Panel | Make workbench | Toolbars Setup, Fits, Hardware, Output, Printer, Panels |

Workbenches removed: Workshop Parts, Workshop Electronics, Workshop Documents,
SafetyNet. Workbench kept: `WorkshopMakeWorkbench` (shown as **Make**). Its
class name is kept, so the panel layout and Agent Link's tab placement still
match. The Make panel (Setups, Materials, Fits, Review) and the Manual panel
open in it. SafetyNet's Session panel opens in whatever workbench is active
(as before); when Agent Link hosts it as a tab, the tab belongs to Make.

Four injected icons: Standard parts (shown in both Part and Part Design),
Checks, Hole for hardware and Drawing.

The echo's workbench per tool (each family's `WORKBENCHES`) follows the
buttons: `gen_`, `hw_hole`, `thread_lookup`, `dfm_check`, `part_review`,
`mass_properties`, `board_`, `printed_channel` → PartDesignWorkbench;
`drawing_` → TechDrawWorkbench (unchanged); the rest of Make → Make; `kicad_`
has none, because the File menu is in every workbench.

### 2.1 Hole for hardware and PartDesign Hole's task panel

PartDesign Hole's task panel is C++ (`TaskHoleParameters`). FreeCAD has no
Python API for adding a section to another command's task panel. The only
route from Python would be to find the panel's widgets with Qt and insert a
box into its layout while a Hole is in edit. That depends on private object
names and layouts that change between releases. So the fold **isn't done**:
Hole for hardware keeps its own panel and gets its own icon right after
PartDesign_Hole. What it adds on top of FreeCAD's Hole (printer allowance,
nut trap, insert and magnet pockets) is unchanged (`workshop_make/pdhole.py`),
and the Hole it makes can still be edited in FreeCAD's own panel.

## 3. SafetyNet's repository

SafetyNet-FreeCAD stays as it is, as history (last commit 25ca601). Its code
is copied in here unchanged except: no workbench of its own
(`safetynet/workbench.py` keeps the start-up work, the Tools-menu fallback
and the commands, minus the workbench class), and `agentlink_families.py` →
`families.py` (see 4). Both are LGPL-2.1-or-later. The launcher stops
installing `Mod/SafetyNet` and sets aside a copy left in Mod (RETIRED, like
AddonKit and WorkshopCommon), together with WorkshopParts, WorkshopMake,
WorkshopElectronics and WorkshopDocuments. Two copies of SafetyNet would
register its commands twice and offer its tools twice.

## 4. Agent tools

One family module, `workshop/agentlink_families.py`, which Agent Link finds
by its convention. It imports each package's `families.py` (the old
`agentlink_families.py`, renamed so it isn't found a second time) and joins
their `FAMILIES`. Each part loads on its own: one that fails is logged and
left out, the others still load. Every package's guides folder is
registered. **Tool names are unchanged**, so Agent Link and existing prompts
keep working. Services, hooks and hosted tabs (print_pauses, mass and
material services, library_pack, checkpoints, reopen, the panels) register
as before, from the same code. No new token cost: nothing is added to any
tool's description.

## 5. Settings

The only parameter group of the five is `Mod/SafetyNet` (the clean-up
schedule). It's read and written as before. The Workshop packages keep no
`Mod/Workshop*` groups; their data overrides stay under
`~/.config/<package>`, and the package names don't change. There's nothing
to migrate, and no old key stops being read. A later `Mod/Workshop` group
would read `Mod/SafetyNet` and the old names as fallbacks first.

## 6. Test plan

- Each feature's tests, moved to `tests/<feature>/`, pass unchanged except
  for paths (ROOT is the repository root). CI runs `tests/` and then each
  sub-folder, alone and with Agent Link beside it.
- `tests/test_loads.py`: `InitGui.py` run the way FreeCAD runs it, under
  stand-ins. One workbench (Make), every command registered once, no Agent
  Link import, the manipulator added (or the Qt fallback without one).
- `tests/test_placement.py`: every command of every package has a home in
  the table. The manipulator's `modifyToolBars` and `modifyMenuBar` dicts
  have the expected shape, insert after the right FreeCAD command, and inject
  only the planned icons. A stand-in Gui applies them to model PartDesign,
  Part, TechDraw and File menus/toolbars and checks where each lands. There's
  no fold test, because nothing is folded (2.1).
- `tests/test_shared.py`: the vendored copies match Agent Link's (skipped
  without it); the old module names alias the one copy.
- `tests/test_families.py`: the single family module joins every family,
  tool names match the old set exactly, and no other `agentlink_families`
  module is left in the tree.
- `tests/test_release.py`, `tests/test_files.py`: one package.xml (one
  workbench, matching InitGui), licences, FILES current.
- Live (on the Mac, FreeCAD 1.1.3): the manipulator anchors, the dropdowns,
  the Tools ▸ SafetyNet submenu, the Make workbench and its two panels.
