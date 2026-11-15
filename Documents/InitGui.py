# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Documents: its own workbench, "Workshop Documents":
# drawings, exploded assembly drawings, library packs and patent figures and
# drafts, each a command over Documents' own runner (the handler the agent's
# tool calls; a drawing's page opens in TechDraw), and its Manual panel.
# Needs no other add-on.
import FreeCAD
import FreeCADGui

try:
    from workshop_documents import commands as _documents_commands  # registers the commands
except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
    _documents_commands = None
    FreeCAD.Console.PrintWarning(f"Workshop Documents: commands not loaded ({e}).\n")


class WorkshopDocumentsWorkbench(FreeCADGui.Workbench):
    MenuText = "Workshop Documents"
    ToolTip = "Drawings and documents from the bodies: dimensioned sheets, assembly manuals, patent figures, library packs (Workshop for FreeCAD)"

    def Initialize(self):
        from workshop_documents import commands

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


FreeCADGui.addWorkbench(WorkshopDocumentsWorkbench())
