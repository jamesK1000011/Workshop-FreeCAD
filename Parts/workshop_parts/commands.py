# SPDX-License-Identifier: LGPL-2.1-or-later
# The Parts add-on's FreeCAD commands: one per generator, each a task panel
# of its parameters (the same table the agent's values are checked against)
# in the Tasks tab, then api.make in the active document on OK (one undo
# step: the panel's transaction).
import FreeCAD
import FreeCADGui

from . import api


_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into", "of", "on", "or", "per", "the", "to", "vs", "via", "with"}


def title(text):
    """Menu text in Title Case, as FreeCAD's design guide asks for command
    names: each word capitalised but the small ones inside; a word that
    already has a capital (KiCad, DFM, STL) is left as it is."""
    words = text.split(" ")
    out = []
    for i, w in enumerate(words):
        if w and w[0].islower() and not any(c.isupper() for c in w) and (i == 0 or w not in _SMALL):
            w = w[0].upper() + w[1:]
        out.append(w)
    return " ".join(out)

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
        return {"MenuText": title(api.NAMES[self.generator]) + "…", "ToolTip": TIPS[self.generator], "Pixmap": command_name(self.generator)}

    def IsActive(self):
        return True

    def Activated(self):
        from workshop_parts import form

        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        form.show(api.NAMES[self.generator], api.params(self.generator), TIPS[self.generator],
                  run=lambda values: run(doc, self.generator, values),
                  summary=lambda values: summary(doc, self.generator, values), doc=doc)


def run(doc, generator, values):
    """The task panel's OK: the part made in doc. (ok, what to say)."""
    from workshop_parts.refusal import Refused

    try:
        out = api.make(doc, generator, values)
    except Refused as e:
        return False, e.message
    FreeCAD.Console.PrintMessage(f"Workshop: made {', '.join(out['bodies'])} ({out['printerFit']}).\n")
    try:
        FreeCADGui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass
    return True, ""


def summary(doc, generator, values):
    """The live line under the fields: whether the values will do, and the
    printer fit its holes take."""
    from workshop_parts.refusal import Refused

    try:
        api.check(generator, values)
    except Refused as e:
        return "Not yet: " + e.message
    return "Printer fit: " + api.calibration(doc)[1]


def command_name(generator):
    """The command (and its icon's file stem) for a generator."""
    return "Workshop_Parts_" + "".join(w.title() for w in generator.split("_"))


NAMES = []
for g in api.GENERATORS:
    n = command_name(g)
    FreeCADGui.addCommand(n, Make(g))
    NAMES.append(n)
