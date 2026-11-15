# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics' KiCad board task panel (design row 11): a path field and
# Browse… in the Tasks tab instead of a modal file dialog, a live line saying
# what the board is, OK/Cancel commit/abort the document's transaction.
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Stand-ins for PySide (widgets that keep their values, signals that call
# back), FreeCAD and FreeCADGui (a document double that records its
# transactions; Control.closeDialog counted), in a fresh Python with only
# this add-on on the path.
QTSTUB = r'''
import json, sys, types

class Stub(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        v = Stub(f"{self.__name__}.{k}")
        setattr(self, k, v)
        return v
    def __call__(self, *a, **k):
        return Stub(self.__name__ + "()")

class Signal:
    def __init__(self): self.fns = []
    def connect(self, f): self.fns.append(f)
    def emit(self, *a):
        for f in self.fns: f(*a)

class W:
    def __init__(self, *a, **k):
        self._text = a[0] if a and isinstance(a[0], str) else ""
        self.rows, self.title = [], ""
        for s in ("clicked", "textChanged", "valueChanged", "toggled", "currentIndexChanged"):
            setattr(self, s, Signal())
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return lambda *a, **kw: None
    def setText(self, t): self._text = t; self.textChanged.emit(t)
    def text(self): return self._text
    def setWindowTitle(self, t): self.title = t
    def windowTitle(self): return self.title

class QFormLayout(W):
    def __init__(self, parent=None):
        super().__init__(); parent.layout_ = self
    def addRow(self, *a): self.rows.append(a)

class QCheckBox(W):
    def __init__(self, *a, **k): super().__init__(); self.on = False
    def setChecked(self, v): self.on = bool(v); self.toggled.emit(self.on)
    def isChecked(self): return self.on

class QComboBox(W):
    def __init__(self, *a, **k): super().__init__(); self.items, self.idx = [], -1
    def addItems(self, xs):
        self.items += list(xs)
        if self.idx < 0 and self.items: self.idx = 0
    def currentIndex(self): return self.idx
    def setCurrentIndex(self, i): self.idx = i; self.currentIndexChanged.emit(i)

class QSpinBox(W):
    def __init__(self, *a, **k): super().__init__(); self.v, self.lo, self.hi = 0, -10**9, 10**9
    def setRange(self, lo, hi): self.lo, self.hi = lo, hi
    def setValue(self, v): self.v = min(max(v, self.lo), self.hi); self.valueChanged.emit(self.v)
    def value(self): return self.v

class QDoubleSpinBox(QSpinBox):
    pass

class QFileDialog:
    answer = ""
    @classmethod
    def getOpenFileName(cls, *a): return (cls.answer, "")

qt = types.ModuleType("PySide.QtGui")
for n in ("QWidget", "QLabel", "QPushButton", "QLineEdit", "QHBoxLayout", "QVBoxLayout"):
    setattr(qt, n, type(n, (W,), {}))
for c in (QFormLayout, QCheckBox, QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog):
    setattr(qt, c.__name__, c)
pyside = types.ModuleType("PySide")
pyside.QtGui = pyside.QtWidgets = qt
pyside.QtCore = Stub("PySide.QtCore")
sys.modules.update({"PySide": pyside, "PySide.QtGui": qt, "PySide.QtWidgets": qt, "PySide.QtCore": pyside.QtCore})

said = []
FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=said.append, PrintWarning=said.append, PrintError=said.append, PrintLog=lambda m: None)

class Doc:
    def __init__(self): self.tx, self.Objects, self.Meta = [], [], {}
    def openTransaction(self, n): self.tx.append("open")
    def commitTransaction(self): self.tx.append("commit")
    def abortTransaction(self): self.tx.append("abort")

FreeCAD.ActiveDocument = None
Gui = Stub("FreeCADGui")
closed = []
Gui.Control = types.SimpleNamespace(closeDialog=lambda: closed.append(1), activeDialog=lambda: None, showDialog=lambda p: None)
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher"):
    sys.modules[n] = Stub(n)
sys.path.insert(0, sys.argv[1])
OUT = {}
'''


def run(code):
    src = QTSTUB + code + "\nprint(json.dumps(OUT, default=str))\n"
    r = subprocess.run([sys.executable, "-I", "-c", src, ROOT], capture_output=True, text=True, cwd=ROOT,
                       env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1", "HOME": os.environ.get("HOME", "/tmp")})
    if r.returncode:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])

from test_electronics import BOARD  # noqa: E402


class ImportBoardPanel(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.dir = tempfile.mkdtemp()
        self.pcb = os.path.join(self.dir, "t.kicad_pcb")
        with open(self.pcb, "w", encoding="utf-8") as f:
            f.write(BOARD)

    def test_panel(self):
        out = run(f"""
from workshop_electronics import taskpanels as T
doc = Doc()
p = T.ImportBoardPanel(doc)
OUT["title"] = p.form.windowTitle()
OUT["empty"] = p.line.text()
OUT["refused"] = (p.accept(), p.msg.text())
p.path.setText("/no/such.kicad_pcb")
OUT["missing"] = p.line.text()
QFileDialog.answer = {self.pcb!r}
p.pick()
OUT["picked"] = p.path.text()
OUT["line"] = p.line.text()
OUT["board"] = p.board["size"]
OUT["tx"] = doc.tx
d2 = Doc()
OUT["cancel"] = T.ImportBoardPanel(d2).reject()
OUT["tx2"] = d2.tx
src = open(T.__file__).read() + open(T.__file__.replace("taskpanels", "commands")).read()
OUT["noexec"] = "exec_" not in src and "QDialog(" not in src
""")
        self.assertEqual(out["title"], "KiCad board")
        self.assertIn("Pick a KiCad board", out["empty"])
        self.assertEqual(out["refused"][0], False)
        self.assertEqual(out["missing"], "Not a file yet.")
        self.assertEqual(out["picked"], self.pcb)
        self.assertIn("50 × 30 mm", out["line"])
        self.assertEqual(out["board"], [50.0, 30.0])
        self.assertEqual(out["tx"], ["open"])
        self.assertEqual(out["tx2"], ["open", "abort"])
        self.assertTrue(out["noexec"])

    def test_command_opens_the_panel(self):
        out = run("""
shown = []
Gui.Control.showDialog = shown.append
FreeCAD.ActiveDocument = Doc()
from workshop_electronics import commands
commands.ImportBoard().Activated()
[p] = shown
OUT["title"] = p.form.windowTitle()
""")
        self.assertEqual(out["title"], "KiCad board")


if __name__ == "__main__":
    unittest.main()
