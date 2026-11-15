# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics' FreeCAD commands: a KiCad board read into the active document,
# through a task panel (taskpanels.py), not a modal dialog.
import FreeCAD
import FreeCADGui



class ImportBoard:
    def GetResources(self):
        return {"Pixmap": "Workshop_Electronics_ImportBoard", "MenuText": "KiCad Board…", "ToolTip": "Read a KiCad board (.kicad_pcb, KiCad 5 to 9; KiCad not needed) into the document as a solid: its outline, cut-outs and mounting holes."}

    def IsActive(self):
        return True

    def Activated(self):
        from workshop_electronics import taskpanels

        taskpanels.show_import_board(FreeCAD.ActiveDocument or FreeCAD.newDocument())


NAMES = ["Workshop_Electronics_ImportBoard"]
FreeCADGui.addCommand(NAMES[0], ImportBoard())
