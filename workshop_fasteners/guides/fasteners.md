# Fasteners

Screws, bolts, nuts, washers, heat-set inserts, PEM parts, pins and retaining rings come from **Fasteners Workbench** (Shai Seger; its screw_maker by Ulrich Brammer; LGPL-2.1-or-later), a separate add-on. Workshop calls it; these tools exist only when it is installed. Say where a part came from when you name it.

## Finding one
- `fastener_types { query: "socket cap" }`, `{ standard: "ISO", kind: "nut" }`: types. ISO4762 socket head cap, ISO7380-1 button head, ISO10642 countersunk, ISO4017 hex head, ISO4032 nut, ISO7089 washer, IUTHeatInsert heat-set insert.
- `fastener_types { type }` lists its sizes. `{ type, size }` lists its lengths and the tap hole from Fasteners' calculator. For IUTHeatInsert it also gives the insert's hole and depth.

## Putting one in
- On holes: `fastener_add { type, edges: ["Plate.Edge7", …] }` puts one on each round edge. Leave `size` out and it matches the hole: `match: "outer"` for a pass hole (the screw goes through), `"inner"` for a tap hole (the thread bites). `invert` flips it, `offset` (mm) lifts it off the face.
- Pick an edge by a point: `edges: [{ body: "Stem", near: [x, y, z] }]`. Both work: a point on the round edge, or the hole's centre on its face (within 1 mm). At a centre the nearest centre wins, then the hole's outer rim, where the screw seats.
- A `size` given wins over the hole. Given on a counterbore's wall, the screw goes on the bore's edge at the counterbore's floor, where its head sits. The answer says so (`attachNote`) and gives the edge's diameter.
- Loose: `fastener_add { type, size, length, at: [x, y, z] }`.
- `length` takes the nearest length Fasteners has. `thread: "real"` models the thread. That's slow: use it for a render or a printed thread, not for fit checks.
- From a hole Workshop makes: `hw_hole { …, screw: true }` or `screw: { type, length }`. The screw goes in the hole, its length taken from the plate (less a counterbore). A nut trap's screw comes from the far side. An insert's screw is as long as the insert is deep, so add the thickness of what it clamps. `hw_hole` again on the same hole changes the screw already in it, never a second one.

## Kept on the hole, under one label
- Each fastener Workshop puts in keeps its hole by the edge's geometry as well as its name. When a later feature renumbers the Body's edges, it is put back on the same circle (`reattached` says from which edge to which). When no edge of that size is left near, it stays where it is and says so: `lost` on it, `warnings` in `fastener_list`, a warning in the Report view. Then `fastener_set { objects, edge }` puts it on a hole again. `fastener_list` gives each one's `hole`: kept, reattached or lost.
- Screws from an older document (made before Workshop kept them) are taken in as it opens or recomputes: their hole from the edge they are on now, and a label Fasteners counted up (`M8x25-Screw221`) put back in the scheme (`M8x25-Screw`). A name someone gave stays. `adopted: true` says so. If one was already on the wrong edge before, put it right with `fastener_set { edge }`.
- Labels read `M8x25-Screw`, then `M8x25-Screw 2` for the next of that size, and keep that through recomputes. Fasteners relabels at every recompute, and Workshop puts the label back. `fastener_set { objects: [one], label }` sets a name of your own, kept as given. Edits always change the object in place: its name and label stay.

## Changing and counting
- `fastener_set { objects, size | length | type | thread | invert | offset | match | edge | label }`, as Fasteners' Change Parameters, Flip and Move do. `type` takes another type with the same properties (a screw for a screw).
- `fastener_set { restore: true }`: a file saved where Fasteners wasn't loaded gets its fasteners back.
- `fastener_list` gives every fastener and the bill of materials, counted from the objects as they are now: each fastener once, a hidden one too (`hidden: true`; Fasteners' own BOM leaves it out, so `sheet: true` then writes Workshop's sheet), plus the links and arrays of it Fasteners counts. `sheet: true` writes it to a spreadsheet. `drawing_exploded`'s BOM and `mass_properties` list fasteners as bought hardware, not as parts.

## Printing threads
- `fastener_print` reads Fasteners' 3D-print thread settings. `{ mode: "3dprint", nut: [A, B], screw: [A, B] }` sets them: a printed thread's diameter is d × A + B.
- With Fasteners in 3dprint mode, Workshop's modelled threads on printed parts (`thread_cut`) take its nut scaling as their clearance. `thread_lookup` and `hw_hole` take its insert table over Workshop's typical figures. The answer names the source.
