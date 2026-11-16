# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for the Parts add-on: gen_make (Gridfinity bins) and
# gen_part (baseplates, project boxes, board enclosures), the names they have
# always had: the handlers in handlers.py (no Agent Link import there) bound
# to the session, with their descriptions and schemas. Loaded by Agent Link
# only.

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
        return ", ".join(f"{k} ({v.get('default')})" for k, v in api.GENERATORS[g].items())

    make_desc = ("Make a Gridfinity bin to size (open Gridfinity profile: 42 mm cells, 7 mm units): params " + table("gridfinity_bin")
                 + ". measure: true gives the sizes without adding it. Magnets: the pause height to drop them in is given (and the slicer's pause written by slice).")
    part_desc = (
        "Make a standard part to size, each piece its own body: gridfinity_baseplate (42 mm pockets; style open, or magnets), project_box (box and lid; "
        "bosses: corner screw bosses with pilot holes), board_box (an enclosure round a board: standoffs, connector openings, a lid; for a KiCad board, "
        "board_enclosure reads all that from the import). Holes take the printer's fit calibration (fit calibrate); without one, 0.2 mm big. measure: true "
        "builds it and gives the sizes without adding it. Params — " + " | ".join(f"{g}: {table(g)}" for g in api.GENERATORS if g != "gridfinity_bin")
        + " (mm and counts; a refused value is answered with its range).")
    body = {"type": "string", "description": "The body's name; a lid gets ' lid' after it."}
    return [
        Tool("gen_make", make_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": ["gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "additionalProperties": False}, h["gen_make"], changes=True),
        Tool("gen_part", part_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": [g for g in api.GENERATORS if g != "gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "required": ["generator"], "additionalProperties": False}, h["gen_part"], changes=True),
    ]
