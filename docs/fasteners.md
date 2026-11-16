<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# The Fasteners bridge

`workshop_fasteners` lets Workshop and agents use
[Fasteners Workbench](https://github.com/shaise/FreeCAD_FastenersWB), Shai
Seger's add-on (LGPL-2.1-or-later since V0.6.00; its screw_maker is Ulrich
Brammer's), when the person has it installed. Workshop copies and bundles
nothing of it. Its modules (`FastenerBase`, `ScrewMaker`, `FastenersCmd`,
`PEMInserts`, `FSutils`) are loaded at run time from where FreeCAD
installed it. Every size, length and shape comes from them.

## Without Fasteners

`detect.find()` checks folders and imports nothing: `sys.path` and every
folder of the Mod folders (Addon Manager's `Mod/fasteners`, a clone's
`FreeCAD_FastenersWB`, any name). A folder counts when it holds
`FastenerBase.py`, `ScrewMaker.py` and `FastenersCmd.py`; its `package.xml`
gives the version. If nothing is found, `families.FAMILIES` is empty. That
means no tools, no `fasteners` group in `tool_groups`, no guide, no `screw`
argument on `hw_hole`, no panel checkbox and no errors. FreeCAD's log gets one
debug line. `WORKSHOP_FASTENERS=off` turns the bridge off;
`WORKSHOP_FASTENERS=<folder>` points it at a copy.

## Python API (`workshop_fasteners.api`)

| Call | What it does (Fasteners' function used) |
|---|---|
| `types(query, standard, kind, ftype, size)` | Types (`FSScrewCommandTable`, `FSGetStandardFromType`, `GetTypeName`); sizes (`GetAllDiams`); lengths (`GetAllLengths`); tap hole (`GetInnerThread`, the calculator's charts) |
| `add(doc, type, size, length, thread, edges, at, match, invert, offset)` | `FSScrewObject` on each round edge (or loose); length by `FindClosest`; its view provider when there is a window |
| `change(doc, refs, …)` | What Change Parameters, Flip and Move do |
| `listing(doc)`, `bom_sheet(doc)`, `restore(doc)` | Its BOM count (`GetTotalObjectRepeats`), its Generate BOM command in a window, Restore fasteners |
| `print_settings(mode, nut, screw)` | Its 3D Print Settings (`FSParam`, `updateFastenerParameters`) |
| `insert_figures(size)` | Its IUT heat-set insert table (`FSutils.csv2dict` on its `HeatInserts.csv`) |
| `hole_screw(doc, hole_args, hole_out, spec)` | The matching screw in a hole Hole for hardware made |
| `bom_text(o)`, `detect.is_fastener(o)` | A fastener's BOM line, and whether an object is one. Neither needs Fasteners loaded |

**Without a window.** `FastenerBase` imports `FreeCADGui` at its top but
uses it only behind `FSutils.isGuiLoaded()`. In a Python where
`FreeCADGui` can't load, `fs.load()` puts a stand-in module in
`sys.modules` for the length of the import, then takes it out. Fasteners
itself isn't patched.

## Agent tools (group `fasteners`, not in the lean list)

`fastener_types`, `fastener_add`, `fastener_set`, `fastener_list`,
`fastener_print`. Plus `hw_hole { screw }`, an Agent Link tool extension
registered only when Fasteners is there. The echo: Fasteners' workbench
(`FastenersWorkbench`, from its InitGui.py) comes up. The lit button is
its own: `FS<type>` for `fastener_add`, `Fasteners_ChangeParameters`,
`Fasteners_Flip`, `Fasteners_Move`, `Fasteners_RestoreProperties`,
`Fasteners_BOM`, `Fasteners_3dPrintSettings`, `Fasteners_Search`.

Every Fasteners command is judged (tool / window / n/a) in
`workshop_fasteners/data/coverage.json`, and a test fails when its source
gains a command the map doesn't judge.

## Kept on the hole, under one label (`keep.py`)

Fasteners attaches by edge name, and FreeCAD renumbers edges after a later
PartDesign feature (topological naming). Its `execute()` also sets the label
on every recompute, and FreeCAD then makes the label unique by a growing
suffix (`M8x25-Screw218`, `219`, `222`). Workshop does not change Fasteners.
An App document observer (registered in `Init.py`, only when Fasteners is
installed) and every `fastener_*` call check each fastener Workshop put in
against its `WorkshopKeep` property:

- **Anchor.** The edge's object, name, centre, axis and radius. When the
  edge named is no longer that circle, the round edge with the same radius
  and a parallel axis nearest the stored centre, within its radius (at least
  1 mm), is taken and the fastener recomputed. With a window this happens
  just after the document's recompute, never inside it. If there is none,
  the fastener is left where it is and a warning goes to the Report view,
  to `lost` on it and to `warnings` in `fastener_list`.
- **Label.** `M8x25-Screw`, then `M8x25-Screw 2` and so on, numbered per
  size once and put back after each recompute. A label given with
  `fastener_set { label }` is kept as given.

## Where Workshop uses it

- **Hole for hardware**: `screw: true | {type, length, thread}`, or the
  panel's *Add the matching screw (Fasteners)* checkbox, shown only when
  Fasteners is installed. The screw is attached to the hole's round edge,
  and its shank points into the material:
  - clearance hole: the screw is the plate's thickness long;
  - counterbore: it sits on the counterbore's floor and is the plate less
    the counterbore long;
  - countersink: a countersunk screw (ISO 10642) at the top;
  - nut trap: it comes from the far side;
  - insert: it is as long as the insert is deep (add what it clamps).
  Pass holes match the screw's outer diameter and an insert its inner
  thread. The length is the nearest one Fasteners has.
- **Bills of materials**: `drawing_exploded` (the BOM and the assembly
  manual) lists Fasteners parts as bought hardware, one item per type and
  size, by the BOM line Fasteners itself uses. `fastener_list` gives
  Fasteners' own count. `mass_properties` lists them apart, in steel (they
  carry no material), instead of as printed PLA bodies.
- **Heat-set inserts**: `hw_hole { kind: insert }` and `thread_lookup` take
  Fasteners' IUT insert table (hole D, length) where it has the size
  (M2–M6). Workshop's typical figures are the fallback. The answer's
  `insertSource` / `source` says which was used.
- **Printed threads**: `thread_cut { mode: modelled }` on a part in a print
  setup, with Fasteners set to 3D-print mode, gives the Hole FreeCAD's own
  custom thread clearance from Fasteners' nut scaling (d × A + B − d). The
  answer's `printClearance.source` says so.

## What Workshop defers to Fasteners (earn their keep)

- Bought screws, nuts, washers, inserts, pins and rings as solids: none of
  Workshop's own. Workshop models only the holes and pockets for them.
- Heat-set insert hole sizes: Fasteners' IUT table first. Workshop's
  `metric-hardware.json` insert figures are the fallback (M8 is ours only).
- Printed-thread compensation: Fasteners' 3D-print setting where it is on.
- The hardware BOM line and count: Fasteners' own wording and counting.
- Kept as Workshop's: ISO 273 clearance holes, counterbores, countersinks
  and nut traps as cuts (FreeCAD's PartDesign Hole, plus the printer
  allowance), and the printer calibration. Fasteners' countersunk-hole
  feature is deprecated by Fasteners itself in favour of PartDesign Hole.

## Live check (FreeCAD 1.1.3 with Fasteners installed)

1. `tool_groups` lists `fasteners`, and `hw_hole`'s schema has `screw`.
2. `fastener_add { type: "ISO4762", edges: ["<body>.EdgeN"] }` on a
   through hole: Fasteners' workbench comes up and its ISO4762 button
   lights; the screw sits in the hole and the answer names its size.
3. `hw_hole { kind: counterbore, size: M3, at, screw: true }`: the screw
   sits on the counterbore's floor, its shank into the plate.
4. In the hidden FreeCAD (window closed): `fastener_types { type:
   "ISO4762", size: "M3" }` and `fastener_add` work.
5. `fastener_list { sheet: true }` runs Fasteners' own Generate BOM.
6. Hole for hardware's panel shows the checkbox.
