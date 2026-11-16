<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Changelog

All notable changes to Workshop for FreeCAD, the suite the Addon Manager
installs (its version is the one in `package.xml`). Each add-on keeps its own
changelog and version: [Parts](Parts/CHANGELOG.md), [Make](Make/CHANGELOG.md),
[Electronics](Electronics/CHANGELOG.md) and
[Documents](Documents/CHANGELOG.md). The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release is being prepared.

### Planned

- docs/combine-design.md: Workshop's four add-ons and SafetyNet become one
  add-on, each feature placed in its FreeCAD workbench by a workbench
  manipulator, one small Make workbench for what has no FreeCAD home.

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
