# SPDX-License-Identifier: LGPL-2.1-or-later
# The fasteners group for Agent Link, joined by workshop/agentlink_families,
# only when Fasteners Workbench is installed (detect.find(): folder checks,
# nothing imported). Absent, FAMILIES is empty: no tools, no group, no
# guide, no extension of hw_hole — no token cost.
from . import detect

AGENTLINK_API = ">=1,<2"
FAMILIES = []
if detect.present():
    from . import fam_fasteners

    FAMILIES = [fam_fasteners]
