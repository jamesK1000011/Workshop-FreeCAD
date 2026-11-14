# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Parts: its commands in the Workshop workbench.
try:
    from workshop_common import workbench
    from workshop_parts import commands

    workbench.add("Parts", commands.NAMES)
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    import FreeCAD

    FreeCAD.Console.PrintWarning(f"Workshop Parts: commands not loaded ({e}); is the Workshop Common add-on installed?\n")
