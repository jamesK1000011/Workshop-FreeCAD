# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Make: its own workbench, "Workshop Make". It holds
# no commands yet — Make's setups, checks, fits and slicing are its tools
# for agents and its API for now; the buttons come with its panels. Needs no
# other add-on.
import FreeCADGui


class WorkshopMakeWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Make"
    ToolTip = "How each part is made: setups, printability and DFM checks, fits, hardware, slicing (Workshop for FreeCAD; its buttons are still to come)"

    def Initialize(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopMakeWorkbench())
