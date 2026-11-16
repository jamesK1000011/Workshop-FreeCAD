# SPDX-License-Identifier: LGPL-2.1-or-later
# A measuring stand-in for PySide (and FreeCAD, FreeCADGui) for the narrow
# dock tests: widgets and layouts keep what they hold, and min_width() works
# out a form's minimum width the way Qt does (QLayout's minimumSize from each
# item's minimumSizeHint, qSmartMinSize's size policies), with text measured
# at a Mac's 13 pt system font (7 px a character, 9 px for "X"). Imported
# first thing in a fresh Python (tests/test_narrow.py runs each case in one).
import re
import sys
import types

CH, CHX, SPACING, MARGIN = 7, 9, 6, 9
FIXED_CALLS = []  # (widget class, call, value): fixed widths are not allowed


def text_w(t):
    return len(re.sub(r"<[^>]+>", "", str(t or ""))) * CH


class _Meta(type):
    def __getattr__(cls, k):  # enums: Qt 5 flat and Qt 6 scoped, as names
        if k.startswith("__"):
            raise AttributeError(k)
        return k


class Signal:
    def __init__(self):
        self.fns = []

    def connect(self, f):
        self.fns.append(f)

    def disconnect(self, *a):
        self.fns = []

    def emit(self, *a):
        for f in list(self.fns):
            f(*a)


class _Any:
    """Whatever an unmodelled call returns: callable, any attribute."""

    def __call__(self, *a, **k):
        return _Any()

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return _Any()

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())

    def __str__(self):
        return ""


SIGNALS = ("clicked", "toggled", "textChanged", "returnPressed", "currentChanged", "currentIndexChanged",
           "valueChanged", "itemClicked", "itemSelectionChanged", "linkActivated", "stateChanged", "editingFinished",
           "itemChanged", "activated", "triggered")


class QWidget(metaclass=_Meta):
    def __init__(self, *a, **k):
        self._text = a[0] if a and isinstance(a[0], str) else ""
        self._layout, self._visible, self._wrap = None, True, False
        self._minw, self._policy, self._ss, self._name, self._enabled = 0, None, "", "", True
        for s in SIGNALS:
            setattr(self, s, Signal())

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return _Any()

    # what the code reads back
    def setText(self, t): self._text = t
    def text(self): return self._text
    def setWordWrap(self, v): self._wrap = bool(v)
    def wordWrap(self): return self._wrap
    def setVisible(self, v): self._visible = bool(v)
    def isVisible(self): return self._visible
    def show(self): self._visible = True
    def hide(self): self._visible = False
    def setEnabled(self, v): self._enabled = bool(v)
    def isEnabled(self): return self._enabled
    def setStyleSheet(self, s): self._ss = s
    def styleSheet(self): return self._ss
    def setObjectName(self, n): self._name = n
    def objectName(self): return self._name
    def palette(self): raise RuntimeError("no palette here")
    def setLayout(self, lay): self._layout = lay; lay._margins = lay._margins if lay._margins is not None else MARGIN
    def layout(self): return self._layout
    def setSizePolicy(self, h, v=None): self._policy = str(h)

    # widths
    def setMinimumWidth(self, w):
        self._minw = max(self._minw, int(w))
        if w:
            FIXED_CALLS.append((type(self).__name__, "setMinimumWidth", w))
    def setFixedWidth(self, w):
        self._minw = max(self._minw, int(w))
        FIXED_CALLS.append((type(self).__name__, "setFixedWidth", w))
    def setMinimumSize(self, w, h=0):
        self._minw = max(self._minw, int(getattr(w, "width", lambda: w)()))
        if self._minw:
            FIXED_CALLS.append((type(self).__name__, "setMinimumSize", self._minw))
    def setFixedSize(self, w, h=0):
        self._minw = max(self._minw, int(w))
        FIXED_CALLS.append((type(self).__name__, "setFixedSize", w))

    def hint(self):
        """minimumSizeHint().width(); in this model sizeHint where the
        default policy cannot shrink (buttons, spin boxes) is the same."""
        return self._layout.min_width() if self._layout is not None else 0

    def min_width(self):
        """What a layout gives it at least (qSmartMinSize): its explicit
        minimum, else its hint; nothing for an Ignored policy or hidden."""
        if not self._visible:
            return 0
        if self._policy and "Ignored" in self._policy:
            return self._minw
        return max(self._minw, self.hint())

    def children_w(self):
        return [self._layout] if self._layout is not None else []


