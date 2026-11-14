# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for the Parts add-on: gen_make (Gridfinity bins) and
# gen_part (baseplates, project boxes, board enclosures), the names they have
# always had. Loaded by Agent Link only.

from workshop_common import Refused

from . import api

GROUP = "parts"
LEAN = True  # listed by default
INFO = "Standard parts made to size (Workshop for FreeCAD · Parts): Gridfinity bins (gen_make), baseplates, project boxes and board enclosures with lids (gen_part)."


def tools(session):
    from agentlink.protocol import Tool, ToolError

    s = session

    def run(generator, a, step):
        try:
            out = api.make(s.doc, generator, a.get("params") or {}, a.get("name"), bool(a.get("measure")))
        except Refused as e:
            raise ToolError(e.code, e.message)
        if out.get("made") is False:
            return out
        for label in out["bodies"]:
            s.meta[label] = {"generator": generator, "values": out["values"]}
        if out.get("encased"):
            s.meta[out["bodies"][0]]["encased"] = out["encased"]
        if out.get("magnets"):
            s.meta[out["bodies"][0]]["fitted"] = out["magnets"]
        s.snapshot(step)
        out["step"] = len(s.steps)
        mags = out.pop("encased", None)
        if mags:
            out["encased"] = {"what": f"{mags['count']} {mags['what']}", "pauseAt": mags["top"], "note": "The magnet holes open onto the bed: press the magnets in after printing, or drop them in at the pause and print over them."}
        return out

    def gen_make(a):
        gen = a.get("generator", "gridfinity_bin")
        if gen != "gridfinity_bin":
            raise ToolError("invalid_input", "generator: gridfinity_bin (gen_part makes baseplates and boxes).")
        return run(gen, a, "gen_make")

    def gen_part(a):
        gen = a.get("generator")
        if gen not in api.GENERATORS or gen == "gridfinity_bin":
            raise ToolError("invalid_input", f"generator: one of {', '.join(g for g in api.GENERATORS if g != 'gridfinity_bin')} (gridfinity_bin is gen_make's).")
        return run(gen, a, "gen_part")

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
        Tool("gen_make", make_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": ["gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "additionalProperties": False}, gen_make, changes=True),
        Tool("gen_part", part_desc, {"type": "object", "properties": {"generator": {"type": "string", "enum": [g for g in api.GENERATORS if g != "gridfinity_bin"]}, "params": {"type": "object"}, "name": body, "measure": {"type": "boolean"}}, "required": ["generator"], "additionalProperties": False}, gen_part, changes=True),
    ]
