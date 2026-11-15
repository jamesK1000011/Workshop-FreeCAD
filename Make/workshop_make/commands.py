# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's FreeCAD commands: each runs one of Make's tools through its own
runner (workshop_make.runner: the handler the agent's tool calls, one undo
step), on the part selected or the one there is. Forms open as task panels.
Icons: Make's own (icons/, by file stem) where FreeCAD has none to reuse,
else FreeCAD's own by name. No agent and no Agent Link needed."""
import FreeCAD
import FreeCADGui

from . import runner as R
from . import taskpanels as T


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

PREFIX = "Workshop_Make_"


def report(title, ok, out):
    """The answer in the Report view: refusal, findings, the figures."""
    c = FreeCAD.Console
    if not ok:
        c.PrintError(f"Workshop Make · {title}: {(out.get('error') or {}).get('message', 'refused')}\n")
        return
    lines = [f"Workshop Make · {title}:"]
    for k, v in out.items():
        if isinstance(v, (str, int, float, bool)) and k not in ("step",):
            lines.append(f"  {k}: {v}")
    for f in out.get("findings") or []:
        if isinstance(f, dict):
            lines.append(f"  [{f.get('severity', '·')}] {f.get('says') or f.get('message') or f.get('id', '')}")
    for k in ("bodies", "pauses", "files", "model"):
        v = out.get(k)
        if isinstance(v, (list, dict)) and v:
            lines.append(f"  {k}: {str(v)[:600]}")
    c.PrintMessage("\n".join(lines) + "\n")


def _body():
    return T.picked()[0]


class Run:
    """A command that runs a tool at once on the part selected."""

    def __init__(self, tool, text, tip, pixmap, args=None, body=True):
        self.tool, self.text, self.tip, self.pixmap = tool, text, tip, pixmap
        self.args, self.body = dict(args or {}), body

    def GetResources(self):
        return {"MenuText": title(self.text), "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def arguments(self):
        a = dict(self.args)
        b = _body() if self.body else None
        if b:
            a["body"] = b
        return a

    def Activated(self):
        a = self.arguments()
        if a is None:
            return
        ok, out = R.run(self.tool, a)
        report(self.text, ok, out)
        if ok:
            try:
                FreeCADGui.updateGui()
            except Exception:
                pass


class Form:
    """A command that opens one of Make's task panels."""

    def __init__(self, panel, text, tip, pixmap):
        self.panel, self.text, self.tip, self.pixmap = panel, text, tip, pixmap

    def GetResources(self):
        return {"MenuText": title(self.text) + "…", "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None or self.panel == "calibrate"

    def Activated(self):
        T.show(self.panel, done=lambda ok, out: report(self.text, ok, out))


class ThreadLookup(Run):
    def IsActive(self):
        return True

    def arguments(self):
        from PySide import QtGui

        size, ok = QtGui.QInputDialog.getText(FreeCADGui.getMainWindow(), "Thread lookup", "Thread (M6, M10x1.25, 1/4-20, #10-32):")
        return {"size": size.strip()} if ok and size.strip() else None


class PrinterSend(Run):
    def IsActive(self):
        return True

    def arguments(self):
        from PySide import QtGui

        path = QtGui.QFileDialog.getOpenFileName(FreeCADGui.getMainWindow(), "Send to the printer (it is not started)", "", "G-code (*.gcode *.bgcode *.3mf)")
        path = path[0] if isinstance(path, tuple) else path
        return {"file": path} if path else None


class Panel:
    def GetResources(self):
        return {"MenuText": "Make Panel", "ToolTip": "Setups, materials, fits and review: Agent Link's panel when it hosts Make, else Make's own dock", "Pixmap": "Workshop_Make_Workbench"}

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show()


# name (after Workshop_Make_) -> command; the tool it runs is the echo's.
COMMANDS = {
    "NewSetup": Form("setup_new", "New setup", "A setup: how parts are made (print, cut, mill) and its settings", "Workshop_Make_NewSetup"),
    "AddBody": Form("setup_add", "Add body", "Put the selected part in a setup", "list-add"),
    "RemoveSetup": Form("setup_remove", "Remove setup", "Remove a setup (its parts then have no process)", "list-remove"),
    "DfmCheck": Run("dfm_check", "DFM check", "Is the part printable as it stands: walls, overhangs, bridges, holes, bed contact, build volume", "Workshop_Make_DfmCheck"),
    "PartReview": Run("part_review", "Part review", "One verdict on the part: soundness, then its process's checks, wall and mass", "Workshop_Make_PartReview"),
    "MassProperties": Run("mass_properties", "Mass properties", "Mass as made (as printed in a print setup), centre of mass, inertia", "Workshop_Make_MassProperties"),
    "FitSize": Form("fit_size", "Fit size", "The size to model a hole or peg at for a bought part, the printer's calibration added", "Workshop_Make_FitSize"),
    "Calibrate": Form("calibrate", "Calibrate", "How much this printer prints a hole small and a peg big", "Workshop_Make_Calibrate"),
    "Hole": Form("hole", "Hole", "A hole for hardware: clearance, counterbore, countersink, nut trap, insert, magnet", "PartDesign_Hole"),
    "Embed": Form("embed", "Embed", "A pocket for a bought part encased mid-print, with its pause", "PartDesign_Pocket"),
    "Pauses": Run("hw_pauses", "Pauses", "Every pause the part's print needs: layers, heights, what goes in", "Workshop_Make_Pauses"),
    "ThreadLookup": ThreadLookup("thread_lookup", "Thread lookup", "A thread's sizes from the standards: major, pitch, minor, tap drill", "Workshop_Make_ThreadLookup", body=False),
    "Slice": Form("slice", "Slice", "Slice the part in its print setup with the slicer on this computer", "Workshop_Make_Slice"),
    "CutExport": Run("cut_export", "Cut export", "DXF and SVG of a sheet part's flat profile, laid out on the sheet", "Std_Export"),
    "MillExport": Run("mill_export", "Mill export", "STEP of a milled part and its setup sheet", "Std_Export"),
    "PrinterStatus": Run("printer_status", "Printer status", "The printer's state now: temperatures, job, progress", "Workshop_Make_PrinterStatus", body=False),
    "PrinterSend": PrinterSend("printer_send", "Send to printer", "Upload a G-code file to the printer (it is not started)", "document-open", body=False),
    "Panel": Panel(),
}

# The bench's toolbars (design 2.2); printer last.
TOOLBARS = (
    ("Setup", ("NewSetup", "AddBody", "RemoveSetup")),
    ("Check", ("DfmCheck", "PartReview", "MassProperties")),
    ("Fits", ("FitSize", "Calibrate", "Hole")),
    ("Hardware", ("Embed", "Pauses", "ThreadLookup")),
    ("Output", ("Slice", "CutExport", "MillExport")),
    ("Printer", ("PrinterStatus", "PrinterSend")),
)

for _n, _c in COMMANDS.items():
    FreeCADGui.addCommand(PREFIX + _n, _c)

NAMES = [PREFIX + n for n in COMMANDS]