class QLabel(QWidget):
    def hint(self):
        t = re.sub(r"<[^>]+>", "", str(self._text or ""))
        if self._wrap:
            return max([len(x) for x in t.split()] or [0]) * CH
        return len(t) * CH


class QPushButton(QWidget):
    def hint(self):
        return max(70, text_w(self._text) + 24)


class QCheckBox(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.on = False

    def setChecked(self, v):
        self.on = bool(v)
        self.toggled.emit(self.on)

    def isChecked(self): return self.on
    def hint(self): return text_w(self._text) + 22


QRadioButton = QCheckBox


class QLineEdit(QWidget):
    def setPlaceholderText(self, t): pass
    def hint(self): return 40


class QComboBox(QWidget):
    def __init__(self, *a, **k):
        super().__init__()
        self.items, self.idx, self._policy_adj, self._mincl = [], -1, "AdjustToContentsOnFirstShow", 0

    def setSizeAdjustPolicy(self, p): self._policy_adj = str(p)
    def setMinimumContentsLength(self, n): self._mincl = int(n)
    def addItems(self, xs):
        self.items += [str(x) for x in xs]
        if self.idx < 0 and self.items:
            self.idx = 0
    def addItem(self, x, *a): self.addItems([x])
    def clear(self): self.items, self.idx = [], -1
    def count(self): return len(self.items)
    def itemText(self, i): return self.items[i]
    def currentText(self): return self.items[self.idx] if 0 <= self.idx < len(self.items) else ""
    def setCurrentIndex(self, i): self.idx = i
    def currentIndex(self): return self.idx
    def setCurrentText(self, t): self.idx = self.items.index(t)
    def findText(self, t): return self.items.index(t) if t in self.items else -1
    def blockSignals(self, b): return False

    def hint(self):
        w = 0
        if "MinimumContentsLength" not in self._policy_adj:
            w = max([text_w(t) for t in self.items] or [7 * CH])
        w = max(w, self._mincl * CHX)
        return w + 30


class _Spin(QWidget):
    def __init__(self, *a, **k):
        super().__init__()
        self.v, self.lo, self.hi, self.dec, self.pre, self.suf, self.special = 0.0, 0.0, 99.0, 2, "", "", ""

    def setRange(self, lo, hi): self.lo, self.hi = lo, hi
    def setMinimum(self, lo): self.lo = lo
    def setMaximum(self, hi): self.hi = hi
    def setDecimals(self, d): self.dec = d
    def setPrefix(self, p): self.pre = p
    def setSuffix(self, s): self.suf = s
    def setSpecialValueText(self, t): self.special = t
    def setValue(self, v): self.v = float(v)
    def value(self): return self.v
    def _fmt(self, v): return f"{v:.{self.dec}f}"

    def hint(self):
        # QAbstractSpinBox::minimumSizeHint: the longer of its minimum and
        # maximum as text, with prefix, suffix and a space; or the special
        # text. Then its frame and arrows.
        fixed = self.pre + self.suf + " "
        w = max(text_w(self._fmt(self.lo)[:18] + fixed), text_w(self._fmt(self.hi)[:18] + fixed), text_w(self.special))
        return w + 2 + 22


class QDoubleSpinBox(_Spin):
    pass


class QSpinBox(_Spin):
    def __init__(self, *a, **k):
        super().__init__()
        self.dec = 0

    def _fmt(self, v): return str(int(v))
    def value(self): return int(self.v)


class _Scroll(QWidget):
    """Lists, trees, tables, text: they scroll, so ask little."""

    def hint(self): return 70


class QTreeWidget(_Scroll):
    def __init__(self, *a, **k):
        super().__init__()
        self.rows = []
    def addTopLevelItem(self, it): self.rows.append(it)
    def clear(self): self.rows = []
    def topLevelItemCount(self): return len(self.rows)
    def topLevelItem(self, i): return self.rows[i]
    def currentItem(self): return None
    def header(self): return QHeaderView()


class QListWidget(_Scroll):
    def __init__(self, *a, **k):
        super().__init__()
        self.rows = []
    def addItem(self, it): self.rows.append(it)
    def clear(self): self.rows = []
    def count(self): return len(self.rows)
    def item(self, i): return self.rows[i]


class QTableWidget(_Scroll):
    def __init__(self, *a, **k):
        super().__init__()
        self.n = 0
    def insertRow(self, r): self.n += 1
    def removeRow(self, r): self.n -= 1
    def rowCount(self): return self.n
    def currentRow(self): return -1


class QPlainTextEdit(_Scroll):
    pass


QTextEdit = QTextBrowser = QPlainTextEdit


class QHeaderView(QWidget):
    pass


class QTreeWidgetItem:
    def __init__(self, texts=()):
        self.texts, self.d = [str(t) for t in texts], {}
    def text(self, i): return self.texts[i]
    def setData(self, c, role, v): self.d[(c, role)] = v
    def data(self, c, role): return self.d.get((c, role))
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return _Any()


class QListWidgetItem(QTreeWidgetItem):
    def __init__(self, t=""):
        super().__init__([t])
    def text(self, i=0): return self.texts[0]


class QTabWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__()
        self.tabs = []
    def addTab(self, w, t): self.tabs.append((w, t))
    def count(self): return len(self.tabs)
    def tabText(self, k): return self.tabs[k][1]
    def widget(self, k): return self.tabs[k][0]
    def hint(self): return max([w.min_width() for w, _t in self.tabs] or [0]) + 8
    def children_w(self): return [w for w, _t in self.tabs]


class QDockWidget(QWidget):
    def setWidget(self, w): self._w = w
    def hint(self): return self._w.min_width() if getattr(self, "_w", None) else 0


class QScrollArea(QDockWidget):
    def hint(self): return 70


class QDialogButtonBox(QWidget):
    Ok, Cancel, Close = 1, 2, 4


class QSizePolicy(QWidget):
    pass


# ---- layouts ----

class _Layout(metaclass=_Meta):
    def __init__(self, parent=None):
        self.items, self._margins = [], None
        if isinstance(parent, QWidget):
            parent._layout = self
            self._margins = MARGIN

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return _Any()

    def setContentsMargins(self, l, t=0, r=0, b=0): self._margins = (l + r) / 2.0
    def addWidget(self, w, *a, **k): self.items.append(w)
    def addLayout(self, lay, *a, **k):
        if lay._margins is None:
            lay._margins = 0
        self.items.append(lay)
    def addStretch(self, *a): pass
    def addSpacing(self, *a): pass
    def insertWidget(self, i, w, *a): self.items.insert(i, w)
    def margins(self): return 2 * (self._margins or 0)

    def _w(self, x): return x.min_width()

    def visible(self):
        return [x for x in self.items if not isinstance(x, QWidget) or x._visible]

    def children(self):
        return list(self.items)


class QHBoxLayout(_Layout):
    def min_width(self):
        xs = self.visible()
        return sum(self._w(x) for x in xs) + SPACING * max(0, len(xs) - 1) + self.margins()


class QVBoxLayout(_Layout):
    def min_width(self):
        return max([self._w(x) for x in self.visible()] or [0]) + self.margins()


class QGridLayout(_Layout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cells = []

    def addWidget(self, w, r=0, c=0, rs=1, cs=1, *a):
        self.cells.append((w, r, c, cs))
        self.items.append(w)

    def addLayout(self, lay, r=0, c=0, rs=1, cs=1, *a):
        super().addLayout(lay)
        self.cells.append((lay, r, c, cs))

    def min_width(self):
        cols = {}
        for w, _r, c, cs in self.cells:
            if isinstance(w, QWidget) and not w._visible:
                continue
            if cs == 1:
                cols[c] = max(cols.get(c, 0), self._w(w))
        return sum(cols.values()) + SPACING * max(0, len(cols) - 1) + self.margins()


class QFormLayout(_Layout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows, self.wrap = [], "DontWrapRows"  # the Mac style's default

    def setRowWrapPolicy(self, p): self.wrap = str(p)

    def addRow(self, a, b=None):
        if b is None:
            self.rows.append((None, a))
            self.items.append(a)
            return
        lab = QLabel(a) if isinstance(a, str) else a
        self.rows.append((lab, b))
        self.items += [lab, b]

    def children(self):
        return [x for x in self.items if x is not None]

    def min_width(self):
        span, lab_w, fld_w = 0, 0, 0
        for lab, fld in self.rows:
            if isinstance(fld, QWidget) and not fld._visible:
                continue
            if lab is None:
                span = max(span, self._w(fld))
            else:
                lab_w, fld_w = max(lab_w, self._w(lab)), max(fld_w, self._w(fld))
        if "WrapLongRows" in self.wrap or "WrapAllRows" in self.wrap:
            rows = max(lab_w, fld_w)
        else:
            rows = lab_w + SPACING + fld_w if (lab_w or fld_w) else 0
        return max(span, rows) + self.margins()


# ---- reading a widget tree ----

def walk(x):
    """Every widget and layout under x (x included)."""
    seen, out, todo = set(), [], [x]
    while todo:
        y = todo.pop()
        if y is None or id(y) in seen:
            continue
        seen.add(id(y))
        out.append(y)
        if isinstance(y, _Layout):
            todo += y.children()
        elif isinstance(y, QWidget):
            todo += y.children_w()
    return out


def min_width(x):
    return x.min_width()


def worst(x, limit):
    """Leaf widgets asking more than limit on their own: [(class, text, width)]."""
    out = []
    for y in walk(x):
        if isinstance(y, QWidget) and y._layout is None and not isinstance(y, (QTabWidget, QDockWidget)):
            w = y.min_width()
            if w > limit:
                out.append((type(y).__name__, (y._text or "") if not isinstance(y, QComboBox) else max(y.items or [""], key=len), w))
    return out


def unwrapped(x, chars=45):
    """Labels of more than chars characters that do not wrap."""
    return [y._text for y in walk(x) if type(y) is QLabel and y._visible and not y._wrap
            and len(re.sub(r"<[^>]+>", "", str(y._text or ""))) > chars]


def report(x, limit=320):
    return {"width": min_width(x), "worst": worst(x, limit), "unwrapped": unwrapped(x), "fixed": list(FIXED_CALLS)}


# ---- install ----

def install():
    qt = types.ModuleType("PySide.QtWidgets")
    for k, v in list(globals().items()):
        if isinstance(v, type) and k.startswith("Q"):
            setattr(qt, k, v)
    for n in ("QMessageBox", "QInputDialog", "QFileDialog", "QDialog", "QDesktopServices", "QPalette", "QFrame", "QToolButton",
              "QMenu", "QAction", "QApplication", "QStyle", "QSplitter", "QStackedWidget", "QGroupBox", "QAbstractItemView"):
        if not hasattr(qt, n):
            setattr(qt, n, type(n, (QWidget,), {}))
    core = types.ModuleType("PySide.QtCore")
    core.QObject = QWidget
    core.Qt = _Meta("Qt", (), {"UserRole": 32, "Checked": 2, "Unchecked": 0})
    core.QEvent = _Meta("QEvent", (), {"PaletteChange": 39})
    core.QTimer = _Meta("QTimer", (), {"singleShot": staticmethod(lambda *a, **k: None)})
    core.QUrl = QWidget
    core.QSize = lambda w=0, h=0: types.SimpleNamespace(width=lambda: w, height=lambda: h)
    core.Signal = lambda *a, **k: Signal()
    pyside = types.ModuleType("PySide")
    pyside.QtGui, pyside.QtCore, pyside.QtWidgets = qt, core, qt
    sys.modules.update({"PySide": pyside, "PySide.QtGui": qt, "PySide.QtCore": core, "PySide.QtWidgets": qt})
