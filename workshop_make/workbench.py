# SPDX-License-Identifier: LGPL-2.1-or-later
# The Make workbench, the one workbench of the Workshop add-on:
# workshop/workbench.py builds it with make_class(). add() is a no-op left
# for an old WorkshopMake folder's InitGui. It is built here, in a real module, because FreeCAD runs InitGui.py
# with exec() and a separate locals dict: a class body or a method body there
# sees only FreeCAD's own globals, never the names InitGui.py defines.
import os

# Its icons, by file stem: the commands' Pixmap names (design 5).
ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def make_class(Gui):
    """WorkshopMakeWorkbench on this FreeCADGui's Workbench base."""

    class WorkshopMakeWorkbench(Gui.Workbench):
        MenuText = "Make"
        Icon = os.path.join(ICONS, "Workshop_Make_Workbench.svg")
        ToolTip = "How each part is made: setups, fits, encased hardware, slicing, cut and mill output, printers (Workshop for FreeCAD)"

        def Initialize(self):
            from . import commands

            from workshop import placement

            p = commands.PREFIX
            for name, cmds in commands.TOOLBARS:
                self.appendToolbar(name, [p + c for c in cmds])
            # The Make panel and the Manual panel (Documents'), each shown,
            # or slid in and out (PanelLayout left-slide).
            panels = list(placement.MAKE_PANELS)
            self.appendMenu("&Make", [p + c for _n, cmds in commands.TOOLBARS for c in cmds] + panels)
            self.appendToolbar("Make Panels", panels)

        def Activated(self):
            # Its panel with it: beside Model and Tasks (the panel layout
            # setting), in front the first time.
            try:
                from . import layout, panel

                # Opening the panel changes nothing: the window's "*" stays
                # as it was (layout.keep_marks).
                with layout.keep_marks():
                    panel.show()
            except Exception as e:  # noqa: BLE001 — never stop the bench (no window in tests)
                import FreeCAD

                FreeCAD.Console.PrintLog(f"Workshop Make: panel not shown ({e})\n")

        def Deactivated(self):
            # Leaving Make: a part the panel selected to show its work (a
            # review's) is not left selected; the person's own selection stays.
            try:
                from . import panel

                panel.put_back_selection()
            except Exception:  # noqa: BLE001 — never stop a workbench switch
                pass

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    return WorkshopMakeWorkbench


def add(Gui=None):
    """Nothing: Workshop's own InitGui (workshop/workbench.py) registers the
    Make workbench. Kept for an old WorkshopMake folder's InitGui.py, which
    calls this when it is still beside Workshop: it adds no second workbench
    (workshop/stale.py says the old folder is there)."""
    return None
