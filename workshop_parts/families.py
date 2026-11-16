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

