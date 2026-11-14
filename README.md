<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Workshop for FreeCAD

> Not affiliated with or endorsed by the FreeCAD project or the FreeCAD project association (FPA); FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

FreeCAD add-ons for making things. Each one is a plain FreeCAD add-on that
works on its own, with commands in the **Workshop** workbench and a Python
API. Each is designed agent-first: every function takes and gives plain
values in millimetres, and a refusal says what to do instead. When
[Agent Link for FreeCAD](https://github.com/jamesK1000011/AgentLink-FreeCAD) is
installed, the same functions are also tools an AI agent can call.

| Folder | Add-on | What it does |
|---|---|---|
| `Common` | Workshop Common | The Workshop workbench the others add their commands to. Records, shape helpers and fits come from [AddonKit for FreeCAD](https://github.com/jamesK1000011/AddonKit-FreeCAD), which every add-on here needs. |
| `Parts` | Workshop Parts | Standard parts made to size: Gridfinity bins and baseplates, project boxes with lids, enclosures round a circuit board. |
| `Make` | Workshop Make | Getting a part made: how each part is made (setups) and the limits it must meet, the printability check and a pass/fix verdict, mass as printed and ballast, slicing with PrusaSlicer, fits and hardware holes sized for your printer, screw threads from the standards, parts encased mid-print and the pauses to drop them in, and a wall-thickness map. Slicing with OrcaSlicer and Bambu Studio, printers, and cut and mill checks move here next. |

More are on the way: Electronics (the KiCad bridge) and Documents (assembly
manuals, BOMs, library packs).

## Data

Tables (thread sizes, bearings, the tools agents see) are data files in
each add-on's `data/` folder: versioned, checked against a schema in CI,
each entry with its source and date, under CC BY 4.0 (`LICENSE-DATA`). Your
own entries go in `~/.config/addonkit/<package>/<name>.json`; updates never
touch that folder and your entries win.

## Install

Each folder is an add-on of its own. Copy or link `Common` and the ones you
want into FreeCAD's `Mod` folder (for example `Mod/WorkshopCommon`,
`Mod/WorkshopParts`, `Mod/WorkshopMake`), plus AddonKit (`Mod/AddonKit`), then restart FreeCAD. The Claude extension of FreeCAD
Agent Link installs them for you.

## Use

- **In FreeCAD:** switch to the Workshop workbench. Each command asks for its
  values, with each one's range shown, and makes the part in the open
  document.
- **From Python or a macro:**
  ```python
  from workshop_parts import api
  api.make(App.ActiveDocument, "gridfinity_bin", {"x": 2, "y": 1, "units": 4, "magnets": True})
  ```
  ```python
  from workshop_make import api
  api.thread("M6")                                  # sizes from the standards
  api.hole(App.ActiveDocument, "Bracket", "counterbore", "M3", at=[10, 10, 5])
  ```
- **From an agent (with Agent Link):** `gen_make`, `gen_part`; `setup`, `part_spec`, `dfm_check`, `part_review`, `slice`, `mass_calibrate`, `mass_properties`, `mass_target`, `mass_ballast`, `fit`, `hw_hole`, `thread_lookup`, `thread_identify`, `thread_cut`, `hw_embed`, `hw_embed_list`, `hw_unembed`, `hw_pauses`.

## Tests

CI runs each add-on alone, then with Agent Link beside it, on the newest
FreeCAD and on 1.1 and 1.0:

```
PYTHONPATH=Common:Parts python -m unittest discover -s Parts/tests
```

## History and licence

Parts moved here from Agent Link for FreeCAD on 14 Nov 2026. Its history before
that is in that repository: `agentlink/gridfinity.py`, `agentlink/boxes.py`
and `agentlink/families/parts.py` up to commit c954763.

LGPL-2.1-or-later. The Gridfinity profile follows the open Gridfinity
system by Zack Freedman.
