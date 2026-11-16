# Fasteners

Screws, bolts, nuts, washers, heat-set inserts, PEM parts, pins and retaining rings come from **Fasteners Workbench** (Shai Seger; its screw_maker by Ulrich Brammer; LGPL-2.1-or-later), a separate add-on. Workshop calls it; these tools exist only when it is installed. Say where a part came from when you name it.

## Finding one
- `fastener_types { query: "socket cap" }`, `{ standard: "ISO", kind: "nut" }`: types. ISO4762 socket head cap, ISO7380-1 button head, ISO10642 countersunk, ISO4017 hex head, ISO4032 nut, ISO7089 washer, IUTHeatInsert heat-set insert.
- `fastener_types { type }` lists its sizes. `{ type, size }` lists its lengths and the tap hole from Fasteners' calculator. For IUTHeatInsert it also gives the insert's hole and depth.

## Putting one in
- On holes: `fastener_add { type, edges: ["Plate.Edge7", …] }` puts one on each round edge. Leave `size` out and it matches the hole: `match: "outer"` for a pass hole (the screw goes through), `"inner"` for a tap hole (the thread bites). `invert` flips it, `offset` (mm) lifts it off the face.
- Loose: `fastener_add { type, size, length, at: [x, y, z] }`.
- `length` takes the nearest length Fasteners has. `thread: "real"` models the thread. That's slow: use it for a render or a printed thread, not for fit checks.
- From a hole Workshop makes: `hw_hole { …, screw: true }` or `screw: { type, length }`. The screw goes in the hole, its length taken from the plate (less a counterbore). A nut trap's screw comes from the far side. An insert's screw is as long as the insert is deep, so add the thickness of what it clamps.

## Changing and counting
- `fastener_set { objects, size | length | type | thread | invert | offset | match | edge }`, as Fasteners' Change Parameters, Flip and Move do. `type` takes another type with the same properties (a screw for a screw).
- `fastener_set { restore: true }`: a file saved where Fasteners wasn't loaded gets its fasteners back.
- `fastener_list` gives every fastener and the bill of materials, counted as Fasteners counts them (links and arrays too). `sheet: true` writes it to a spreadsheet. `drawing_exploded`'s BOM and `mass_properties` list fasteners as bought hardware, not as parts.

## Printing threads
- `fastener_print` reads Fasteners' 3D-print thread settings. `{ mode: "3dprint", nut: [A, B], screw: [A, B] }` sets them: a printed thread's diameter is d × A + B.
- With Fasteners in 3dprint mode, Workshop's modelled threads on printed parts (`thread_cut`) take its nut scaling as their clearance. `thread_lookup` and `hw_hole` take its insert table over Workshop's typical figures. The answer names the source.
