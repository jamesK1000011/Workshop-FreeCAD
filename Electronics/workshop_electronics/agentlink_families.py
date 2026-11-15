# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Electronics when both are installed: the tools
# kicad_import, board_enclosure, pcb_order_package and printed_channel, with
# their guide. Agent Link finds this module by convention and never names
# it; without Agent Link it is never loaded.
from . import fam_electronics

FAMILIES = [fam_electronics]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"
AGENTLINK_API = ">=1,<2"

