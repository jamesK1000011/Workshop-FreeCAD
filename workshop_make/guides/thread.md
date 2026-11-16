# Threads

## Sizes
- `thread_lookup { size }`: M1.6–M24 coarse, the common fine pitches, #4–1/2" UNC and UNF; major, pitch, minors, tap drill (mm).
- `thread_identify { faces: { near } }`: a hole or shaft's diameter and the nearest sizes. A hole may be a tap drill, a cosmetic minor or a modelled major — the answer says which reading fits.
- When sizes tie but for pitch (M10 or M10x1.25) it answers `needs: pitch`: ask the person, or measure with a thread gauge.

## Cutting
- `thread_cut { faces, size, mode }` uses FreeCAD's PartDesign Hole on an existing hole.
- cosmetic (default): the hole at the tapping size, the thread recorded; tap it after making.
- modelled: the thread cut into the part. Under M5 a printed thread rarely comes out clean: print the tapping hole and tap it, or use a heat-set insert (hw_hole).
- Outside threads (shafts) can only be recorded.
- In a PartDesign Body the thread is a feature that stays: a sketch at the hole's end and FreeCAD's own Hole (`route: "PartDesign Hole"`, `features`), editable in the Hole's panel. In a plain Part solid the result is written back as a plain shape (`route: "Part solid"`).
- A parametric Part object (a Part::Box, a boolean, an extrusion) is refused: FreeCAD would rebuild it at the next recompute and the thread would be gone. Work on a plain copy (`part_transform { op: "move", by: [0, 0, 0], copy: true }`), or `pd_clone` it into a Body.
