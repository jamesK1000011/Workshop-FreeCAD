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


# Each generator's fields as a person reads them: words and units, not the
# parameter names the agent uses (millimetre fields show "mm" in the box).
_BOX = {"length": "Length", "width": "Width", "height": "Height", "wall": "Wall", "floor": "Floor",
        "radius": "Corner radius", "lid": "Lid thickness", "lip": "Lid lip depth", "clearance": "Lip clearance",
        "bosses": "Screw bosses", "screw": "Screw size", "gap": "Lid spacing on the bed"}
# A board box's gap is round the board; its lid's spacing is gapLid.
_BOARD = dict(_BOX, board="Board size", thickness="Board thickness", holes="Mounting holes", screw="Screw size",
              standoff="Standoff height", headroom="Headroom over board", gap="Board to wall gap",
              openings="Connector openings", margin="Opening margin", gapLid="Lid spacing on the bed")
LABELS = {
    "gridfinity_bin": {"x": "Width (cells)", "y": "Depth (cells)", "units": "Height (units of 7 mm)", "lip": "Stacking lip",
                       "magnets": "Magnet holes", "screws": "Screw holes", "wall": "Wall", "floor": "Floor",
                       "dividersX": "Dividers across", "dividersY": "Dividers front to back", "label": "Label ledge depth",
                       "holes": "Hole allowance"},
    "gridfinity_baseplate": {"x": "Width (pockets)", "y": "Depth (pockets)", "style": "Style", "floor": "Magnet floor"},
    "project_box": _BOX,
    "board_box": _BOARD,
}

# The list fields as tables: [(key, column header, "num" or the choices)];
# "pair" for a size X × Y.
COLUMNS = {
    "board_box": {
        "board": "pair",
        "holes": [("x", "X from board corner", "num"), ("y", "Y from board corner", "num")],
        "openings": [("side", "Side", ("front", "back", "left", "right")), ("at", "Middle from corner", "num"),
                     ("width", "Width", "num"), ("height", "Height", "num"), ("z", "Bottom over board", "num")],
    },
}

# A field used only with another's choice: off otherwise.
NEEDS = {"gridfinity_baseplate": {"floor": ("style", ("magnets",))}}


class Make:
    def __init__(self, generator):
        self.generator = generator

    def GetResources(self):
        return {"MenuText": title(api.NAMES[self.generator]) + "…", "ToolTip": TIPS[self.generator], "Pixmap": command_name(self.generator)}

    def IsActive(self):
        return True

    def Activated(self):
        from workshop_parts import form

        if form.busy():
            return
        doc = FreeCAD.ActiveDocument or FreeCAD.newDocument()
        form.show(title(api.NAMES[self.generator]), api.params(self.generator), TIPS[self.generator],
                  run=lambda values: run(doc, self.generator, values),
                  summary=lambda values: summary(doc, self.generator, values), doc=doc,
                  labels=LABELS.get(self.generator), columns=COLUMNS.get(self.generator), needs=NEEDS.get(self.generator))


def run(doc, generator, values):
    """The task panel's OK: the part made in doc. (ok, what to say)."""
    from workshop_parts.refusal import Refused

    try:
        out = api.make(doc, generator, values)
    except Refused as e:
        return False, e.message
    FreeCAD.Console.PrintMessage(api.report_line(out) + "\n")
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
    return f"Printer calibration: {api.calibration_said(api.calibration(doc)[1])}."


def command_name(generator):
    """The command (and its icon's file stem) for a generator."""
    return "Workshop_Parts_" + "".join(w.title() for w in generator.split("_"))


NAMES = []
for g in api.GENERATORS:
    n = command_name(g)
    FreeCADGui.addCommand(n, Make(g))
    NAMES.append(n)
