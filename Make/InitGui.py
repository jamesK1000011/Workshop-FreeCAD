# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Make: its own workbench, "Workshop Make": setups,
# checks, fits, hardware and output, each a command over Make's own runner
# (the handler the agent's tool calls), and its panel (Setups, Materials,
# Fits, Review). Needs no other add-on.
import os

import FreeCAD
import FreeCADGui

import workshop_make

# Its icons, by file stem: the commands' Pixmap names (design 5).
_ICONS = os.path.join(os.path.dirname(os.path.abspath(workshop_make.__file__)), "icons")
FreeCADGui.addIconPath(_ICONS)

try:
    from workshop_make import commands as _make_commands  # registers the commands
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    _make_commands = None
    FreeCAD.Console.PrintWarning(f"Workshop Make: commands not loaded ({e}).\n")


class WorkshopMakeWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Make"
    Icon = os.path.join(_ICONS, "Workshop_Make_Workbench.svg")
    ToolTip = "How each part is made: setups, printability and DFM checks, fits, hardware, slicing (Workshop for FreeCAD)"

    def Initialize(self):
        from workshop_make import commands

        p = commands.PREFIX
        for name, cmds in commands.TOOLBARS:
            self.appendToolbar(name, [p + c for c in cmds])
        self.appendMenu("&Make", [p + c for _n, cmds in commands.TOOLBARS for c in cmds] + [p + "Panel"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WorkshopMakeWorkbench())
