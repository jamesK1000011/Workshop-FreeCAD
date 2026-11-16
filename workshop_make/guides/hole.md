# Holes for hardware

## The call
- `hw_hole { body, kind, size, at, dir, depth }`: kind clearance, counterbore, countersink, nut_trap, insert or magnet. `at` is where the hole enters, on a flat face; `dir` runs into the material from there.
- In a PartDesign Body it is FreeCAD's own Hole, editable with a double-click. In a plain Part solid it is cut as a shape (`route` says which).

## Which face the head is on
- The screw head, counterbore, countersink or nut trap is always on the face `at` is on: `dir` points away from it. The answer's `headSide` says it ("countersink on the face at x=0, facing -x").
- A wall-mount bracket: the countersink goes on the face away from the wall, where the screw goes in. Enter from that face (`at` on it, `dir` towards the wall), not from the wall side. Read `headSide` before going on.

## The printer allowance
- With a printer calibration (`fit calibrate`) the hole and its cut are made that much larger. FreeCAD sets a sized hole's diameter again from its size and fit whenever the file is opened, so with an allowance the Hole is FreeCAD's plain hole (Profile None) at FreeCAD's size plus the allowance. The answer's `allowanceOn` names the properties; the size and fit are in the Hole's description (Label2).
- To change the size, run `hw_hole` again. A size picked in the Hole's own panel takes FreeCAD's size without the allowance.
