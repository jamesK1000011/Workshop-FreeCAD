# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics' FreeCAD commands: a KiCad board read into the active document.
import FreeCAD
import FreeCADGui

from . import api


class ImportBoard:
    def GetResources(self):
        return {"Pixmap": "Workshop_Electronics_ImportBoard", "MenuText": "KiCad board…", "ToolTip": "Read a KiCad board (.kicad_pcb, KiCad 5 to 9; KiCad not needed) into the document as a solid: its outline, cut-outs and mounting holes."}

    def IsActive(self):
        return True

    def Activated(self):
        from PySide import QtGui

        from workshop_electronics.refusal import Refused

        path, _ = QtGui.QFileDialog.getOpenFileName(None, "KiCad board", "", "KiCad board (*.kicad_pcb)")
        if not path:
            return
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction("KiCad board")
        try:
            o = api.add_board(doc, api.read_board(path))
        except (Refused, ValueError) as e:
            doc.abortTransaction()
            FreeCAD.Console.PrintError(f"Workshop: {getattr(e, 'message', e)}\n")
            return
        doc.commitTransaction()
        FreeCAD.Console.PrintMessage(f"Workshop: read {o.Label}.\n")
        try:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass


NAMES = ["Workshop_Electronics_ImportBoard"]
FreeCADGui.addCommand(NAMES[0], ImportBoard())
