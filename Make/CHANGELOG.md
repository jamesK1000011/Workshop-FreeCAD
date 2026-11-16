# Changelog

All notable changes to Workshop Make. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.3.0 (the version in `package.xml`), is being prepared.

### Added

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

### Changed

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

### Fixed

- `fea_frame`: gravity is defined.
