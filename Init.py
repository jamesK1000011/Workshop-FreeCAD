# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD at start: its own packages first on the path, ahead of
# any old WorkshopParts/Make/Electronics/Documents or SafetyNet folder still
# beside it, which is said in one line (workshop/stale.py; Agent Link's
# update sets those folders aside). Agent Link, when installed, finds
# workshop.agentlink_families.
try:
    from workshop import stale as _workshop_stale

    _workshop_stale.prefer_own()
except Exception as _e:  # noqa: BLE001 — never stop FreeCAD starting
    import FreeCAD

    FreeCAD.Console.PrintWarning(f"Workshop: start-up check skipped ({_e}).\n")
