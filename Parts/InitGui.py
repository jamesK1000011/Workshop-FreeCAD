# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Parts: its own workbench, "Workshop Parts", with one
# command per generator in its toolbar and menu. Needs no other add-on.
import os

import FreeCAD
import FreeCADGui

import workshop_parts

# Its icons, by file stem: the commands' Pixmap names (design 5).
_ICONS = os.path.join(os.path.dirname(os.path.abspath(workshop_parts.__file__)), "icons")
FreeCADGui.addIconPath(_ICONS)

try:
    from workshop_parts import commands as _parts_commands  # registers the commands
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    _parts_commands = None
    FreeCAD.Console.PrintWarning(f"Workshop Parts: commands not loaded ({e}).\n")


class WorkshopPartsWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Parts"
    Icon = os.path.join(_ICONS, "Workshop_Parts_Workbench.svg")
    ToolTip = "Standard parts made to size: Gridfinity bins and baseplates, project boxes, enclosures round a board (Workshop for FreeCAD)"

    def Initialize(self):
        from workshop_parts import commands

        self.appendToolbar("Parts", commands.NAMES)
        self.appendMenu("&Parts", commands.NAMES)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopPartsWorkbench())
