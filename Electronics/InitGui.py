# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Electronics: its commands in the Workshop workbench.
try:
    from workshop_common import workbench
    from workshop_electronics import commands

    workbench.add("Electronics", commands.NAMES)
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    import FreeCAD

    FreeCAD.Console.PrintWarning(f"Workshop Electronics: commands not loaded ({e}); is Workshop Common installed for the Workshop workbench?\n")
