# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts' task panel (design row 11): the form is built from the parameter table
# (no modal dialog, no exec_), reads back typed values, keeps a live summary
# line, and OK/Cancel commit/abort the document's transaction.
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


class Form(unittest.TestCase):
    def test_built_from_each_table(self):
        out = run("""
from workshop_parts import api, form
for g in api.GENERATORS:
    t = api.params(g)
    w, lay, fields = form.build(t, "intro")
    asked = [k for k, s in t.items() if s.get("kind") in ("bool", "enum", "int", "num")]
    OUT[g] = {"fields": list(fields), "asked": asked, "rows": len(lay.rows), "values": form.read(fields), "checked": api.check(g, form.read(fields))}
""")
        for g, o in out.items():
            self.assertEqual(o["fields"], o["asked"], g)
            self.assertEqual(o["rows"], len(o["asked"]) + 1, g)
            self.assertEqual(o["values"], {k: o["checked"][k] for k in o["values"]}, g)

    def test_panel_live_line_and_transaction(self):
        out = run("""
from workshop_parts import api, form, commands
doc = Doc()
calls = []
def refuse_then_ok(values):
    calls.append(values)
    return (False, "Too big.") if len(calls) == 1 else (True, "")
p = form.TaskPanel("Project box", api.params("project_box"), "tip", run=refuse_then_ok,
                   summary=lambda v: commands.summary(doc, "project_box", v), doc=doc)
OUT["title"] = p.form.windowTitle()
OUT["line0"] = p.line.text()
kind, w, spec = p.fields["wall"]
w.setValue(spec["max"])
OUT["line1"] = p.line.text()
OUT["first"] = p.accept()
OUT["msg"] = p.msg.text()
OUT["second"] = p.accept()
OUT["tx"] = list(doc.tx)
OUT["closed"] = len(closed)
d2 = Doc()
q = form.TaskPanel("Gridfinity bin", api.params("gridfinity_bin"), doc=d2)
OUT["cancel"] = q.reject()
OUT["tx2"] = d2.tx
OUT["noexec"] = "exec_" not in open(form.__file__).read() and "QDialog" not in open(form.__file__).read()
""")
        self.assertEqual(out["title"], "Project box")
        self.assertTrue(out["line0"].startswith("Printer fit: "), out["line0"])
        self.assertTrue(out["noexec"])
        self.assertEqual((out["first"], out["msg"]), (False, "Too big."))
        self.assertTrue(out["second"])
        self.assertEqual(out["tx"], ["open", "commit"])
        self.assertEqual(out["closed"], 1)
        self.assertEqual(out["tx2"], ["open", "abort"])

    def test_live_line_says_a_refusal(self):
        out = run("""
from workshop_parts import commands
OUT["bad"] = commands.summary(None, "project_box", {"wall": 999})
OUT["fine"] = commands.summary(None, "project_box", {})
""")
        self.assertTrue(out["bad"].startswith("Not yet: wall"), out["bad"])
        self.assertTrue(out["fine"].startswith("Printer fit: "), out["fine"])

    def test_command_opens_the_panel(self):
        out = run("""
shown = []
Gui.Control.showDialog = shown.append
FreeCAD.ActiveDocument = Doc()
from workshop_parts import commands
commands.Make("gridfinity_bin").Activated()
[p] = shown
OUT["title"] = p.form.windowTitle()
OUT["fields"] = len(p.fields)
OUT["tx"] = FreeCAD.ActiveDocument.tx
""")
        self.assertEqual(out["title"], "Gridfinity Bin")
        self.assertGreater(out["fields"], 3)
        self.assertEqual(out["tx"], ["open"])


    def test_labels_in_words_and_options_capitalised(self):
        out = run("""
from workshop_parts import api, form, commands
OUT["rows"] = {}
for g in api.GENERATORS:
    w, lay, fields = form.build(api.params(g), "", labels=commands.LABELS.get(g))
    OUT["rows"][g] = [r[0] for r in lay.rows if len(r) == 2]
w, lay, fields = form.build(api.params("gridfinity_baseplate"), labels=commands.LABELS["gridfinity_baseplate"])
OUT["style"] = fields["style"][1].items
OUT["value"] = form.read(fields)["style"]
OUT["fallback"] = form.label_of("dividersX")
""")
        bin_rows = out["rows"]["gridfinity_bin"]
        for want in ("Width (cells)", "Height (units of 7 mm)", "Dividers across"):
            self.assertIn(want, bin_rows)
        for g, rows in out["rows"].items():
            for label in rows:
                self.assertTrue(label[:1].isupper(), (g, label))
                self.assertNotIn(label, ("x", "y", "units", "dividersX", "gapLid"), g)
        self.assertEqual(out["style"], ["Open", "Magnets"])
        self.assertEqual(out["value"], "open")
        self.assertEqual(out["fallback"], "Dividers x")

    def test_a_second_task_is_refused(self):
        out = run("""
told, shown = [], []
class Box:
    @staticmethod
    def information(parent, title, text): told.append([title, text])
sys.modules["PySide.QtGui"].QMessageBox = Box
Gui.Control = types.SimpleNamespace(activeDialog=lambda: object(), showDialog=shown.append, closeDialog=lambda: None)
FreeCAD.ActiveDocument = Doc()
from workshop_parts import commands
commands.Make("project_box").Activated()
OUT["told"], OUT["shown"], OUT["tx"] = told, len(shown), FreeCAD.ActiveDocument.tx
""")
        self.assertEqual(out["told"], [["Workshop Parts", "Finish or cancel the open task first."]])
        self.assertEqual((out["shown"], out["tx"]), (0, []))


if __name__ == "__main__":
    unittest.main()
