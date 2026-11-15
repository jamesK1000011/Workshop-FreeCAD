# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' FreeCAD commands: each runs one of Documents' tools through its
own runner (workshop_documents.runner: the handler the agent's tool calls,
one undo step when it changes the document), on the parts selected or all of
them. Forms open as task panels. Icons are FreeCAD's own, by name, until
Workshop's are drawn. No agent and no Agent Link needed."""
import FreeCAD
import FreeCADGui

from . import runner as R
from . import taskpanels as T

PREFIX = "Workshop_Documents_"


def report(title, ok, out):
    """The answer in the Report view: refusal, the figures, the files."""
    c = FreeCAD.Console
    if not ok:
        c.PrintError(f"Workshop Documents · {title}: {(out.get('error') or {}).get('message', 'refused')}\n")
        return
    lines = [f"Workshop Documents · {title}:"]
    for k, v in out.items():
        if isinstance(v, (str, int, float, bool)):
            lines.append(f"  {k}: {v}")
    for k in ("files", "figures", "steps", "bom"):
        v = out.get(k)
        if isinstance(v, (list, dict)) and v:
            lines.append(f"  {k}: {str(v)[:600]}")
    c.PrintMessage("\n".join(lines) + "\n")


class Run:
    """A command that runs a tool at once on the parts selected (all when
    none is)."""

    def __init__(self, tool, text, tip, pixmap, args=None):
        self.tool, self.text, self.tip, self.pixmap = tool, text, tip, pixmap
        self.args = dict(args or {})

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": self.pixmap}

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
        report(self.text, ok, out)
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
        return {"MenuText": self.text + "…", "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        T.show(self.panel, done=lambda ok, out: report(self.text, ok, out))


class Panel:
    def GetResources(self):
        return {"MenuText": "Manual panel", "ToolTip": "The Manual tab, an assembly manual step by step: Agent Link's panel when it hosts Documents, else Documents' own dock", "Pixmap": "Std_DlgParameter"}

    def IsActive(self):
        return True

    def Activated(self):
        from . import panel

        panel.show()


# name (after Workshop_Documents_) -> command.
COMMANDS = {
    "Drawing": Form("drawing", "Drawing", "A dimensioned sheet of standard views: a TechDraw page, and SVG, PDF and DXF files", "TechDraw_PageDefault"),
    "Exploded": Form("exploded", "Exploded drawing", "An assembly manual: exploded views a step, balloons and a bill of materials", "TechDraw_Balloon"),
    "LibraryPack": Form("library", "Library pack", "The parts as STEP and STL with a README, a licence and credits, nothing personal in the files", "Std_Export"),
    "PatentFigures": Run("patent_figures", "Patent figures", "Line figures of the parts with reference numerals, for a patent application", "TechDraw_ProjectionGroup"),
    "PatentDraft": Form("patent", "Patent draft", "A draft to start a patent attorney's work from: the figures described, numerals listed", "document-new"),
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
