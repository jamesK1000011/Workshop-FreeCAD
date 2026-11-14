# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Documents when both are installed: drawing_make,
# drawing_exploded, patent_figures, patent_draft and library_pack, with their
# guides. Agent Link finds this module by convention and never names it;
# without Agent Link it is never loaded.
import os

from . import fam_drawing, fam_share

FAMILIES = [fam_drawing, fam_share]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"
AGENTLINK_API = ">=1,<2"


def _guides():
    from agentlink import tools as al_tools

    reg = getattr(al_tools, "register_guides", None)
    if reg is not None:
        reg(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides"))


try:
    _guides()
except Exception:  # noqa: BLE001 — an Agent Link without the hook: the tools still load
    pass
