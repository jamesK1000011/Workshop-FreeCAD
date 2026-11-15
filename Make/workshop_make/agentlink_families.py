# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Make when both are installed: the make loop
# (setup, part_spec, dfm_check, part_review, slice), mass, fits and hardware
# holes, threads, encased parts, slicing, printers, the cut and mill checks
# and frames (fea_frame) — the names they have always had — with their
# guides; the wall map for view_render, the print pauses as a service, the
# print-aware strength on fea_setup and fea_solve, and the wall and
# scan-thread readers asked through Agent Link's hooks.
# Agent Link finds this module by convention and never names it; without
# Agent Link it is never loaded. It also hosts Make's panel tabs (Setups,
# Materials, Fits) in Agent Link's panel over its panel._call, gives its
# Review tab the part_review verdict, and says Make is hosted (so Make's own
# dock stays away).
from . import handlers
from . import fam_cut, fam_embed, fam_fits, fam_frame, fam_make, fam_mass, fam_mill, fam_printer, fam_slicing, fam_thread, maps, printability, printed

AGENTLINK_API = ">=1,<2"
FAMILIES = [fam_make, fam_fits, fam_mass, fam_thread, fam_embed, fam_slicing, fam_printer, fam_cut, fam_mill, fam_frame]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"


def _register():
    from agentlink import hooks, render

    hooks.provide("print_pauses", fam_embed.pauses_for)
    # One list of wall readers: whatever add-on reads walls better is asked
    # by the printability check here.
    printability.WALL_READERS = hooks.readers("wall")
    render.register_map("wall", maps.wall, maps.ABOUT)
    # Print-aware strength on Agent Link's FEM tools.
    printed.register(hooks)


def _host():
    """Make's panel tabs in Agent Link's panel and its reviewer."""
    import workshop_make

    from agentlink import hooks

    workshop_make._hosted = True
    if hasattr(hooks, "register_tab"):
        from . import panel

        for title, cls, order in panel.HOSTED:
            if not any(t.get("title") == title for t in getattr(hooks, "TABS", [])):
                hooks.register_tab(title, panel.factory(cls), order)
    if hasattr(hooks, "register_reviewer"):
        hooks.register_reviewer(handlers.review)


try:
    _register()
except Exception:  # noqa: BLE001 — an Agent Link without these hooks: the tools still load
    pass
try:
    _host()
except Exception:  # noqa: BLE001 — no Qt (a headless Agent Link): the tools still load
    import workshop_make

    workshop_make._hosted = True
