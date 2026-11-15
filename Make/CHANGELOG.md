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
