<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Changelog

All notable changes to Workshop for FreeCAD, the one add-on the Addon
Manager installs (its version is the one in `package.xml`). Workshop Parts,
Make, Electronics, Documents and SafetyNet were separate add-ons until 15 Nov
2026; their own changelogs as they stood then are under
[History before the combine](#history-before-the-combine). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.4.0 (the version in `package.xml`), is being
prepared.

### Added

- The Fasteners bridge (`workshop_fasteners`). When
  [Fasteners Workbench](https://github.com/shaise/FreeCAD_FastenersWB) (Shai
  Seger; screw_maker by Ulrich Brammer) is installed, Workshop calls it at
  run time and copies none of it:
  - Hole for hardware can put the matching screw in the hole (`hw_hole
    { screw }`, or the panel's checkbox).
  - Exploded drawings' BOM and mass properties list its parts as bought
    hardware.
  - Its heat-set insert table and 3D-print thread setting come before
    Workshop's typical figures.
  - Agents get the `fasteners` tools: `fastener_types`, `fastener_add`,
    `fastener_set`, `fastener_list` and `fastener_print`.
  Without Fasteners nothing shows and nothing costs tokens.

### Fixed

- Hole for hardware (`hw_hole`) on a Body with a recompute pending (an edit not yet recomputed, or recomputes frozen): the Body is brought up to date first, and only it; the new Hole and its sketch are recomputed by themselves, forced, when the document's recompute leaves them waiting. It failed "FreeCAD's Hole could not be made here: Touched." A face named with its feature (`face: "Pocket 5.Face4"`) is that feature's face; the whole reference was taken as the face's name, so the sketch had no face. FreeCAD's state words and its exceptions are said as sentences, a broken feature before the hole named. Found on a live test drive (bike stem, 16 Nov 2026).
- `hw_hole { screw }` searches for the hole's edge in the Body's own frame: a Body inside an App::Part moved off the origin searched [75, 11.5, 4] for an edge at [67, 11.5, 12]. The search runs along the hole's axis (the counterbore's floor found when its depth reads a little short), and the through length is read in that frame too.
- `fastener_add { edges: [{ body, near: [x, y, z] }] }` takes the round edge nearest the point (a bad pick is refused with the nearest round edges; it crashed on its own error path, `o.Label` on None). A `size` given wins: Fasteners sizes a screw from its edge again when MatchOuter changes, so an M6 on a counterbore's 15.2 mm wall came out M14; now MatchOuter is taken in first and the size set after, and a size on a counterbore's wall goes on the bore's edge at its floor, said in `attachNote`. Each attached fastener gives `edgeDiameter`. `fastener_set` with match and size keeps the size too.
- A material is shown by its name (`workshop/matname.py`): `mass_properties`' `material` and the drawing's title block, BOM and patent draft showed a FreeCAD library card by its UUID; the id stays apart (`materialId`).
- `drawing_make { file }` honours a path: absolute (its folder made) or under the session's folder, its extension dropped so the PDF, SVG and DXF share the stem (it wrote `Users_jamesk_AgentLink_stem-test_Stem-drawing.pdf.pdf`). `drawing_make` is declared a writer, so Agent Link checks that path as every writer's. `holes` calls out PartDesign Holes as FreeCAD made them (`2× ⌀6.6 THRU CBORE ⌀11 DEEP 6.4`, a thread's size, CSK), and finds the plain round holes PartDesign makes by revolving (surfaces of revolution) as well as Part's cylinders; it answered `holes: []` for two counterbored Holes.

- Every Workshop task panel and dock page fits the Tasks dock (320 px or
  wider). On 1.1.3 Hole for Hardware was about 580 px wide: its intro was
  cut off, its fields ran past the right edge and its OK button was
  clipped. Now in every form (`workshop/narrow.py`):
  - long labels wrap;
  - combos ask for a few characters of room rather than their longest
    entry, so a long part or setup name is elided;
  - a long row's label sits above its field;
  - nothing sets a fixed width.
  Hole for Hardware also puts X, Y and Z one under another, and puts the
  Fasteners checkbox on its own row with the screw type under it. This
  covers Make (its task panels and its Setups, Materials, Fits and Review
  tabs), Documents (Drawing, Exploded drawing, Library pack, Patent draft,
  Manual), the KiCad board panel and the Parts generators (Gridfinity bin
  and baseplate, Project box, Board box). SafetyNet's panel already fit.
- Hole for Hardware starts on what you picked. With a face of a Body
  picked (Hole.Face5, or the same face picked on the Body), Part is that
  Body, even when the parts list leaves it out. The panel also says which
  face the hole starts on ("Face5 of Body") and sets "Into the material"
  from that face. Fit size, Embed hardware and Slice take the picked part
  the same way, and so do Documents' panels.
- No more "Internal C++ object (PySide6.QtWidgets.QMenu) already deleted"
  in the Report view at each workbench switch. Tools ▸ SafetyNet's Qt
  backstop finds the Tools menu again each time it runs, checks it's still
  valid, and quietly skips a menu FreeCAD deleted while rebuilding the menu
  bar.
- Drawing, Exploded drawing, Patent figures and Patent draft are in the
  TechDraw menu again. On 1.1.3 that menu's own level is submenus plus
  Cosmetic Eraser, so they go before Cosmetic Eraser.
- Tools ▸ SafetyNet was missing on FreeCAD 1.1.3, where an append into the
  Tools menu didn't land. It's now inserted before Customize, and a Qt
  backstop adds it after each workbench switch wherever it's still missing.
- Hole for hardware and Thread lookup were missing from the Part Design
  menu. On 1.1.3 an insert can't reach into a submenu, so they now sit at
  the Part Design menu's own level, before Boolean.
- Old WorkshopParts/Make/Electronics/Documents or SafetyNet Mod folders
  left beside Workshop no longer shadow its packages. Workshop's own folder
  goes first on the path, the old folders are named in one line of the
  Report view, and their InitGui files do nothing instead of failing.
  Workshop never touches the Mod folder; Agent Link's update sets the old
  folders aside.

### Changed

- One add-on: Workshop Parts, Make, Electronics and Documents and SafetyNet
  are combined into one, installed as `Mod/Workshop` with one
  `package.xml`, `Init.py` and `InitGui.py` (docs/combine-design.md). Each
  feature sits in its FreeCAD workbench through a workbench manipulator
  (`workshop/placement.py`): Standard Parts beside the Part and Part Design
  primitives, Hole for hardware right after PartDesign Hole with Thread
  lookup after it, Make Checks (DFM check, part review, mass properties)
  beside Check Geometry, Drawing and the patent figures in TechDraw, KiCad
  Board after File ▸ Import, Library Pack after File ▸ Export, SafetyNet in
  Tools ▸ SafetyNet and Recovered Copies in File. One small Make workbench
  keeps setups, fits, encased hardware, slicing, cut and mill output and
  printers, with the Make and Manual panels. The Parts, Electronics,
  Documents and SafetyNet workbenches are gone.
- Hole for hardware isn't folded into PartDesign Hole's task panel (C++,
  with no Python API to add a section). It's its own button right after
  Hole.
- Agent tools: one `workshop.agentlink_families` joins every part's
  families. Tool names are unchanged. The echo's workbench follows the
  buttons (Part Design for the parts, holes, threads and checks).
- One copy of Agent Link's vendored `layout.py` (and of `tooldata.py`), in
  `workshop/`. The old module names are aliases of it. `tests/test_shared.py`
  fails when it drifts from Agent Link's copy.
- SafetyNet's code is brought in from SafetyNet-FreeCAD (25ca601), same
  licence. Its settings (`Mod/SafetyNet`) and files (`~/AgentLink`) are
  unchanged.

### Added

- Workshop for FreeCAD: four add-ons for making things, installed together
  from one Addon Manager entry, each its own workbench that works with no
  other add-on. Workshop Parts (Gridfinity bins and baseplates, project
  boxes, board enclosures), Workshop Make (setups, printability, fits and
  hardware, threads, slicing, printers on the network, output for laser,
  waterjet and mill), Workshop Electronics (KiCad boards read without KiCad,
  enclosures round them) and Workshop Documents (drawing sheets, assembly
  manuals, patent figures, library packs).
- Tools for agents through Agent Link for FreeCAD when it is installed.
- Release preparation: Addon Manager metadata for the suite (numpy declared,
  scipy optional; each workbench's icon relative to its own folder, as
  FreeCAD reads it), a README with install, uninstall and privacy, and this
  changelog.

### Changed

- Features that came back from ScanRuler build on FreeCAD's own and keep
  only the extras: Hole for Hardware is a PartDesign Hole plus the printer
  allowance, nut traps, inserts and magnets; Thread Lookup reads FreeCAD's
  thread tables; the Materials tab hands the library to FreeCAD's Material
  editor and sets FreeCAD's material on the part; Drawing… is a normal
  TechDraw page exported by TechDraw.

## History before the combine

Each add-on's own changelog as it stood when the five became one add-on
(15 Nov 2026).

### Workshop Parts

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

#### Added

- Workshop Parts moved here from Agent Link for FreeCAD: Gridfinity bins and
  baseplates, project boxes with lids and board enclosures, made to size,
  with a Python API (`workshop_parts.api`) and the agent tools `gen_make`
  and `gen_part`.
- Its own workbench, Workshop Parts, with a button for each part.
- A task panel for each part in the Tasks tab, built from its values, with a
  live line (a value refused, or the printer fit) and OK/Cancel as one undo
  step.
- Icons for the workbench and each part, drawn in FreeCAD's style, with
  their credits and licence texts.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata with its own `LICENSE`, licence headers
  or `REUSE.toml` entries checked for every file, and this changelog.

#### Changed

- A new part goes beside the document's solids (+X, 10 mm clear) instead of
  inside them; an empty document keeps it at the origin. The Report line and
  task panel say the printer calibration in a sentence ("Workshop: made
  Gridfinity bin 1×1×3. Printer calibration: none, so holes are assumed to
  print 0.2 mm small.").
- Installs alone: its own copies of what it used from AddonKit (records,
  shape helpers, fits, the data loader), trimmed to what it uses.
- Agent tools bind through Agent Link's tool data; handlers no longer import
  Agent Link. What the window shows while the agent works (workbench, the
  part's button) is declared for Agent Link's echo.

#### Removed

- The `data/fits.json` copy, which nothing loaded.

### Workshop Make

The first tagged release, 0.3.0 (the version in `package.xml`), is being prepared.

#### Added

- Make offers its mass properties and material setting as hook services (`mass_properties`, `material_set`, listed in the README's Hook services table), so Agent Link's own mass and material tools defer to Make when it is installed.
- Its own workbench, Workshop Make, with Setup, Check, Fits, Hardware,
  Output and Printer toolbars over Make's own runner (one undo step a
  command).
- Task panels for New setup, Fit size, Calibrate, Hole, Embed and Slice.
- The Make panel: Setups, Materials and Fits tabs moved in from Agent Link
  (in Agent Link's panel when it is installed), and alone a Make dock with a
  Review tab.
- Icons for the workbench and its commands, drawn in FreeCAD's style, with
  their credits and licence texts.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata with its own `LICENSE`, licence headers
  or `REUSE.toml` entries checked for every file, and this changelog.

#### Changed

- Cut Export lays the sheet parts out with FreeCAD's BIM Nest
  (ArchNesting, as BIM_Nest does; no turns, the gap as its margin) when a
  sheet size is given and BIM is here; Make keeps the kerf, least feature by
  material, cut check and its DXF/SVG flat profiles. Otherwise the rows as
  before, and `layout` says which and why (`nest: false` for rows).
- Mill Export builds on FreeCAD's CAM: the CAM Job holding the part is
  reused, else a Job is made with the stock and least tool used, and the
  setup sheet is CAM's own Sanity report (HTML) with only Make's mill check
  added (verdict, reach and undercut, thin wall and deep pocket findings,
  least wall, assumptions, the stock material where CAM names none). The
  STEP stays. Without CAM, Make's own sheet and `camNote` says why
  (`cam: false` skips CAM). mill_export now counts as a change (it adds a
  Job).
- Part Review and DFM Check judge soundness with FreeCAD's own Check
  Geometry (Shape.check, as Part_CheckGeometry runs it, with its BOP-check
  preference) instead of Make's own validity test; Make keeps only what a
  print needs beyond it (closed, one solid, slivers) and its print checks
  (walls, overhangs, bridges, holes, bed contact, build volume). DFM Check
  adds a check-geometry finding when FreeCAD's check fails.
- The Report view says each command's result in a sentence with units
  ("Workshop: M3 clearance hole in Body, through 20 mm (FreeCAD Hole,
  editable in Part Design). Printer calibration: none, so 0.2 mm added."),
  not the tool's fields; those stay in the tool's answer for agents
  (hw_hole's adds allowance, depth and through).
- Hole for Hardware builds FreeCAD's own PartDesign Hole in a Body, on the
  face or sketch picked (ISO 273 clearance by fit, the screw standard's
  counterbore or countersink, sizes from FreeCAD's tables; editable in its
  task panel), and adds only what it lacks: the printer allowance from the
  setup's calibration, a nut trap (a Pocket from a hexagon), heat-set insert
  and magnet pockets. A plain Part solid keeps the shape cut and the answer
  says so (`route`). `hw_hole` takes `face` and `sketch`.
- Thread Lookup reads FreeCAD's thread tables (a Hole in a hidden scratch
  document) instead of a copy; `threads.json` (data version 2) keeps only a
  Unified size's threads per inch and tap drill name, which FreeCAD lacks.
  Insert holes join the metric rows. Without PartDesign the thread tools
  say they cannot read the tables.
- Materials tab: Give to Part also sets FreeCAD's ShapeMaterial (the
  filament's FreeCAD card, the person's own of the same name first), Forget
  puts FreeCAD's default back, so Inspect Material agrees with Make. Metals
  show E and yield from FreeCAD's material cards only (`freecadCards` in
  `shop-materials.json`). Library… opens FreeCAD's Material editor and
  FreeCAD Material… its Material command; a part given a material there is
  weighed with it.
- The Make dock as tried live in a 354 px dock: a setup named once ("Print",
  not "Print (Print)") with its printer, nozzle and layer height or its
  defaults; tables fitted to the dock (no horizontal scrollbar, cut cells'
  full text in tooltips); shop materials by display name, aluminium found as
  Aluminum and listed once; Fits lists the document's parts, sizes in mm
  with their units, calibration fields in mm, "Bought part size"; Review's
  verdict "PASS — Body, printed", its figures with units, a line before the
  first review, and a part it selected unselected on leaving Make. No
  calibration reads "none, so holes are assumed to print 0.2 mm small".
- Installs alone: its own copies of what it used from AddonKit (records,
  shape helpers, fits, the data loader, CalculiX, sheets, materials), with
  its own data files, trimmed to what it uses.
- Agent tools are data (`data/tools.json`) bound through Agent Link's tool
  data, with `heavy`, `writes` and `pathIsCurve` set on the tools.
- Tool bodies moved into `handlers/`, one module per family, with no Agent
  Link import; `maps.py` and `printed.py` are lent Agent Link's renderer
  and hooks instead of importing them. Tool names, descriptions and refusals
  are unchanged.

#### Fixed

- Cut Export and Cut Check take the cut setup's sheet when no sheet is
  given (the setup's [300, 200] was ignored and the parts went in rows).
- BIM Nest's answer read the way ArchNesting keeps it (run()'s sheets,
  each a list of [hashCode, face]; first sheet placed, later ones left
  over); the gap kept by growing each profile and shrinking the sheet by
  half of it, ROTATIONS held at [0] while it runs. It placed the piece and
  Make had read "placed nothing".
- Mass Properties names the material as a person reads it: "PLA (assumed;
  set the material to change it)", display names for filaments
  (`materialId` keeps the id for agents).
- Mill Export's new CAM Job names its tool controller and tool for the
  diameter set ("TC: 3 mm End Mill"), not CAM's default "5mm Endmill".
- `fea_frame`: gravity is defined.

### Workshop Electronics

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

#### Added

- Its own workbench, Workshop Electronics, with the KiCad board button.
- The KiCad board task panel (path, Browse…, a live line saying what the
  board is) instead of a modal file dialog.
- Icons for the workbench and the import, drawn in FreeCAD's style, with
  their credits and licence texts.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata with its own `LICENSE`, licence headers
  or `REUSE.toml` entries checked for every file, and this changelog.

#### Changed

- No calibration reads "none, so holes are assumed to print 0.2 mm small".
- Installs alone: its own enclosure maker and its own copies of what it used
  from AddonKit; it reads the printer fit itself and no longer needs Workshop
  Parts.
- Agent tools are data (`data/tools.json`) bound through Agent Link's tool
  data; handlers no longer import Agent Link.

#### Fixed

- `pcb_order_package`: its KiCad file no longer shadows the `pcb` module.

### Workshop Documents

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

#### Added

- With ScanRuler-FreeCAD installed (it offers the `library_pack` service),
  Documents' `library_pack` agent tool is left off Agent Link's tool list,
  so the agent sees ScanRuler's `pack_setup`, `pack_plan` and `pack_write`
  only; it stays callable by name and routed to the service, and the
  Library Pack command keeps working through it. Alone, it is listed.
- Library Pack asks for a `library_pack` hook service first (ScanRuler-FreeCAD's pack when it offers one) and falls back to Documents' own pack; the answer's `by` says which made it, and `provider: documents` forces Documents' own.
- Workshop Documents, from Agent Link for FreeCAD: `drawing_make`,
  `drawing_exploded`, `patent_figures`, `patent_draft` and
  `library_pack` with their guides, hidden-line views and library packs; a
  Python API with no agent.
- Its own workbench, Workshop Documents, with Drawings, Share and Patent
  toolbars over its own runner, and task panels for Drawing and Exploded
  drawing.
- The Manual tab, moved in from Agent Link (in Agent Link's panel when it is
  installed, else a Documents dock). Make manual uses another add-on's
  manual maker when one is offered, else Documents' own exploded drawing.
- Icons for the workbench and its commands, drawn in FreeCAD's style, with
  their credits and licence texts.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata with its own `LICENSE`, licence headers
  or `REUSE.toml` entries checked for every file, and this changelog.

#### Changed

- Drawing sheets name the Helvetica font only, so Qt no longer warns of a missing "Sans-serif" in the Report view (Agent Link's copy of sheets.py already does).
- Exploded Drawing builds on FreeCAD 1.x Assembly where the parts are in
  one: the manual's moves become the Assembly's own Exploded View
  (Assembly_CreateView's Exploded View and Move objects), editable there,
  and an ordinary TechDraw page of it with TechDraw balloons per item and
  the bill of materials. Step pictures, balloons, BOM and the manual stay;
  outside an Assembly the steps keep Workshop's own exploded shapes and
  `route` says so.
- Patent Figures: each figure is also an ordinary TechDraw page in patent
  style (blank A4 portrait template, visible lines only, numerals as
  TechDraw balloons without a bubble or arrowhead, FIG. label as an
  annotation, inside the same margins), editable in TechDraw; PDF and SVG
  are its exports where TechDraw can write them. Patent Draft unchanged.
- The Report view says each command's result in a sentence (the drawing's
  paper, scale, TechDraw page and files; the manual's steps; the pack's
  size), not the tool's fields.
- Drawing… makes a normal TechDraw page: TechDraw's own template (its
  preference, else ISO 7200) with the title block filled, its views,
  section and dimensions, all editable in TechDraw. The SVG, PDF and DXF
  are the page's own TechDraw exports where TechDraw can write them;
  Workshop's sheet writer writes the rest (PDF and SVG without a window),
  and `filesFrom` says which. The views keep clear of the template's title
  block.
- The Manual tab's steps table fits the dock (no horizontal scrollbar, cut
  cells in tooltips); its instruction reads "…, then press Add Step."
- Installs alone: its own copies of the sheet writer, ISO 286, materials and
  TechDraw's wait, trimmed to what it uses.
- Tool bodies moved into `handlers/` with no Agent Link import.

### SafetyNet (from SafetyNet-FreeCAD, up to commit 25ca601)

The first release, 0.1.0, is being prepared.

#### Added

- SafetyNet split out of Agent Link for FreeCAD as its own add-on. It keeps
  checkpoints, auto-save copies, recovery after a crash or a hang, a log of
  FreeCAD's settings with rollback, and macros that run only once approved.
- Agent Link finds SafetyNet's tools when both are installed: the checkpoint
  tools in its core group, and the recovery, settings and macro tools in a
  safety group.
- Icons for the workbench and for Checkpoint, Restore and Recover, drawn in
  FreeCAD's style, with their credits and licence texts.
- The SafetyNet workbench, a Tools ▸ SafetyNet submenu in every workbench, and
  the Session panel as its own dock when Agent Link is not installed.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata, licence headers checked for every file,
  how to uninstall, a privacy statement, and this changelog.
- The SafetyNet panel lists Recovered Copies once per original document,
  copies of copies included, says where each copy came from (FreeCAD
  autosave, SafetyNet autosave, My checkpoint or Agent checkpoint, by who
  took it), and folds closed documents over
  two hours old under Older. Its buttons work only on the kind of row picked,
  and SafetyNet's messages have a short bold first line. Opening a recovered
  copy rebuilds the shapes FreeCAD's autosave left empty and says why the
  Report view showed errors.
- Recovered Copies shows only open documents and a Last crash group; the
  rest is under a folded Older row. Old copies are cleaned up at start and
  at most once a day (the newest 3 a document, none past 7 days, never-saved
  documents' past 1 day), to the Trash, keeping open documents, the last
  crash, copies used this week and named checkpoints. Tools ▸ SafetyNet ▸
  Clean Up Copies… shows what would go and asks first.
- Macros build on FreeCAD's own: the list is FreeCAD's macro folder (.FCMacro
  and .py, as Macro ▸ Macros… shows it), and an approved macro runs as
  FreeCAD runs one, alone as well as with Agent Link. The approval list and
  the checkpoint before each run stay. The panel and the Macros command open
  FreeCAD's Macro dialog.
