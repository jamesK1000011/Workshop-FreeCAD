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

# Fasteners Workbench installed: the screws Workshop puts in keep their hole
# (re-found by its geometry when FreeCAD renumbers edges) and their label
# (Fasteners relabels at every recompute). A document observer only;
# nothing of Fasteners is loaded or changed here.
try:
    from workshop_fasteners import detect as _workshop_fs_detect

    if _workshop_fs_detect.present():
        from workshop_fasteners import keep as _workshop_fs_keep

        _workshop_fs_keep.watch()
except Exception as _e:  # noqa: BLE001 — never stop FreeCAD starting
    import FreeCAD

    FreeCAD.Console.PrintWarning(f"Workshop: Fasteners keeper not started ({_e}).\n")
