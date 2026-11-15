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
| `Common` | Workshop Common | No longer needed: each add-on has its own workbench. Its last release is a stub that registers nothing; remove it. |
| `Parts` | Workshop Parts | Standard parts made to size: Gridfinity bins and baseplates, project boxes with lids, enclosures round a circuit board. |
| `Make` | Workshop Make | Getting a part made: how each part is made (setups) and the limits it must meet, the printability check and a pass/fix verdict, mass as printed and ballast, slicing with PrusaSlicer, fits and hardware holes sized for your printer, screw threads from the standards, parts encased mid-print and the pauses to drop them in, and a wall-thickness map; slicing with PrusaSlicer, OrcaSlicer and Bambu Studio (their command lines and presets from [Agent Link for OrcaSlicer](https://github.com/jamesK1000011/AgentLink-OrcaSlicer), installed beside it), printers on the network (OctoPrint, Moonraker, PrusaLink); sheet parts checked and laid out as DXF/SVG for laser, waterjet, plasma or router; milled parts checked with STEP and a setup sheet; frames by beam elements (CalculiX); and strength as printed: the tension across the layers and the print's walls and infill read back on Agent Link's FEM study. |
| `Electronics` | Workshop Electronics | KiCad boards read without KiCad (outline, cut-outs, mounting holes, tall parts with their heights), enclosures made round them with standoffs and openings for the edge connectors, PCB order packages for JLCPCB, PCBWay or OSH Park (nothing uploaded or ordered), and channels inside printed parts for wire or conductive traces with their resistance.  |
| `Documents` | Workshop Documents | Documents for made parts: drawing sheets (standard views, sections, dimensions with ISO 286 fits, hole callouts, a title block) as SVG, PDF, DXF and a TechDraw page; assembly manuals with exploded steps and a bill of materials; patent figures and a draft for an attorney's review; library packs of STEP and STL with a README, a licence and credits, nothing personal in the files. |


## Data

Tables (thread sizes, bearings, the tools agents see) are data files in
each add-on's `data/` folder: versioned, checked against a schema in CI,
each entry with its source and date, under CC BY 4.0 (`LICENSE-DATA`). Your
own entries go in `~/.config/<package>/<name>.json`; updates never
touch that folder and your entries win.

## Install

Each folder is an add-on of its own and installs alone: it carries its own
copy of what it needs (records, shape helpers, a data loader) and needs no
other add-on. Copy or link the ones you want into FreeCAD's `Mod` folder (for example
`Mod/WorkshopParts`, `Mod/WorkshopMake`, `Mod/WorkshopElectronics`, `Mod/WorkshopDocuments`), then restart FreeCAD. The Claude extension of FreeCAD
Agent Link installs them for you.

## Use

- **In FreeCAD:** switch to the add-on's own workbench (Workshop Parts,
  Workshop Electronics; Make's and Documents' benches get their buttons
  later). Each command asks for its
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
- **From an agent (with Agent Link):** `gen_make`, `gen_part`; `setup`, `part_spec`, `dfm_check`, `part_review`, `slice`, `mass_calibrate`, `mass_properties`, `mass_target`, `mass_ballast`, `slicer_presets`, `slice_with`, `slice_read`, `slice_open`, `printer_add`, `printer_list`, `printer_status`, `printer_send`, `printer_pause`, `printer_stop`, `fit`, `hw_hole`, `thread_lookup`, `thread_identify`, `thread_cut`, `hw_embed`, `hw_embed_list`, `hw_unembed`, `hw_pauses`, `cut_check`, `cut_export`, `mill_check`, `mill_export`, `fea_frame`, `kicad_import`, `board_enclosure`, `pcb_order_package`, `printed_channel`, `drawing_make`, `drawing_exploded`, `patent_figures`, `patent_draft`, `library_pack`; and `buildDir` / `printed` added to `fea_setup` and `fea_solve`.

## Tests

CI runs each add-on alone, then with Agent Link beside it, on the newest
FreeCAD and on 1.1 and 1.0:

```
PYTHONPATH=Parts python -m unittest discover -s Parts/tests
```

## History and licence

Parts moved here from Agent Link for FreeCAD on 14 Nov 2026. Its history before
that is in that repository: `agentlink/gridfinity.py`, `agentlink/boxes.py`
and `agentlink/families/parts.py` up to commit c954763.

LGPL-2.1-or-later. The Gridfinity profile follows the open Gridfinity
system by Zack Freedman.
