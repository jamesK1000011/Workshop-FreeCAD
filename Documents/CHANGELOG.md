# Changelog

All notable changes to Workshop Documents. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

### Added

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

### Changed

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
