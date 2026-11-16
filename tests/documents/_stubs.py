# SPDX-License-Identifier: LGPL-2.1-or-later
# Runs code in a fresh Python with stand-ins for FreeCAD, Part and PySide
# (widgets that keep their text, items and values, signals that call back),
# a document double that keeps records in Meta and counts its undo steps,
# and only this add-on on the path. run(code) -> what the code put in OUT.
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PRELUDE = r'''
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
    def __init__(self):
        self.fns = []
    def connect(self, f):
        self.fns.append(f)
    def emit(self, *a):
        for f in self.fns:
            f(*a)

class W:
    def __init__(self, *a, **k):
        self._text = a[0] if a and isinstance(a[0], str) else ""
        self._ss, self._name = "", ""
        for s in ("clicked", "returnPressed", "currentChanged", "itemClicked"):
            setattr(self, s, Signal())
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return lambda *a, **kw: None
    def setText(self, t): self._text = t
    def text(self): return self._text
    def clear(self): self._text = ""
    def setStyleSheet(self, s): self._ss = s
    def styleSheet(self): return self._ss
    def setObjectName(self, n): self._name = n
    def objectName(self): return self._name
    def palette(self): raise RuntimeError("no palette here")

class QComboBox(W):
    def __init__(self, *a, **k):
        super().__init__(); self.items, self.idx = [], -1
    def addItems(self, xs):
        self.items += list(xs)
        if self.idx < 0 and self.items: self.idx = 0
    def clear(self): self.items, self.idx = [], -1
    def count(self): return len(self.items)
    def itemText(self, i): return self.items[i]
    def currentText(self): return self.items[self.idx] if 0 <= self.idx < len(self.items) else ""
    def setCurrentIndex(self, i): self.idx = i
    def currentIndex(self): return self.idx
    def setCurrentText(self, t): self.idx = self.items.index(t)

class QDoubleSpinBox(W):
    def __init__(self, *a, **k):
        super().__init__(); self.v = 0.0
    def setValue(self, v): self.v = float(v)
    def value(self): return self.v

class QTreeWidgetItem:
    def __init__(self, texts=()):
        self.texts, self.d, self.tips = [str(t) for t in texts], {}, {}
    def text(self, i): return self.texts[i]
    def setData(self, c, role, v): self.d[(c, role)] = v
    def data(self, c, role): return self.d.get((c, role))
    def setToolTip(self, c, t): self.tips[c] = t

class QHeaderView(W):
    Stretch, ResizeToContents, Interactive = "stretch", "contents", "interactive"
    def __init__(self, *a, **k):
        super().__init__(); self.modes, self.last = {}, True
    def setSectionResizeMode(self, i, m): self.modes[i] = m
    def setStretchLastSection(self, v): self.last = bool(v)

class QTreeWidget(W):
    def __init__(self, *a, **k):
        super().__init__(); self.rows, self.cur, self.hdr, self.hbar = [], None, QHeaderView(), "as needed"
    def header(self): return self.hdr
    def setHorizontalScrollBarPolicy(self, p): self.hbar = p
    def addTopLevelItem(self, it): self.rows.append(it)
    def clear(self): self.rows, self.cur = [], None
    def currentItem(self): return self.cur
    def setCurrentItem(self, it): self.cur = it
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, i): return self.rows[i]
    def indexOfTopLevelItem(self, it): return self.rows.index(it) if it in self.rows else -1

class QListWidgetItem:
    def __init__(self, t=""):
        self.t, self.state = t, 0
    def text(self): return self.t
    def flags(self): return 0
    def setFlags(self, f): pass
    def setCheckState(self, s): self.state = s
    def checkState(self): return self.state

class QListWidget(W):
    def __init__(self, *a, **k):
        super().__init__(); self.rows = []
    def addItem(self, it): self.rows.append(it)
    def clear(self): self.rows = []
    def count(self): return len(self.rows)
    def item(self, i): return self.rows[i]

class QTabWidget(W):
    def __init__(self, *a, **k):
        super().__init__(); self.tabs = []
    def addTab(self, w, t): self.tabs.append((w, t))
    def count(self): return len(self.tabs)
    def tabText(self, k): return self.tabs[k][1]
    def widget(self, k): return self.tabs[k][0]

qt = types.ModuleType("PySide.QtGui")
for n in ("QWidget", "QLabel", "QPushButton", "QLineEdit", "QVBoxLayout", "QHBoxLayout", "QFormLayout", "QDockWidget", "QSizePolicy", "QPalette", "QInputDialog", "QFileDialog", "QDesktopServices"):
    setattr(qt, n, type(n, (W,), {}))
for c in (QHeaderView, QComboBox, QDoubleSpinBox, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QTabWidget):
    setattr(qt, c.__name__, c)
core = types.ModuleType("PySide.QtCore")
core.QObject = W
core.Qt = types.SimpleNamespace(UserRole=32, Checked=2, Unchecked=0, ItemIsUserCheckable=16, LeftDockWidgetArea=1, ElideRight=1, ScrollBarAlwaysOff="off")
core.QEvent = types.SimpleNamespace(PaletteChange=39)
core.QUrl = W
pyside = types.ModuleType("PySide")
pyside.QtGui, pyside.QtCore, pyside.QtWidgets = qt, core, qt
sys.modules.update({"PySide": pyside, "PySide.QtGui": qt, "PySide.QtCore": core, "PySide.QtWidgets": qt})

said = []
FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=said.append, PrintWarning=said.append, PrintError=said.append, PrintLog=lambda m: None)
FreeCAD.GuiUp = False

class Shape:
    def __init__(self, solid=True): self.Solids = [1] if solid else []
    def isNull(self): return False

class Obj:
    def __init__(self, label, solid=True):
        self.Label = self.Name = label
        self.Shape, self.InList, self.Visibility, self.TypeId = Shape(solid), [], True, "Part::Feature"
    def getParentGeoFeatureGroup(self): return None

class Doc:
    def __init__(self, labels=("Box", "Lid")):
        self.Objects = [Obj(x) for x in labels]
        self.Meta, self.FileName, self.Name = {}, "", "Doc"
        self.tx = []
    def openTransaction(self, n): self.tx.append(("open", n))
    def commitTransaction(self): self.tx.append(("commit",))
    def abortTransaction(self): self.tx.append(("abort",))
    def recompute(self): pass

FreeCAD.ActiveDocument = Doc()
FreeCAD.Vector = lambda *a: a
Gui = Stub("FreeCADGui")
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "TechDrawGui"):
    sys.modules[n] = Stub(n)
sys.path.insert(0, sys.argv[1])
OUT = {}
'''


def run(code, extra_path=None):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "AGENTLINK_HOME": os.environ.get("AGENTLINK_HOME", ""), "HOME": os.environ.get("HOME", "/tmp")}
    src = PRELUDE + (f"sys.path.append({extra_path!r})\n" if extra_path else "") + code + "\nprint(json.dumps(OUT, default=str))\n"
    r = subprocess.run([sys.executable, "-I", "-c", src, ROOT], capture_output=True, text=True, env=env, cwd=ROOT)
    if r.returncode:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])
