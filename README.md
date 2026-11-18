<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Workshop for FreeCAD

> Not affiliated with or endorsed by the FreeCAD project or the FreeCAD project association (FPA); FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

One FreeCAD add-on for making things. Each feature sits in the FreeCAD
workbench it belongs to, beside the FreeCAD tool it builds on. Only what
FreeCAD has no place for gets a workbench of its own, the small **Make**
workbench. Everything works with no other add-on installed. When
[Agent Link for FreeCAD](https://github.com/jamesK1000011/AgentLink-FreeCAD) is
installed, the same functions are also tools an AI agent can call.

It brings together what used to be five add-ons: Workshop Parts, Make,
Electronics and Documents, and SafetyNet. Each part's own notes (its Python
API, data files and agent tools) are in [docs/](https://github.com/jamesK1000011/Workshop-FreeCAD/tree/main/docs/): [Parts](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/parts.md),
[Make](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/make.md), [Electronics](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/electronics.md),
[Documents](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/documents.md), [SafetyNet](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/safetynet.md).

**With Fasteners Workbench.** If you also have
[Fasteners Workbench](https://github.com/shaise/FreeCAD_FastenersWB) (Shai
Seger's add-on; its screw_maker is Ulrich Brammer's), Workshop works with it:
Hole for hardware can put the matching screw in the hole, drawings' bills of
materials and mass properties list its parts as bought hardware, and its
heat-set insert table and 3D-print thread settings are used before
Workshop's own typical figures. Agents get its fasteners as tools too (the
`fasteners` group below). Workshop calls Fasteners where it is installed
and copies none of it. Without Fasteners none of this shows. Notes:
[docs/fasteners.md](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/fasteners.md).

<!-- screenshot: Part Design with the Standard Parts dropdown open and a Gridfinity bin made -->

## Where things are

| Feature | Where |
|---|---|
| Gridfinity bin and baseplate, project box, board box | **Standard Parts** dropdown in Part (beside the primitives) and Part Design (beside the additive primitives); Part ▸ Primitives menu |
| Hole for hardware (printer allowance, nut trap, insert and magnet pockets) | Part Design, its own button right after Hole; in the Part Design menu before Boolean |
| Thread lookup | Part Design menu, after Hole for hardware |
| DFM check, part review, mass properties | **Make Checks** dropdown beside Check Geometry in Part Design; Mass properties also beside Measure in the menu |
| Drawing (a TechDraw page in one click) | TechDraw, after the page buttons |
| Exploded drawing, patent figures, patent draft | TechDraw menu (last items, before Cosmetic Eraser), after Drawing |
| KiCad board | File menu, after Import |
| Library pack | File menu, after Export |
| Checkpoint, restore, recovered copies, settings history and rollback, macros, clean up copies | **Tools ▸ SafetyNet** in every workbench; Recovered Copies also in the File menu |
| Matching screw in a hole (with Fasteners Workbench installed) | Hole for hardware's panel: **Add the matching screw (Fasteners)** |
| Setups, fit sizes and printer calibration, encased hardware and pauses, slicing, cut and mill export, printers; the Make panel (Setups, Materials, Fits, Review) and the Manual panel | The **Make** workbench |

## Install

You need FreeCAD 1.0 or newer.

- **Addon Manager:** add `https://github.com/jamesK1000011/Workshop-FreeCAD`
  (branch `main`) under **Edit ▸ Preferences ▸ Addon Manager ▸ Custom
  repositories**, then install **Workshop**.
- **Agent Link:** the Agent Link extension for Claude Desktop installs it as
  `Mod/Workshop`. It sets aside the older separate folders (`WorkshopParts`,
  `WorkshopMake`, `WorkshopElectronics`, `WorkshopDocuments`, `SafetyNet`)
  for you.
