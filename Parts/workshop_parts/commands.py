# SPDX-License-Identifier: LGPL-2.1-or-later
# The Parts add-on's FreeCAD commands: one per generator, each a dialog of
# its parameters (the same table the agent's values are checked against),
# then api.make in the active document.
import FreeCAD
import FreeCADGui

from . import api

TIPS = {
    "gridfinity_bin": "A Gridfinity bin made to size: cells, height, lip, magnets, dividers.",
    "gridfinity_baseplate": "A Gridfinity baseplate: pockets for bins, open or with magnet holes.",
    "project_box": "A project box with its lid, optional screw bosses.",
    "board_box": "An enclosure round a circuit board, with standoffs and a lid.",
}


class Make:
    def __init__(self, generator):
        self.generator = generator

    def GetResources(self):
        return {"MenuText": api.NAMES[self.generator] + "…", "ToolTip": TIPS[self.generator], "Pixmap": command_name(self.generator)}

    def IsActive(self):
        return True

    def Activated(self):
        from workshop_parts.refusal import Refused
        from workshop_parts import form

        values = form.ask(api.NAMES[self.generator], api.params(self.generator), TIPS[self.generator])
        if values is None:
            return
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        doc.openTransaction(api.NAMES[self.generator])
        try:
            out = api.make(doc, self.generator, values)
        except Refused as e:
            doc.abortTransaction()
            FreeCAD.Console.PrintError(f"Workshop: {e.message}\n")
            return
        doc.commitTransaction()
        FreeCAD.Console.PrintMessage(f"Workshop: made {', '.join(out['bodies'])} ({out['printerFit']}).\n")
        try:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass


def command_name(generator):
    """The command (and its icon's file stem) for a generator."""
    return "Workshop_Parts_" + "".join(w.title() for w in generator.split("_"))


NAMES = []
for g in api.GENERATORS:
    n = command_name(g)
    FreeCADGui.addCommand(n, Make(g))
    NAMES.append(n)
