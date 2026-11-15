# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Electronics: its own workbench, "Workshop
# Electronics", with its commands in a toolbar and menu. Needs no other
# add-on.
import os

import FreeCAD
import FreeCADGui

import workshop_electronics

# Its icons, by file stem: the commands' Pixmap names (design 5).
_ICONS = os.path.join(os.path.dirname(os.path.abspath(workshop_electronics.__file__)), "icons")
FreeCADGui.addIconPath(_ICONS)

try:
    from workshop_electronics import commands as _electronics_commands  # registers the commands
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    _electronics_commands = None
    FreeCAD.Console.PrintWarning(f"Workshop Electronics: commands not loaded ({e}).\n")


class WorkshopElectronicsWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Electronics"
    Icon = os.path.join(_ICONS, "Workshop_Electronics_Workbench.svg")
    ToolTip = "Boards and wiring: KiCad boards read in, enclosures round them (Workshop for FreeCAD)"

    def Initialize(self):
        from workshop_electronics import commands

        self.appendToolbar("Electronics", commands.NAMES)
        self.appendMenu("&Electronics", commands.NAMES)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopElectronicsWorkbench())
