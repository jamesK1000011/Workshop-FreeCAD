# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Documents: its own workbench, "Workshop Documents".
# It holds no commands yet — drawings, manuals, patent figures and library
# packs are its tools for agents and its API for now (a drawing opens in
# TechDraw); the buttons come with its panel. Needs no other add-on.
import FreeCADGui


class WorkshopDocumentsWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Documents"
    ToolTip = "Drawings and documents from the bodies: dimensioned sheets, assembly manuals, patent figures, library packs (Workshop for FreeCAD; its buttons are still to come)"

    def Initialize(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopDocumentsWorkbench())
