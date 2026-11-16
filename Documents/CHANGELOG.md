# Changelog

All notable changes to Workshop Documents. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The first tagged release, 0.2.0 (the version in `package.xml`), is being prepared.

### Added

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

### Changed

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
