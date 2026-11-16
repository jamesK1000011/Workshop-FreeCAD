# Drawing: sheets, manuals, patent figures

## A drawing sheet
- `drawing_make` gives SVG, PDF and DXF files and a TechDraw page with the same views, on TechDraw's ISO 5457 template with its title block filled. Ask which projection the person works in: first angle (ISO, Europe) or third angle (ASME, North America). Left out, it follows TechDraw's preference, else inch units mean third angle; the answer says which (`projectionFrom`).
- Paper and scale are chosen together: the largest standard scale (1:1, 2:1, 1:2 …) at which the views, with room for their dimensions, fill no more than about 70% of the sheet, and the smallest paper at that scale. The iso view may get a smaller scale of its own (said under its name). `fill` in the answer is how full the sheet is.
- Only the overall sizes are dimensioned. Holes, slots and fits want dimensions placed in TechDraw by the person, on the page made.
- `file` can be a full path: its folder is made, and the PDF, SVG and DXF share its name without the extension.
- `holes: true` calls out every round hole once per size, with a leader, in a view that sees it end on (front, then right, then top …). FreeCAD's own Holes are called out as they are made: size or thread, THRU or ↧ depth, ⌴ counterbore or ⌵ countersink (`4× ⌀8 THRU ⌴⌀13 ↧8.5`). Holes no drawn view sees end on go in a hole table on the sheet.
- The title block's sample texts (names, numbers) are emptied, never filled with a made-up name. Give `drawnBy` only when the person tells you whose name goes there.
- The title block gives the material by its name, never by its id.
- `scale` is refused when it does not fit; leave it out for the largest standard scale that does.

## An assembly manual
- `drawing_exploded { steps: [{ title, add: [bodies], note }] }`, in build order. Bodies the same shape are counted as one item in the bill of materials.
- Record materials (`part_spec`) and setups first, or the bill has no mass or process for them.

## Patent figures and a draft
- `patent_figures` then `patent_draft`, so the draft uses the same numerals and figures.
- The draft is a starting point for a registered patent attorney or agent. Never present it as ready to file, and never file, send or upload it: that is the person's and counsel's.
- Formal drawing rules change, and an examiner may ask for changes. The figures follow the USPTO's margins and lettering size; say that is all they promise.

## Sections
- `drawing_make { section: "front" }` draws that view cut through the middle (`sectionAt` mm towards the viewer moves the plane): the material in front taken away, the cut faces hatched, titled SECTION A-A, and the cutting line drawn and lettered in a view that sees the plane edge on (top for a front section). The TechDraw page gets TechDraw's own section view.
- Cut through what matters: a bore's axis, a pocket's middle, the thinnest wall. Feature `dims` on that view measure the cut.
