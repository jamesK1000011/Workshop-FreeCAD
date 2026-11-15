# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Documents when both are installed: drawing_make,
# drawing_exploded, patent_figures, patent_draft and library_pack, with their
# guides. Agent Link finds this module by convention and never names it;
# without Agent Link it is never loaded.
from . import fam_drawing, fam_share

FAMILIES = [fam_drawing, fam_share]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"
AGENTLINK_API = ">=1,<2"

