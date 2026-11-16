# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' FreeCAD commands: each runs one of Documents' tools through its
own runner (workshop_documents.runner: the handler the agent's tool calls,
one undo step when it changes the document), on the parts selected or all of
them. Forms open as task panels. Icons: Documents' own (icons/, by file stem)
where FreeCAD has none to reuse, else FreeCAD's own by name. No agent and no Agent Link needed."""
import os
import re

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

PREFIX = "Workshop_Documents_"


_AGENT = re.compile(r"[{}]|\b[a-z]+_[a-z_]+\b")


def person_error(out):
    """What a refusal says to a person: the tool's message up to where it
    turns to the agent (tool syntax, a tool's name)."""
    msg = str((out.get("error") or {}).get("message") or "Refused.")
    keep = []
    for part in re.split(r" — |; ", msg):
        if _AGENT.search(part):
            break
        keep.append(part)
    text = "; ".join(keep).strip() or "Documents can't do that with the parts as they stand."
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "?", "!")) else text + "."


def _file(p):
    return os.path.basename(str(p))


def _n(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def _drawing(out):
    tb = out.get("titleBlock") or {}
    files = ", ".join(_file(p) for p in (out.get("files") or {}).values())
    s = f"Drawing of {tb.get('title', 'the parts')} on {out.get('paper')} at {out.get('scale')}"
    if out.get("techdrawPage"):
        s += f": the TechDraw page {out['techdrawPage']} (edit it in TechDraw)"
    return s + (f"; files {files}." if files else ".")


def _exploded(out):
    return (f"Assembly manual in {_n(len(out.get('steps') or []), 'step')}, {_n(len(out.get('bom') or []), 'line')} in the bill of materials: "
            f"{_file(out.get('manual'))}.")


def _pack(out):
    kb = (out.get("bytes") or 0) / 1024
    size = f"{kb / 1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} kB"
    s = f"Library pack of {_n(len(out.get('parts') or []), 'part')} under {out.get('license')}: {_file(out.get('pack'))}, {size}."
    if out.get("personal"):
        s += " Some files may still hold a path or user name: check them before sharing."
    return s


def _figures(out):
    figs = out.get("figures") or []
    return f"{_n(len(figs), 'patent figure')} with {_n(len(out.get('numerals') or {}), 'reference numeral')}, as SVG and PDF."


def _draft(out):
    return f"Patent draft written: {_file(out.get('draft'))} ({_n(out.get('figures') or 0, 'figure')}). Nothing is filed or sent."


SENTENCES = {"drawing_make": _drawing, "drawing_exploded": _exploded, "library_pack": _pack, "patent_figures": _figures, "patent_draft": _draft}


def sentence(tool, name, out):
    """The Report view's line: "Workshop: " and a sentence with units; the
    tool's fields stay in its answer, for agents."""
    fn = SENTENCES.get(tool)
    if fn is not None:
        try:
            return "Workshop: " + fn(out)
        except Exception:  # noqa: BLE001 — an answer of another shape
            pass
    return f"Workshop: {name} done."


def tell(text, title="Workshop Documents", warn=False):
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


def report(text, ok, out, show=False, tool=None):
    """The answer: a refusal in the person's words (a message box when
    show), one line in the Report view either way."""
    name = title(text)
    c = FreeCAD.Console
    if not ok:
        said = person_error(out)
        c.PrintWarning(f"Workshop: {name}: {said}\n")
        if show:
            tell(said, f"Workshop Documents · {name}", warn=True)
        return
    c.PrintMessage(sentence(tool, name, out) + "\n")


class Run:
    """A command that runs a tool at once on the parts selected (all when
    none is)."""

    def __init__(self, tool, text, tip, pixmap, args=None):
        self.tool, self.text, self.tip, self.pixmap = tool, text, tip, pixmap
        self.args = dict(args or {})

    def GetResources(self):
        return {"MenuText": title(self.text), "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def arguments(self):
        a = dict(self.args)
        sel = T.selected_labels()
        if sel:
            a["bodies"] = sel
        return a

    def Activated(self):
        ok, out = R.run(self.tool, self.arguments())
        report(self.text, ok, out, show=True, tool=self.tool)
        if ok:
            try:
                FreeCADGui.updateGui()
            except Exception:
                pass


class Form:
    """A command that opens one of Documents' task panels."""

    def __init__(self, panel, text, tip, pixmap):
        self.panel, self.text, self.tip, self.pixmap = panel, text, tip, pixmap

    def GetResources(self):
        return {"MenuText": title(self.text) + "…", "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        T.show(self.panel, done=lambda ok, out: report(self.text, ok, out, tool=T.PANELS[self.panel][1]))


class Panel:
    def GetResources(self):
        return {"MenuText": "Manual Panel", "ToolTip": "The Manual tab, an assembly manual step by step: Agent Link's panel when it hosts Documents, else Documents' own dock.", "Pixmap": "Workshop_Documents_Manual"}

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        from . import layout

        # Slid out over the 3D view (PanelLayout left-slide): opens and
        # closes it; else shows the panel.
        layout.toggle_or(panel.show)


# name (after Workshop_Documents_) -> command.
COMMANDS = {
    "Drawing": Form("drawing", "Drawing", "A TechDraw page of the standard views in one click, editable in TechDraw, and its SVG, PDF and DXF files.", "Workshop_Documents_Drawing"),
    "Exploded": Form("exploded", "Exploded drawing", "An assembly manual: exploded views step by step, balloons and a bill of materials.", "Workshop_Documents_Exploded"),
    "LibraryPack": Form("library", "Library pack", "The parts as STEP and STL with a README, a licence and credits, nothing personal in the files.", "Workshop_Documents_LibraryPack"),
    "PatentFigures": Run("patent_figures", "Patent figures", "Line figures of the parts with reference numerals, for a patent application.", "Workshop_Documents_PatentFigures"),
    "PatentDraft": Form("patent", "Patent draft", "A draft to start a patent attorney's work from: the figures described, numerals listed.", "document-new"),
    "Panel": Panel(),
}

TOOLBARS = (
    ("Drawings", ("Drawing", "Exploded")),
    ("Share", ("LibraryPack",)),
    ("Patent", ("PatentFigures", "PatentDraft")),
)

for _n, _c in COMMANDS.items():
    FreeCADGui.addCommand(PREFIX + _n, _c)

NAMES = [PREFIX + n for n in COMMANDS]
