# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Make when both are installed: the tools fit,
# hw_hole, thread_* and hw_embed*, the names they have always had, and the
# guides; the print pauses offered as a service, the scan-thread readers
# asked through Agent Link's hooks. Agent Link finds this module by
# convention and never names it; without Agent Link it is never loaded.
import os

from . import fam_embed, fam_fits, fam_thread

AGENTLINK_API = ">=1,<2"
FAMILIES = [fam_fits, fam_thread, fam_embed]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"


def _register():
    from agentlink import hooks
    from agentlink import tools as al_tools

    al_tools.register_guides(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides"))
    hooks.provide("print_pauses", fam_embed.pauses_for)


try:
    _register()
except Exception:  # noqa: BLE001 — an Agent Link without these hooks: the tools still load
    pass
