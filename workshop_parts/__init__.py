# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD · Parts: standard parts made to size — Gridfinity bins
and baseplates, project boxes with lids, enclosures round a board.

    from workshop_parts import api
    api.make(doc, "gridfinity_bin", {"x": 2, "y": 1, "units": 4})

Every function takes and gives plain values in millimetres; a value out of
range is refused (workshop_parts.refusal.Refused) with its range."""

VERSION = "0.2.0"
