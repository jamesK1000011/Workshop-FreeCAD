# Changelog

All notable changes to Workshop Electronics. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

### Added

- Its own workbench, Workshop Electronics, with the KiCad board button.
- The KiCad board task panel (path, Browse…, a live line saying what the
  board is) instead of a modal file dialog.
- Icons for the workbench and the import, drawn in FreeCAD's style, with
  their credits and licence texts.
- Release preparation: a beginner's README with a generated tool list,
  complete Addon Manager metadata with its own `LICENSE`, licence headers
  or `REUSE.toml` entries checked for every file, and this changelog.

### Changed

- Installs alone: its own enclosure maker and its own copies of what it used
  from AddonKit; it reads the printer fit itself and no longer needs Workshop
  Parts.
- Agent tools are data (`data/tools.json`) bound through Agent Link's tool
  data; handlers no longer import Agent Link.

### Fixed

- `pcb_order_package`: its KiCad file no longer shadows the `pcb` module.
