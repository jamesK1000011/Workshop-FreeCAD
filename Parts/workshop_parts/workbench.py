# SPDX-License-Identifier: LGPL-2.1-or-later
# The Workshop Parts workbench and its commands' registration; InitGui.py calls
# add(). It is built here, in a real module, because FreeCAD runs InitGui.py
# with exec() and a separate locals dict: a class body or a method body there
# sees only FreeCAD's own globals, never the names InitGui.py defines.
import os

# Its icons, by file stem: the commands' Pixmap names (design 5).
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def make_class(Gui):
    """WorkshopPartsWorkbench on this FreeCADGui's Workbench base."""

    class WorkshopPartsWorkbench(Gui.Workbench):
        MenuText = "Workshop Parts"
        Icon = os.path.join(ICONS, "Workshop_Parts_Workbench.svg")
        ToolTip = "Standard parts made to size: Gridfinity bins and baseplates, project boxes, enclosures round a board (Workshop for FreeCAD)"

        def Initialize(self):
            from . import commands

            self.appendToolbar("Parts", commands.NAMES)
            self.appendMenu("&Parts", commands.NAMES)

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    return WorkshopPartsWorkbench


def add(Gui=None):
    """The icons, the commands and the workbench: what InitGui.py calls."""
    if Gui is None:
        import FreeCADGui as Gui
    Gui.addIconPath(ICONS)
    try:
        from . import commands  # noqa: F401 — registers the commands
    except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
        import FreeCAD

        FreeCAD.Console.PrintWarning(f"Workshop Parts: commands not loaded ({e}).\n")
    cls = make_class(Gui)
    Gui.addWorkbench(cls())
    return cls
