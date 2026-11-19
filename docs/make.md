<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Workshop Make

> **Written before the combine (15 Nov 2026).** This part is now inside the one Workshop add-on. Where each command sits now (FreeCAD's own workbenches, the Make workbench, Tools ▸ SafetyNet) is in the [README](../README.md#where-things-are). The install and uninstall notes below are out of date; the README has the current ones. What the part does, its Python API and its agent tools are the same.


> Not affiliated with or endorsed by the FreeCAD project or the FPA; FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

Workshop Make helps you get a part you designed actually made. You say how
each part is made (printed, cut from sheet, or milled) and what limits it
must meet. Make checks whether it can be made as it stands and gives one
verdict: pass, or what to fix. It sizes holes and pegs for bought parts with
your printer's real-world error added, looks up screw threads from the
standards, leaves pockets for nuts and magnets dropped in mid-print, weighs
the part as printed, slices it, and sends it to your printer. For sheet and
milled parts it writes the DXF, SVG or STEP the shop needs. It is for makers
who know what they want but not every rule of each process, and for people
who let an AI agent do that work with them.

<!-- screenshot: the Workshop Make workbench with its toolbars and the Make panel beside the model tree -->

You do not need to know Python. You do not need an agent.

## Install

You need FreeCAD 1.0 or newer.

**With the Addon Manager (custom repository).** This installs all four
Workshop add-ons (Parts, Make, Electronics, Documents) together.

1. Open **Edit ▸ Preferences ▸ Addon Manager**.
2. Under **Custom repositories**, add
   `https://github.com/jamesK1000011/Workshop-FreeCAD` with branch `main`.
3. Open **Tools ▸ Addon manager**, find **Workshop for FreeCAD**, and click
   **Install**.
4. Restart FreeCAD.

**As part of Agent Link.** The Agent Link extension for Claude Desktop
installs Workshop Make for you, on its own, as `Mod/WorkshopMake`. Nothing
else to do.

**By hand.** Put this `Make` folder in FreeCAD's `Mod` folder as
`WorkshopMake` and restart FreeCAD.

Use one way, not two: the same workbench installed twice shows up twice.

**Optional programs.** Slicing needs PrusaSlicer, OrcaSlicer or Bambu Studio
on this computer. Frames by beam elements use CalculiX, which comes with
FreeCAD's FEM workbench. Printers are reached on your network through
OctoPrint, Moonraker (Klipper) or PrusaLink.

## What you see in FreeCAD

**The Workshop Make workbench.** Pick it from the workbench list. Its
toolbars and its **Make** menu have:

- **Setup**: **New Setup** (how parts are made: print, cut or mill, and its
  settings), **Add Part to Setup**, **Remove Setup**.
- **Check**: **DFM Check** (is the part printable: walls, overhangs,
  bridges, holes, bed contact, build volume), **Part Review** (one verdict),
  **Mass Properties** (mass as made, centre of mass).
- **Fits**: **Fit Size** (the size to model a hole or peg at),
  **Calibrate Printer** (how much your printer prints holes small and pegs big),
  **Hole for Hardware** (FreeCAD's own PartDesign Hole on the face or sketch
  you pick, with its clearance, counterbore and countersink sizes, editable
  in its panel after; Make adds only what it lacks: your printer's
  allowance, nut traps, heat-set insert and magnet pockets. With an
  allowance the Hole is FreeCAD's plain hole at its size plus the
  allowance, so FreeCAD keeps it when the file is reopened; the size is in
  its description. The screw head, counterbore or countersink goes on the
  face you drill from. A plain Part
  solid, not in a Body, gets the hole cut as a shape, and is told so).
- **Hardware**: **Embed Hardware** (a pocket for a part dropped in mid-print),
  **Pauses** (every pause the print needs), **Thread Lookup** (FreeCAD's
  own thread tables, with insert holes and Unified pitches Make adds).
- **Output**: **Slice**, **Cut Export** (DXF and SVG laid out on the sheet by FreeCAD's BIM Nest
  where BIM is installed, else in rows),
  **Mill Export** (STEP, and the setup sheet from FreeCAD CAM's Job and its
  Sanity report, with Make's mill check added).
- **Printer**: **Printer Status**, **Send to Printer** (uploads; it does not
  start the print).

<!-- screenshot: the Make toolbars: Setup, Check, Fits, Hardware, Output, Printer -->

**Task panels.** New setup, Fit size, Calibrate, Hole, Embed and Slice open a
panel in the **Tasks** tab, like FreeCAD's own tools. **OK** runs it as one
undo step.

<!-- screenshot: the Hole task panel -->

**The Make panel**, beside the model tree (**Make ▸ Make Panel**), with tabs:

- **Setups**: each setup, its process and settings, and the parts in it.
  **New** puts in the part you selected (a feature or sketch stands for its
  Body), else the one you chose in the part list, else the active Body,
  else the only part in the document (meshes and add-ons' helper objects
  left out). With several parts and none of these it asks which, and makes
  nothing; a setup with no part says "No part in this setup: pick one".
- **Materials**: what each part is made of: Make's printing filaments and
  the material each process assumes. **Give to Part** also sets FreeCAD's
  own material on the part, so FreeCAD's Inspect Material agrees. A metal's
  E and yield are read from FreeCAD's material card. **Library…** opens
  FreeCAD's Material editor, and **FreeCAD Material…** runs FreeCAD's
  Material command on the part; Make weighs a part with the material set
  there.
- **Fits**: the size to model at for a bought part, and your printer's
  calibration.
- **Review**: the verdict on the part (in Make's own dock; with Agent Link,
  its Review tab asks Make).

<!-- screenshot: the Make panel on its Setups tab -->
<!-- screenshot: the Make panel on its Fits tab -->

Each button runs the same code an agent's tool does. Panels take their
colours from your FreeCAD theme.

**From Python or a macro:**

```python
from workshop_make import api
api.thread("M6")                                  # sizes from the standards
api.hole(App.ActiveDocument, "Bracket", "counterbore", "M3", at=[10, 10, 5])
```

## What an agent can do with it

When Agent Link for FreeCAD is installed, an agent gets these tools. The list
is generated from the tool definitions (`workshop_make/data/tools.json`) by
`tools/gen_readme_tools.py`.

<!-- tool list as it was; the README has the current one -->
| Tool | Group | What it does |
|---|---|---|
| `fit` | fits | Fits for made parts. |
| `hw_hole` | fits | A hole for hardware in a body, FreeCAD's own Hole where it can be. |
| `thread_lookup` | thread | Thread sizes from FreeCAD's own tables, mm. |
| `thread_identify` | thread | What thread a hole or shaft is. |
| `thread_cut` | thread | Thread a hole with FreeCAD's PartDesign Hole. |
| `hw_embed` | embed | Encase a bought part mid-print. |
| `hw_embed_list` | embed | The parts encased in a body. |
| `hw_unembed` | embed | Take an encased part out by id. |
| `hw_pauses` | embed | Every pause a body's print needs. |
| `setup` | make | How each part is made, recorded. |
| `part_spec` | make | The limits every part must meet, kept with the document. |
| `dfm_check` | make | Is a body printable as it stands, with its print setup's nozzle and printer. |
| `part_review` | make | One verdict on a part, pass, fix or unknown, after every change. |
| `slice` | make | Slice a body in a print setup with the slicer on this computer. |
| `mass_calibrate` | mass | Calibrate mass to a weighed print. |
| `mass_properties` | mass | Each body's mass in its material. |
| `mass_target` | mass | How far a body is from a target mass and/or centre of mass. |
| `mass_ballast` | mass | Lay out closed upright ballast pockets inside a body, minWall clear of every surface, to reach a target mass … |
| `slicer_presets` | slice | The person's own slicer presets, as data. |
| `slice_with` | slice | Slice a body in a print setup with slicer prusaslicer, orcaslicer or bambustudio, by its command line. |
| `slice_read` | slice | Read an OrcaSlicer or Bambu Studio project back. |
| `slice_open` | slice | Open a project in the slicer's own window for the person. |
| `printer_add` | printer | Keep a printer on the network by name. |
| `printer_list` | printer | The printers kept. |
| `printer_status` | printer | A printer's state now. |
| `printer_send` | printer | Upload a G-code file to a printer. |
| `printer_pause` | printer | Pause the printer's job. |
| `printer_stop` | printer | Stop the printer's job. |
| `cut_check` | cut | Can a body in a cut setup be cut from sheet. |
| `cut_export` | cut | The flat profiles of one or more sheet bodies laid out on the sheet by FreeCAD's BIM Nest where BIM is here … |
| `mill_check` | mill | Can a body in a mill setup be milled. |
| `mill_export` | mill | STEP of a milled body and its setup sheet by FreeCAD's CAM. |
| `fea_frame` | strength | A frame of straight members by beam elements. |


Make also adds `buildDir` and `printed` to Agent Link's own `fea_setup` and
`fea_solve`, so a strength study knows the print's layers, walls and infill.
It never starts a print on its own: **Send to Printer** only uploads.
With Agent Link, starting, pausing and stopping a print need your approval
through the client (`approve_file`), bound to the printer, the file and its
SHA-256. A typed confirm is refused then. Before an upload, the file is
read: printer-changing commands and heat over 300 °C (nozzle) or 120 °C
(bed) also need your approval.

## Alone or with Agent Link

| | Alone | With Agent Link |
|---|---|---|
| Workbench, toolbars, task panels | Yes | Yes |
| Make panel | Its own dock, with Review | Setups, Materials and Fits tabs in Agent Link's panel |
| Python API (`workshop_make.api`) | Yes | Yes |
| Wall-thickness map, strength as printed | No | Yes, on Agent Link's renderer and FEM study |
| Agent tools above | No | Yes |

Workshop Make needs no other add-on. It never imports Agent Link: only
`workshop_make/agentlink_families.py` and the `fam_*` modules it loads do, and
only Agent Link loads them. With [Agent Link for OrcaSlicer](https://github.com/jamesK1000011/AgentLink-OrcaSlicer)
installed beside it, OrcaSlicer and Bambu Studio slicing use its command
lines and presets.

### Hook services

With Agent Link, Make offers these through Agent Link's hooks
(`hooks.service(name)`). The names and call shapes are stable
(`workshop_make/services.py`). Make owns mass and materials, so Agent Link's
`measure_mass` and `material_set` defer to these when Make is installed.

| Service | Call | Gives |
|---|---|---|
| `mass_properties` | `f(session, args)` (args as the `mass_properties` tool takes them) | The tool's answer: mass as made (as printed in a print setup, inserts included), centre of mass, inertia |
| `material_set` | `f(doc, bodies, material)` (body labels; `""` forgets) | `{"materials", "freecadMaterial"}`: Make's record, and FreeCAD's material set to match |
| `print_pauses` | `f(session, body object, print setup)` | The pauses a print needs for parts encased mid-print |

## Data

Thread sizes are FreeCAD's own (PartDesign Hole's tables); `threads.json`
holds only what FreeCAD lacks. Fits, bearings, hardware, filaments, shop
materials, printers and cutting machines are data files in `workshop_make/data/`, each with a schema
and each entry with its source and date, under CC BY 4.0 (`LICENSE-DATA`).
Your own entries go in `~/.config/workshop_make/<name>.json`; updates never
touch that folder, and your entries win.

## Uninstall and privacy

Installed with Workshop for FreeCAD through the Addon Manager, it is removed
with it (Tools ▸ Addon manager ▸ Workshop for FreeCAD ▸ Uninstall). Installed
by Agent Link or by hand, delete the `WorkshopMake` folder from FreeCAD's `Mod`
folder and restart FreeCAD. What it wrote beside your documents, or in
`~/Workshop`, is yours to keep or delete.

Workshop Make has no telemetry. It sends nothing anywhere on its own. The one exception is the printer connection: when you ask, it talks to
printers on your own network (OctoPrint, Moonraker, PrusaLink) at the
addresses you give; their keys and passwords are kept in
`~/AgentLink/printers.json`, a file only your user can read, and are never
shown back. A redirect to another host is not followed. With Agent Link, what the agent
reads goes to the AI provider your MCP client uses, under that provider's
terms.

## For developers

```
AGENTLINK_HOME=$(mktemp -d) PYTHONPATH=. python3 -m unittest discover -s tests
python3 tools/gen_readme_tools.py   # refresh the tool list above
```

## Licence

LGPL-2.1-or-later (`LICENSE`); the data files are CC BY 4.0 (`LICENSE-DATA`,
`LICENSES/CC-BY-4.0.txt`). Each file's licence is stated in its header or in
`REUSE.toml`.

## Credits

- The Make panel is inspired by the panels of ScanRuler by Stefan Hermann
  (CNC Kitchen).
- Thread, fit and hardware sizes follow the published standards each data
  entry names.
- Icons are hand-drawn in FreeCAD's icon style. Their designs follow glyphs
  from [Tabler Icons](https://tabler.io/icons) (MIT) and
  [Pictogrammers Material Design Icons](https://pictogrammers.com) (Apache-2.0).
  See `workshop_make/icons/CREDITS.md` and the texts in `LICENSES/`.
- FreeCAD's own icons are used by name from FreeCAD.
