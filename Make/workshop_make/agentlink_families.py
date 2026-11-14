# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Make when both are installed: the make loop
# (setup, part_spec, dfm_check, part_review, slice), mass, fits and hardware
# holes, threads and encased parts — the names they have always had — with
# their guides; the wall map for view_render, the print pauses as a service,
# and the wall and scan-thread readers asked through Agent Link's hooks.
# Agent Link finds this module by convention and never names it; without
# Agent Link it is never loaded.
import os

from . import fam_embed, fam_fits, fam_make, fam_mass, fam_thread, maps, printability

AGENTLINK_API = ">=1,<2"
FAMILIES = [fam_make, fam_fits, fam_mass, fam_thread, fam_embed]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"


def _register():
    from agentlink import hooks, render
    from agentlink import tools as al_tools

    al_tools.register_guides(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides"))
    hooks.provide("print_pauses", fam_embed.pauses_for)
    hooks.provide("printer_volume", lambda name: printability.PRINTERS.get(name or "generic", printability.PRINTERS["generic"]))
    # One list of wall readers: whatever add-on reads walls better is asked
    # by the printability check here.
    printability.WALL_READERS = hooks.readers("wall")
    render.register_map("wall", maps.wall, maps.ABOUT)


try:
    _register()
except Exception:  # noqa: BLE001 — an Agent Link without these hooks: the tools still load
    pass
