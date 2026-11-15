# Changelog

All notable changes to Workshop Parts. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

### Added

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

### Changed

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

### Removed

- The `data/fits.json` copy, which nothing loaded.