- **By hand:** download a release from
  [Releases](https://github.com/jamesK1000011/Workshop-FreeCAD/releases)
  (or the current
  [main as a zip](https://github.com/jamesK1000011/Workshop-FreeCAD/archive/refs/heads/main.zip)),
  unzip it into FreeCAD's `Mod` folder and rename the folder to `Workshop`.
  A `git clone` into `Mod/Workshop` works too.

Use one way, not two. If you had the separate add-ons or SafetyNet
installed, remove them first: two copies would show every command twice.

<!-- screenshot: the Make workbench with the Make panel's Setups tab -->
<!-- screenshot: Tools ▸ SafetyNet menu -->

## Uninstall

- **Addon Manager**: Tools ▸ Addon manager ▸ Workshop ▸ Uninstall, then
  restart FreeCAD.
- **Installed by Agent Link or by hand**: delete `Workshop` from FreeCAD's
  `Mod` folder and restart FreeCAD.
- **Your files** are yours to keep or delete. What the add-on writes goes
  beside the open document, or to `~/Workshop` when the document hasn't been
  saved. SafetyNet's checkpoints, copies and logs are under `~/AgentLink`.
  Its one setting group is `Mod/SafetyNet` in FreeCAD's parameters.

## Privacy

There's no telemetry, and nothing is sent anywhere on its own. The one
network use is the printer connection: when you ask it to, it talks to
printers on your own network (OctoPrint, Moonraker, PrusaLink) at the
addresses you give it. Their keys and passwords are kept in a file only your
user can read, and are never shown back. Library packs are scrubbed of
personal details before they're written. A macro runs only after you've
approved it yourself. With Agent Link, what the agent reads goes to the AI
provider your MCP client uses, under that provider's terms.

## What an agent can do with it

With Agent Link installed, these are the tools (names unchanged from the
separate add-ons):

<!-- tools:begin (generated by tools/gen_readme_tools.py) -->
| Tool | Group | What it does |
|---|---|---|
| `gen_make` | parts | Make a Gridfinity bin to size as a new body. |
| `gen_part` | parts | Make a standard part to size, each piece its own new body. |
| `fit` | fits | Give sizes for parts that fit together, and keep the fit calibration of the printer. |
| `hw_hole` | fits | Make a hole for hardware in a body. |
| `thread_lookup` | thread | Read thread sizes in mm from FreeCAD's own PartDesign Hole tables. |
| `thread_identify` | thread | Find what thread a hole or shaft is. |
| `thread_cut` | thread | Thread an existing hole with FreeCAD's PartDesign Hole. |
| `hw_embed` | embed | Encase a bought part mid-print. |
| `hw_embed_list` | embed | List the parts encased in a body. |
| `hw_unembed` | embed | Take an encased part out again, by its id. |
| `hw_pauses` | embed | List every pause that the print of a body needs, on the layer grid of its print setup. |
| `setup` | make | Record how each part is made, with the document. |
| `part_spec` | make | Keep with the document the limits that every part of it must meet, and what parts are made of. |
| `dfm_check` | make | Check if a body is printable as it stands, +z up, with the nozzle and printer of its print setup. |
| `part_review` | make | Give one verdict on a part. |
| `slice` | make | Slice a body that is in a print setup with the slicer on this computer. |
| `mass_calibrate` | mass | Calibrate mass to a weighed print. |
| `mass_properties` | mass | Read the mass, centre of mass and inertia of each body in its material. |
| `mass_target` | mass | Read how far a body is from a target. |
| `mass_ballast` | mass | Lay out closed, upright, round ballast pockets inside a body. |
| `slicer_presets` | slice | Read and use the slicer presets of the person, as data. |
| `slice_with` | slice | Slice a body in a print setup with a named slicer, by its command line. |
| `slice_read` | slice | Read back an OrcaSlicer or Bambu Studio project. |
| `slice_open` | slice | Open a project in the slicer's own window, for the person. |
| `printer_add` | printer | Keep a printer on the network by name. |
| `printer_list` | printer | List the printers that printer_add keeps. |
| `printer_status` | printer | Read the state of a printer now, over the network. |
| `printer_send` | printer | Upload a G-code file to a printer. |
| `printer_pause` | printer | Pause the running job of the printer. |
| `printer_stop` | printer | Stop the job of the printer. |
| `cut_check` | cut | Check if a body in a cut setup can be cut from sheet. |
| `cut_export` | cut | Write the flat profiles of sheet bodies as DXF and SVG in mm, laid out on a sheet. |
| `mill_check` | mill | Check if a body in a mill setup can be milled. |
| `mill_export` | mill | Write the STEP file of a milled body and its setup sheet to the folder of the session. |
| `fea_frame` | strength | Solve a frame of straight members with beam elements. |
| `kicad_import` | electronics | Read a KiCad board into the document. |
| `board_enclosure` | electronics | Make an enclosure round a board that kicad_import read, placed round it where it stands. |
| `pcb_order_package` | electronics | Package the fabrication files of a board for ordering. |
| `printed_channel` | electronics | Cut a channel inside a body along a path, for a wire or a conductive trace. |
| `drawing_make` | drawing | Make a dimensioned drawing of bodies in one call, and its SVG, PDF and DXF files. |
| `drawing_exploded` | drawing | Make an assembly manual. |
| `patent_figures` | drawing | Make patent-style figures FIG. |
| `patent_draft` | drawing | Write a Markdown draft of a patent description and a claims skeleton to the folder of the session. |
| `library_pack` | share | Pack bodies to share as one zip in the folder of the session. |
| `history_checkpoint` | core | Save a copy of the document now. |
| `history_restore` | core | Go back to a checkpoint. |
| `macro_save` | safety | Save the changing calls of this session as a FreeCAD macro. |
| `macro_list` | safety | List the macros in the macro folder of FreeCAD. |
| `macro_show` | safety | Show the text of one macro, its named sizes, how many calls it makes, and whether it is approved. |
| `macro_approve` | safety | Ask for the person's approval to run a macro. |
| `macro_unapprove` | safety | Take a macro off the approved list. |
| `macro_run` | safety | Run an approved macro as the Macro dialog of FreeCAD runs it. |
| `app_recover` | safety | Get documents back after a crash or a hang. |
| `pref_history` | safety | List the settings changes that Agent Link made, newest first. |
| `pref_rollback` | safety | Put the settings of FreeCAD back as they were before a change. |
| `fastener_types` | fasteners (with Fasteners Workbench installed) | Read the types, sizes and lengths of Fasteners Workbench, from its own tables. |
| `fastener_add` | fasteners (with Fasteners Workbench installed) | A Fasteners Workbench screw, nut, washer or insert, attached to round edges or loose. |
| `fastener_set` | fasteners (with Fasteners Workbench installed) | Change Fasteners parts in place, as Fasteners' own Change Parameters, Flip and Move do. |
| `fastener_list` | fasteners (with Fasteners Workbench installed) | The Fasteners parts in the document and their bill of materials. |
| `fastener_print` | fasteners (with Fasteners Workbench installed) | Read or set the 3D-print thread settings of Fasteners Workbench. |
<!-- tools:end -->

## For developers

Each part is its own Python package with its own API: `workshop_parts.api`,
`workshop_make.api`, `workshop_electronics.api`, `workshop_documents.api`,
`safetynet`, and `workshop_fasteners.api` (the Fasteners bridge, dormant
without Fasteners Workbench). `workshop/` is the add-on's own layer: the placement table
(`workshop/placement.py`), the one `agentlink_families` module, and the
helper files Agent Link vendors. The design is in
[docs/combine-design.md](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/combine-design.md). Tests, with no FreeCAD
needed:

```
AGENTLINK_HOME=$(mktemp -d) python3 -m unittest discover -s tests
for d in parts make electronics documents safetynet fasteners; do AGENTLINK_HOME=$(mktemp -d) PYTHONPATH=. python3 -m unittest discover -s tests/$d; done
python3 tools/gen_readme_tools.py   # the tool list above
```

## Licence

LGPL-2.1-or-later (`LICENSE`). The data files are CC BY 4.0 (`LICENSE-DATA`,
`LICENSES/CC-BY-4.0.txt`). Each file's licence is in its header or in
`REUSE.toml`. Parts moved here from Agent Link for FreeCAD on 14 Nov 2026;
its earlier history is in that repository (`agentlink/gridfinity.py`,
`agentlink/boxes.py` and `agentlink/families/parts.py`, up to commit
c954763). SafetyNet came from SafetyNet-FreeCAD (up to commit 25ca601), under
the same licence. Each part's changelog up to the combine is in
`CHANGELOG.md`.

## Credits

- Fasteners, when installed, are Fasteners Workbench's, by Shai Seger
  (shaise) and its contributors, with screw_maker by Ulrich Brammer
  (LGPL-2.1-or-later). Workshop calls them at run time and bundles none of
  them.
- The Make panel is inspired by the panels of ScanRuler by Stefan Hermann
  (CNC Kitchen).
- The Gridfinity profile follows the open Gridfinity system by Zack Freedman.
- Thread, fit and hardware sizes follow the published standards each data
  entry names. Fits follow ISO 286.
- KiCad is the KiCad project's. Its board files are read here without any
  KiCad code.
- Drawings are TechDraw pages, made with FreeCAD's own drawing workbench.
- Icons are hand-drawn in FreeCAD's icon style. Their designs follow glyphs
  from [Tabler Icons](https://tabler.io/icons) (MIT) and
  [Pictogrammers Material Design Icons](https://pictogrammers.com) (Apache-2.0).
  See each `icons/CREDITS.md` and the texts in `LICENSES/`.
- FreeCAD's own icons are used by name from FreeCAD.
