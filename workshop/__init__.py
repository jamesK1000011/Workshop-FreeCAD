# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD: one add-on for making things. Its parts live in the
packages beside this one (workshop_parts, workshop_make,
workshop_electronics, workshop_documents, safetynet, and workshop_fasteners —
the bridge to Fasteners Workbench, dormant without it), each with its own
Python API; this package is the add-on's own layer: the Make workbench and
the placement of every other command in FreeCAD's own workbenches
(placement.py, through a workbench manipulator), the one agentlink_families
module for Agent Link, and the helper files Agent Link vendors (layout.py)."""

VERSION = "0.4.0"
# The add-on's parts, in load order.
PARTS = ("workshop_parts", "workshop_make", "workshop_electronics", "workshop_documents", "safetynet", "workshop_fasteners")
