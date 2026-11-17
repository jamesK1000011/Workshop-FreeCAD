# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for the Parts add-on: gen_make (Gridfinity bins) and
# gen_part (baseplates, project boxes, board enclosures), the names they have
# always had: the handlers in handlers.py (no Agent Link import there) bound
# to the session, with their descriptions and schemas. Loaded by Agent Link
# only.

import json

from . import api, handlers

GROUP = "parts"
LEAN = True  # listed by default
INFO = "Standard parts made to size (Workshop for FreeCAD · Parts): Gridfinity bins (gen_make), baseplates, project boxes and board enclosures with lids (gen_part)."

# What the window shows while these run (Agent Link's echo): the Workshop
# Parts bench, the button of the generator made, "Parts › …" in Activity.
# COMMANDS is the echo declaration ({tool or prefix: FreeCAD command name});
# gen_part's button depends on the generator asked for, so it is not in it.
WORKBENCHES = {"gen_": "PartDesignWorkbench"}  # Standard Parts, beside the additive primitives
AREAS = {"gen_": "Parts"}
COMMANDS = {"gen_make": "Workshop_Parts_GridfinityBin"}
# The answer's keys that name what a call made (its bodies' labels), for
# Agent Link's echo to select and frame them (its OUT_MORE; an echo that
# does not read this frames what is new in the document instead).
OUT_MORE = {"gen_make": ("bodies",), "gen_part": ("bodies",)}


def command_for(name, args):
    """Alias kept for the per-generator button (gen_part, or gen_make with a
    generator named): one per generator, as commands.py names them; COMMANDS
    otherwise."""
    gen = (args or {}).get("generator")
    if name in ("gen_make", "gen_part") and gen in api.GENERATORS:
        return "Workshop_Parts_" + "".join(w.title() for w in gen.split("_"))
    if gen is not None and name in ("gen_make", "gen_part"):
        return None
    return COMMANDS.get(name)


def tools(session):
    from agentlink.protocol import Tool, ToolError

    handlers.lend(ToolError=ToolError)
    h = handlers.bound(session)

    def table(g):
        """A generator's parameters as the description lists them: each
        with its range or choices, its default and what it is (from the
        generator's own table, so it cannot go stale)."""
        rows = []
        for k, v in api.GENERATORS[g].items():
            if v.get("kind") in ("int", "num"):
                rng = f"{v.get('min'):g}–{v.get('max'):g}, "
            elif v.get("kind") == "enum":
                rng = "|".join(str(x) for x in v.get("values", [])) + ", "
            else:
                rng = ""
            rows.append(f"{k} ({rng}default {json.dumps(v.get('default'))}): {str(v.get('tip', '')).rstrip('.')}")
        return "; ".join(rows)

    reply = ("Reply: generator, values (every parameter as used, defaults filled in), parts [{ name, volume mm³, min, max, size }], bodies [labels], sound { label: true|false }, "
             "printerFit (the calibration the holes took), movedBy (when it was put beside what is already there), step")
    health = " A changing call's reply may also carry health { ok, verdict, todo } from the shared check."
    make_desc = ("Make a Gridfinity bin to size as a new body (open Gridfinity profile, 42 mm cells, 7 mm height units), centred on the origin in X and Y and standing on z = 0, or put 10 mm clear beside (+X of) what the document already holds. "
                 "generator: gridfinity_bin (the only one here; gen_part makes baseplates and boxes). name: the body's label (left out: \"Gridfinity bin 2x1x4\" style; a second of the same gets \" 2\"). "
                 "params { " + table("gridfinity_bin") + " }. Counts are whole numbers, sizes mm; an unknown key or a value out of range is refused with the keys or the range. "
                 "measure: true builds it and answers the sizes without adding anything (made: false). "
                 "The body is a plain Part solid (Part::Feature), not a PartDesign Body: hw_embed, mass_ballast and the part_ tools work on it directly; it has no feature history to edit — make it again with other params instead. "
                 "It takes a second or two; bins of many cells with dividers a little longer. magnets: true leaves four 6 x 2 mm holes under each cell, open to the bed: press them in after printing, or drop them in at the pause — "
                 "encased { what, pauseAt mm, note } gives the height, hw_pauses lists it once the bin is in a print setup, and slice writes the pause. "
                 + reply + ", encased." + health)
    part_desc = (
        "Make a standard part to size, each piece its own new body (a box and its lid are two; the lid is laid beside the box, printed top down — turn it over about X to put it on). generator (required): "
        "gridfinity_baseplate (42 mm pockets; style open, or magnets: a floor with four 6 x 2 holes a pocket), project_box (a box and lid; bosses: corner screw bosses with pilot holes and clearance holes in the lid), "
        "board_box (an enclosure round a circuit board: standoffs under its mounting holes, connector openings, a lid; for a KiCad board, board_enclosure reads all that from the import instead). "
        "name: the body's label (the lid gets \" lid\" after it). Holes take the printer's fit calibration kept with the document (fit calibrate); without one they are made 0.2 mm big and printerFit says so. "
        "measure: true builds it and answers the sizes without adding anything (made: false). The parts go at the origin in an empty document, else 10 mm clear beside (+X of) what is there (movedBy). "
        "They are plain Part solids (Part::Feature), no feature history: make it again with other params to change it. A wrong generator, an unknown key or a value out of range is refused with what is allowed. "
        "Params — " + " | ".join(f"{g}: {table(g)}" for g in api.GENERATORS if g != "gridfinity_bin")
        + ". " + reply + ", and what the generator says of what it made: outside and inside [x, y, z], lid { plate, lip, clearance, at, note }, bosses or standoffs { screw, at, pilot, pilotDepth … }, boardAt, openings, and for a baseplate pockets (how many), height and magnets." + health)
    body = {"type": "string", "description": "The body's name; a lid gets ' lid' after it."}
    return [
        Tool("gen_make", make_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": ["gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "additionalProperties": False}, h["gen_make"], changes=True),
        Tool("gen_part", part_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": [g for g in api.GENERATORS if g != "gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "required": ["generator"], "additionalProperties": False}, h["gen_part"], changes=True),
    ]
