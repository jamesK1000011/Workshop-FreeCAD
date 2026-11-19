# Slicing with another slicer

## The loop
1. The body needs a print setup. `slice_with { slicer: "prusaslicer" | "orcaslicer" | "bambustudio" }`.
2. Give the person's own profiles when they have them: `profiles: { machine, process, filament }` (JSON exported from OrcaSlicer or Bambu Studio), or `{ config }` (a PrusaSlicer .ini). Without them minimal profiles are written from the setup, and the slicer's defaults fill the rest.
3. The pauses for encased parts are written in. `hw_pauses` lists them.

## Traps
- A slicer not on this computer is refused, naming those present. AGENTLINK_ORCASLICER and AGENTLINK_BAMBUSTUDIO set their paths.
- Bambu printers pause on `M400 U1`; Klipper on `PAUSE` (give it as `pauseCommand`). pauseCommand takes only M601, M600, M0, M1 or PAUSE, one command, no new lines.
- OrcaSlicer and Bambu Studio are not run by this add-on's tests: check the first G-code they give.
- A part whose material is no printing filament (a metal, a wood) is refused by `slice`, naming the call that fixes it: `material_set { bodies: ["Bracket"], id: "petg" }` records a filament for the body (ask the person which first). To try a filament without recording it, `slice { body: "Bracket", material: "petg" }` (or `slice_with { ..., material }`) slices in it this time only; the body's material stays as it was. A filament profile or the setup's presets win over `material`.

## The person's own presets
- `slicer_presets { action: "list", slicer: "bambustudio", query: "H2D" }` lists the printer, process and filament presets on this computer, the person's own first. `use { body, machine, process, filament }` puts them on the body's print setup: from then on its layer height, walls, infill and shells come from them (so the checks and the printed mass agree with the slice), and `slice` slices with that slicer and those presets.
- Presets are data: `export` writes the three, flattened, as one JSON file (and keeps it by name); `import` takes such a file on another computer, and `use { bundle }` chooses it. Nothing of a printer is in the code; the minimal profiles used when none are chosen are a data file too.
- Ask which presets the person prints with rather than guessing: the right printer and nozzle matter more than any setting.
