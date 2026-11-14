# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from this add-on when both are installed: the tools
# gen_make and gen_part, a thin layer over workshop_parts.api. Agent Link
# finds this module by convention (a package on the path holding
# agentlink_families) and never names it; without Agent Link it is never
# loaded.
from . import fam_parts

FAMILIES = [fam_parts]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"


def _guides():
    # The parts guide beside Agent Link's own (guide_read { topic: "parts" }).
    import os

    from agentlink import tools as al_tools

    reg = getattr(al_tools, "register_guides", None)
    if reg is not None:
        reg(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides"))


try:
    _guides()
except Exception:  # noqa: BLE001 — an Agent Link without the hook: the tools still load
    pass
