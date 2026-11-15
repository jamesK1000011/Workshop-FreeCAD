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
