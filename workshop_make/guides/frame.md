# Frames and printed strength

## Frames
- `fea_frame` solves a frame of straight members with beam elements: members by ends and section (rect, circ, pipe, box), or BIM bodies (their centre lines and sizes, joined within `tolerance`). Supports pinned, fixed or roller at member ends; loads along members (N/mm, or kPa over a width) and at joints; `gravity` for own weight. Each member's stress, safety, deflection (span over deflection; `deflectionLimit` judges it) and each support's reaction. Checked: a simple beam's stress and deflection within 1 % of the textbook.
- Needs CalculiX (`ccx`). FreeCAD's FEM preference for ccx is used when set.

## A printed part
1. `fea_setup { body, buildDir }`: the build direction (+z from the part's print setup when it has one).
2. With a sliced OrcaSlicer project: `fea_setup { body, printed: { project, object } }` reads back its walls, infill and layers.
3. `fea_solve` then adds `acrossLayers` (the tension along the build direction, its face and its safety against half the yield) and, with a project, `asPrinted` (safety and displacement scaled by the print's knock-downs, with what would make it stronger).

## Traps
- Across the layers is a simplification (0.5 × yield): a real printed part can be weaker still, and is weakest where layers are pulled apart.
- As printed is an estimate from the slicer's settings on the solid body's solve: a feasibility check, never a sign-off.
