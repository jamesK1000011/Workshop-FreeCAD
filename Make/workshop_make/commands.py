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


def tell(text, title="Workshop Make", warn=False):
    """A message box over FreeCAD's window, titled (nothing when there is
    no GUI). macOS shows no window title on a message box, so there the
    title is the bold first line and the text goes under it."""
    import sys

    try:
        from PySide import QtGui

        try:
            from PySide import QtWidgets
        except ImportError:
            QtWidgets = QtGui
        B = QtWidgets.QMessageBox
        box = B(FreeCADGui.getMainWindow())
        box.setIcon(B.Warning if warn else B.Information)
        box.setWindowTitle(title)
        if sys.platform == "darwin":
            box.setText(title)
            box.setInformativeText(text)
        else:
            box.setText(text)
        (getattr(box, "exec", None) or box.exec_)()
    except Exception:
        pass


# Refusals that only say what to do first (no setup yet, nothing picked):
# guidance, said as a normal message; anything else as a warning.
GUIDANCE = ("invalid_state", "not_found", "invalid_input")


def report(text, ok, out, tool=None, show=False):
    """The answer said to the person: a refusal in a message box in their
    words; a check's verdict and figures in a message box (show) or the
    task's own panel; one line in the Report view either way."""
    from . import results

    c = FreeCAD.Console
    name = title(text)
    if not ok:
        said = results.person_error(out)
        guide = (out.get("error") or {}).get("code") in GUIDANCE
        (c.PrintMessage if guide else c.PrintWarning)(f"Workshop Make · {name}: {said}\n")
        if show:
            tell(said, f"Workshop Make · {name}", warn=not guide)
        return
    fmt = results.SHOWN.get(tool)
    if fmt:
        _verdict, said, line = fmt(out)
        c.PrintMessage(f"Workshop Make · {line}\n")
        if show:
            tell(said, f"Workshop Make · {name}")
        return
    c.PrintMessage(results.line(f"Workshop Make · {name}", out) + "\n")


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
        report(self.text, ok, out, self.tool, show=True)
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
        if self.panel == "slice":
            why = no_print_setup(_body() or _only_part())
            if why:
                report(self.text, False, why, show=True)
                return
        T.show(self.panel, done=lambda ok, out: report(self.text, ok, out))


def _only_part():
    from . import panel

    ps = panel.parts(FreeCAD.ActiveDocument)
    return ps[0] if len(ps) == 1 else None


def no_print_setup(body):
    """The refusal Pauses gives a part in no print setup ({"error"}), or
    None: Slice says the same before its panel opens."""
    if not body:
        return None
    ok, out = R.run("setup", {"action": "list"})
    if not ok:
        return None
    if any(s.get("type") == "print" and body in (s.get("bodies") or []) for s in out.get("setups") or []):
        return None
    return {"error": {"code": "invalid_state", "message": f"{body} is in no print setup"}}


class ThreadLookup(Run):
    def IsActive(self):
        return True

    def arguments(self):
        from PySide import QtGui

        size, ok = QtGui.QInputDialog.getText(FreeCADGui.getMainWindow(), "Thread Lookup", "Thread (M6, M10x1.25, 1/4-20, #10-32):")
        return {"size": size.strip()} if ok and size.strip() else None


class PrinterSend(Run):
    def IsActive(self):
        return True

    def arguments(self):
        from PySide import QtGui

        path = QtGui.QFileDialog.getOpenFileName(FreeCADGui.getMainWindow(), "Send to Printer", "", "G-code (*.gcode *.bgcode *.3mf)")
        path = path[0] if isinstance(path, tuple) else path
        return {"file": path} if path else None


class Panel:
    def GetResources(self):
        return {"MenuText": "Make Panel", "ToolTip": "Setups, materials, fits and review: Agent Link's panel when it hosts Make, else Make's own dock.", "Pixmap": "Workshop_Make_Workbench"}

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        from . import layout

        # Slid out over the 3D view (PanelLayout left-slide): opens and
        # closes it; else shows the panel.
        layout.toggle_or(panel.show)


# name (after Workshop_Make_) -> command; the tool it runs is the echo's.
COMMANDS = {
    "NewSetup": Form("setup_new", "New setup", "A setup: how parts are made (print, cut, mill) and its settings.", "Workshop_Make_NewSetup"),
    "AddBody": Form("setup_add", "Add part to setup", "Put the selected part in a setup.", "list-add"),
    "RemoveSetup": Form("setup_remove", "Remove setup", "Remove a setup (its parts then have no process).", "list-remove"),
    "DfmCheck": Run("dfm_check", "DFM check", "Is the part printable as it stands: walls, overhangs, bridges, holes, bed contact, build volume.", "Workshop_Make_DfmCheck"),
    "PartReview": Run("part_review", "Part review", "One verdict on the part: soundness, then its process's checks, wall and mass.", "Workshop_Make_PartReview"),
    "MassProperties": Run("mass_properties", "Mass properties", "Mass as made (as printed in a print setup), centre of mass, inertia.", "Workshop_Make_MassProperties"),
    "FitSize": Form("fit_size", "Fit size", "The size to model a hole or peg at for a bought part, the printer's calibration added.", "Workshop_Make_FitSize"),
    "Calibrate": Form("calibrate", "Calibrate printer", "How much this printer prints a hole small and a peg big.", "Workshop_Make_Calibrate"),
    "Hole": Form("hole", "Hole for hardware", "A hole for hardware: clearance, counterbore, countersink, nut trap, insert, magnet.", "PartDesign_Hole"),
    "Embed": Form("embed", "Embed hardware", "A pocket for a bought part encased mid-print, with its pause.", "PartDesign_Pocket"),
    "Pauses": Run("hw_pauses", "Pauses", "Every pause the part's print needs: layers, heights, what goes in.", "Workshop_Make_Pauses"),
    "ThreadLookup": ThreadLookup("thread_lookup", "Thread lookup", "A thread's sizes from the standards: major, pitch, minor, tap drill.", "Workshop_Make_ThreadLookup", body=False),
    "Slice": Form("slice", "Slice", "Slice the part in its print setup with the slicer on this computer.", "Workshop_Make_Slice"),
    "CutExport": Run("cut_export", "Cut export", "DXF and SVG of a sheet part's flat profile, laid out on the sheet.", "Std_Export"),
    "MillExport": Run("mill_export", "Mill export", "STEP of a milled part and its setup sheet.", "Std_Export"),
    "PrinterStatus": Run("printer_status", "Printer status", "The printer's state now: temperatures, job, progress.", "Workshop_Make_PrinterStatus", body=False),
    "PrinterSend": PrinterSend("printer_send", "Send to printer", "Upload a G-code file to the printer (it is not started).", "document-open", body=False),
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
