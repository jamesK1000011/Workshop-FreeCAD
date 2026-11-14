# SPDX-License-Identifier: LGPL-2.1-or-later
# The Workshop workbench: the commands of every Workshop add-on installed.
import FreeCADGui


class WorkshopWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop"
    ToolTip = "Making things: printable parts, standard parts, boards and documents (FreeCAD Workshop add-ons)"

    def Initialize(self):
        from workshop_common import workbench

        for menu, names in workbench.MENUS.items():
            self.appendToolbar(f"Workshop {menu}", names)
            self.appendMenu(["&Workshop", menu], names)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopWorkbench())
