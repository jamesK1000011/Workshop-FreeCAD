# SPDX-License-Identifier: LGPL-2.1-or-later
# The Workshop Documents workbench and its commands' registration; InitGui.py calls
# add(). It is built here, in a real module, because FreeCAD runs InitGui.py
# with exec() and a separate locals dict: a class body or a method body there
# sees only FreeCAD's own globals, never the names InitGui.py defines.
import os

# Its icons, by file stem: the commands' Pixmap names (design 5).
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def make_class(Gui):
    """WorkshopDocumentsWorkbench on this FreeCADGui's Workbench base."""

    class WorkshopDocumentsWorkbench(Gui.Workbench):
        MenuText = "Workshop Documents"
        Icon = os.path.join(ICONS, "Workshop_Documents_Workbench.svg")
        ToolTip = "Drawings and documents from the bodies: dimensioned sheets, assembly manuals, patent figures, library packs (Workshop for FreeCAD)"

        def Initialize(self):
            from . import commands

            try:
                import TechDrawGui  # noqa: F401 — its icons (the buttons use them by name)
            except Exception:  # noqa: BLE001
                pass
            p = commands.PREFIX
            for name, cmds in commands.TOOLBARS:
                self.appendToolbar(name, [p + c for c in cmds])
            self.appendMenu("&Documents", [p + c for _n, cmds in commands.TOOLBARS for c in cmds] + [p + "Panel"])

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    return WorkshopDocumentsWorkbench


def add(Gui=None):
    """The icons, the commands and the workbench: what InitGui.py calls."""
    if Gui is None:
        import FreeCADGui as Gui
    Gui.addIconPath(ICONS)
    try:
        from . import commands  # noqa: F401 — registers the commands
    except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
        import FreeCAD

        FreeCAD.Console.PrintWarning(f"Workshop Documents: commands not loaded ({e}).\n")
    cls = make_class(Gui)
    Gui.addWorkbench(cls())
    return cls
