# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's panel tabs: Setups (how each part is made), Materials (what it is
made of, from Make's own filaments and shop materials), Fits (the size to
model a hole or peg at, the printer's calibration) and Review (the verdict,
in Make's own dock only: under Agent Link its Review tab asks Make's
reviewer). Inspired by the ScanRuler fork's panels (Stefan Hermann, CNC
Kitchen).

Each tab is written against a runner, runner(tool, args) -> (ok, result):
under Agent Link it is the panel's _call (the click shown and logged like
the agent's work), alone Make's own (workshop_make.runner, one undo step a
call). Under Agent Link the tabs sit in its panel; alone in a "Make" dock
beside the model tree. No Agent Link import here."""

from . import materials as fil
from . import records as store
from . import runner as local_runner
from . import theme

try:
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
except ImportError:  # pragma: no cover
    QtCore = QtGui = QtWidgets = None

_Base = QtWidgets.QWidget if QtWidgets else object
DOCK = "WorkshopMakeDock"
CSS = "#SELF QLabel#msg {color: @muted;} #SELF QLabel#bad {color: @bad;} #SELF QPushButton:default {border: 1px solid @accent;}"


# ---- what the tabs show, without Qt (tested headless) ----

def parts(doc):
    """The parts a person would name in the document."""
    if doc is None:
        return []
    return [o.Label for o in local_runner.bodies_in(doc)]


def summary(settings):
    """A setup's settings in a line: 'h2d, 0.4 nozzle, 0.2 layers, 15% infill'."""
    s = dict(settings or {})
    bits = []
    if s.get("printer"):
        bits.append(str(s["printer"]))
    if s.get("nozzle"):
        bits.append(f"{s['nozzle']:g} nozzle" if isinstance(s["nozzle"], (int, float)) else f"{s['nozzle']} nozzle")
    if s.get("layerHeight"):
        bits.append(f"{s['layerHeight']:g} layers" if isinstance(s["layerHeight"], (int, float)) else str(s["layerHeight"]))
    if s.get("infill") is not None:
        v = s["infill"]
        bits.append(f"{v:g}% infill" if isinstance(v, (int, float)) else f"{v} infill")
    rest = [k for k in s if k not in ("printer", "nozzle", "layerHeight", "infill", "fit")]
    bits += [f"{k} {s[k]}" for k in rest[:3]]
    return ", ".join(bits)


def setup_rows(out, names):
    """(rows [(id, 'name (kind)', parts, settings)], parts in no setup)
    from setup list's answer."""
    setups = (out or {}).get("setups") or []
    rows = []
    for s in setups:
        label = store.TYPES.get(s.get("type"), {}).get("label", s.get("type", ""))
        rows.append((s.get("id"), f"{s.get('name')} ({label})", ", ".join(s.get("bodies") or []) or "—",
                     summary({k: v for k, v in s.items() if k not in ("id", "type", "name", "bodies")})))
    none = [b for b in names if not any(b in (s.get("bodies") or []) for s in setups)]
    return rows, none


EMPTY_SETUPS = "No setups yet: Make ▸ New Setup…"


def said(ok, out, good=""):
    """(text, is_bad) for a message line under a tab."""
    if ok:
        return good, False
    return (out.get("error") or {}).get("message", "Refused."), True


def material_rows(doc):
    """[(part, material name, density)] — what each part is recorded as."""
    mats = store.materials(doc) if doc is not None else {}
    out = []
    for b in parts(doc):
        mid = mats.get(b)
        c = fil.card(mid) if mid else None
        if mid and c:
            out.append((b, c["name"], f"{c['density']:.3g}"))
        elif mid:
            out.append((b, str(mid), ""))
        else:
            out.append((b, "— (PLA assumed)", f"{fil.DENSITY.get('pla', 1.24):.3g}"))
    return out


def _shop():
    from . import datafiles

    try:
        return datafiles.load(local_runner._DATA, "shop-materials", package="workshop_make")["entries"]
    except Exception:
        return {}


def material_hits(words="", limit=40):
    """Make's materials matching words: its filaments (a part can be given
    one) and its shop materials (what the cut and mill checks take).
    [(id, name, category, density, E, yield, givable)]."""
    w = [x for x in str(words or "").lower().split() if x]
    out = []
    for k, f in fil.FILAMENTS.items():
        hay = f"{k} {f.get('name', '')} filament".lower()
        if all(x in hay for x in w):
            out.append((k, f.get("name", k), "Printing filament", f.get("density"), f.get("E"), f.get("yield"), True))
    for k, v in _shop().items():
        cat = "Shop: " + ", ".join(x for x in ("metal" if v.get("metal") else "", "cut" if v.get("cut") else "", "mill" if "millWall" in v else "") if x)
        if all(x in f"{k} {cat}".lower() for x in w):
            out.append((k, k, cat, None, None, None, False))
    return out[:limit]


def fit_rows(out):
    """[(fit, 'model at' mm)] from fit size's answer."""
    return [(k, f"{v:.3f}") for k, v in ((out or {}).get("model") or {}).items() if isinstance(v, (int, float))]


def review_lines(out, body):
    """(verdict text, colour role, [(mark, finding, fix)], figures line)."""
    v = str(out.get("verdict", "?"))
    role = {"pass": "ok", "warn": "warn", "fix": "bad", "fail": "bad"}.get(v, "muted")
    head = f"{v.upper()} — {body}, made by {out.get('process', 'unknown')}"
    rows = []
    for f in out.get("findings") or []:
        sev = {"error": "✗", "warning": "!", "info": "·"}.get(str(f.get("severity", "")).lower(), "·")
        rows.append((sev, str(f.get("says") or f.get("message") or f.get("what") or f.get("id", "")), str(f.get("fix") or f.get("do") or "")))
    fig = out.get("figures") or {}
    return head, role, rows, "  ·  ".join(f"{k} {v}" for k, v in fig.items())


# ---- the widgets ----

def _doc():
    import FreeCAD

    return FreeCAD.ActiveDocument


def _sync(combo, items):
    if [combo.itemText(i) for i in range(combo.count())] == items:
        return
    keep = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(items)
    if keep in items:
        combo.setCurrentIndex(items.index(keep))
    combo.blockSignals(False)


class Tab(_Base):
    """A tab over a runner. fill() refreshes it from the document."""

    NAME = "MakeTab"

    def __init__(self, runner=None, doc_fn=None):
        super().__init__()
        self.runner = runner or local_runner.local()
        self.doc_fn = doc_fn or _doc
        self.lay = QtWidgets.QVBoxLayout(self)
        self.build()
        self.msg = QtWidgets.QLabel("")
        self.msg.setObjectName("msg")
        self.msg.setWordWrap(True)
        self.lay.addWidget(self.msg)
        theme.style(self, self.NAME, CSS)

    def say(self, ok, out, good=""):
        text, bad = said(ok, out, good)
        self.msg.setText(text)
        self.msg.setObjectName("bad" if bad else "msg")
        self.msg.setStyleSheet(f"color: {theme.roles(self)['bad' if bad else 'muted']};")

    def button(self, text, tip, fn):
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.clicked.connect(fn)
        return b

    def tree(self, heads):
        t = QtWidgets.QTreeWidget()
        t.setHeaderLabels(heads)
        t.setRootIsDecorated(False)
        return t

    def empty_line(self, text):
        """The line shown under an empty list, saying how to fill it."""
        lab = QtWidgets.QLabel(text)
        lab.setObjectName("msg")
        lab.setWordWrap(True)
        lab.setVisible(False)
        return lab

    def showEvent(self, e):
        """Each time the tab comes up it shows the document as it is now."""
        _fill(self)
        try:
            super().showEvent(e)
        except Exception:
            pass


class SetupsTab(Tab):
    NAME = "MakeSetups"

    def build(self):
        self.setups = self.tree(["Setup", "Parts", "Settings"])
        self.lay.addWidget(self.setups, 1)
        self.none = self.empty_line(EMPTY_SETUPS)
        self.lay.addWidget(self.none)
        row = QtWidgets.QHBoxLayout()
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems([store.TYPES[k]["label"] for k in store.TYPES])
        self.kind.setToolTip("How the part is made.")
        self.body = QtWidgets.QComboBox()
        self.body.setToolTip("The part.")
        row.addWidget(self.kind, 1)
        row.addWidget(self.body, 1)
        for b in (self.button("New", "A new setup of this kind with the part in it.", self.new),
                  self.button("Add to Setup", "Put the part in the setup picked above.", self.add),
                  self.button("Remove", "Remove the setup picked above (its parts then have no process).", self.remove)):
            row.addWidget(b)
        self.lay.addLayout(row)

    def fill(self):
        ok, out = self.runner("setup", {"action": "list"})
        self.setups.clear()
        names = parts(self.doc_fn())
        _sync(self.body, names)
        if not ok:
            self.say(ok, out)
            return
        rows, none = setup_rows(out, names)
        self.none.setVisible(not rows)
        for sid, name, ps, sets in rows:
            it = QtWidgets.QTreeWidgetItem([name, ps, sets])
            it.setData(0, QtCore.Qt.UserRole, sid)
            it.setToolTip(2, sets)
            self.setups.addTopLevelItem(it)
        self.say(True, out, ("In no setup (no process yet): " + ", ".join(none)) if none else "")

    def picked(self):
        it = self.setups.currentItem()
        return it.data(0, QtCore.Qt.UserRole) if it else None

    def new(self):
        b = self.body.currentText()
        ok, out = self.runner("setup", {"action": "add", "type": list(store.TYPES)[max(self.kind.currentIndex(), 0)], "bodies": [b] if b else []})
        self.fill()
        self.say(ok, out)

    def add(self):
        sid, b = self.picked(), self.body.currentText()
        if not sid or not b:
            self.msg.setText("Pick a setup in the list and a part.")
            return
        ok, out = self.runner("setup", {"action": "set", "id": sid, "add": [b]})
        self.fill()
        self.say(ok, out)

    def remove(self):
        sid = self.picked()
        if not sid:
            self.msg.setText("Pick a setup in the list.")
            return
        ok, out = self.runner("setup", {"action": "remove", "id": sid})
        self.fill()
        self.say(ok, out)


class MaterialsTab(Tab):
    NAME = "MakeMaterials"

    def build(self):
        self.parts = self.tree(["Part", "Material", "Density g/cm³"])
        self.lay.addWidget(self.parts, 1)
        row = QtWidgets.QHBoxLayout()
        self.find = QtWidgets.QLineEdit()
        self.find.setPlaceholderText("Find a material (pla, petg, steel …)")
        self.find.returnPressed.connect(self.search)
        row.addWidget(self.find, 1)
        row.addWidget(self.button("Find", "Make's filaments and shop materials.", self.search))
        self.lay.addLayout(row)
        self.hits = self.tree(["Material", "Category", "Density", "E MPa", "Yield MPa"])
        self.lay.addWidget(self.hits, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.button("Give to Part", "The material picked below, for the part picked above.", self.give))
        row.addWidget(self.button("Forget", "The part picked above goes back to no material (PLA assumed, and said).", self.forget))
        self.lay.addLayout(row)

    def fill(self):
        self.parts.clear()
        for row in material_rows(self.doc_fn()):
            self.parts.addTopLevelItem(QtWidgets.QTreeWidgetItem(list(row)))
        if not self.hits.topLevelItemCount():
            self.search()

    def search(self):
        self.hits.clear()
        for mid, name, cat, d, e, y, _give in material_hits(self.find.text().strip()):
            it = QtWidgets.QTreeWidgetItem([str(name), cat] + ["" if v is None else f"{v:g}" for v in (d, e, y)])
            it.setData(0, QtCore.Qt.UserRole, mid)
            self.hits.addTopLevelItem(it)
        self.msg.setText("")

    def give(self):
        part, hit = self.parts.currentItem(), self.hits.currentItem()
        if part is None or hit is None:
            self.msg.setText("Pick a part above and a material below.")
            return
        ok, out = self.runner("part_spec", {"bodies": [part.text(0)], "material": hit.data(0, QtCore.Qt.UserRole)})
        self.fill()
        self.say(ok, out, f"{part.text(0)}: {hit.text(0)}")

    def forget(self):
        part = self.parts.currentItem()
        if part is None:
            self.msg.setText("Pick a part above.")
            return
        ok, out = self.runner("part_spec", {"bodies": [part.text(0)], "material": ""})
        self.fill()
        self.say(ok, out)


class FitsTab(Tab):
    NAME = "MakeFits"

    def build(self):
        form = QtWidgets.QFormLayout()
        self.nominal = QtWidgets.QDoubleSpinBox()
        self.nominal.setRange(0.1, 2000)
        self.nominal.setDecimals(2)
        self.nominal.setValue(5.0)
        self.nominal.setSuffix(" mm")
        self.of = QtWidgets.QComboBox()
        self.of.addItems(["Hole", "Shaft"])
        self.body = QtWidgets.QComboBox()
        self.body.setToolTip("The part, so its print setup's calibration is used (blank: the document's).")
        form.addRow("Bought part / mate", self.nominal)
        form.addRow("Modelling a", self.of)
        form.addRow("In part", self.body)
        self.lay.addLayout(form)
        self.lay.addWidget(self.button("Size It", "The size to model at, each fit.", self.size))
        self.table = self.tree(["Fit", "Model at mm"])
        self.lay.addWidget(self.table, 1)
        cal = QtWidgets.QHBoxLayout()
        self.cal_hole = QtWidgets.QDoubleSpinBox()
        self.cal_shaft = QtWidgets.QDoubleSpinBox()
        for sb, tip in ((self.cal_hole, "How much smaller a printed hole comes out, diametral mm."), (self.cal_shaft, "How much bigger a printed peg comes out, diametral mm.")):
            sb.setRange(-1, 1)
            sb.setDecimals(2)
            sb.setSingleStep(0.05)
            sb.setToolTip(tip)
        self.cal_hole.setValue(0.2)
        cal.addWidget(QtWidgets.QLabel("Printer: holes small by"))
        cal.addWidget(self.cal_hole)
        cal.addWidget(QtWidgets.QLabel("pegs big by"))
        cal.addWidget(self.cal_shaft)
        cal.addWidget(self.button("Keep", "Every hole and fit sized from now on takes it.", self.calibrate))
        self.lay.addLayout(cal)

    def fill(self):
        _sync(self.body, [""] + parts(self.doc_fn()))

    def size(self):
        args = {"action": "size", "nominal": round(self.nominal.value(), 3), "of": self.of.currentText().lower()}
        if self.body.currentText():
            args["body"] = self.body.currentText()
        ok, out = self.runner("fit", args)
        self.table.clear()
        if not ok:
            self.say(ok, out)
            return
        for k, v in fit_rows(out):
            self.table.addTopLevelItem(QtWidgets.QTreeWidgetItem([k, v]))
        self.say(True, out, "Calibration: " + str(out.get("printerFit", "")))

    def calibrate(self):
        ok, out = self.runner("fit", {"action": "calibrate", "hole": round(self.cal_hole.value(), 3), "shaft": round(self.cal_shaft.value(), 3)})
        self.say(ok, out, "Kept: " + str(out.get("calibration", "")))


class ReviewTab(Tab):
    """The verdict on a part (Make's dock only; Agent Link has its own)."""

    NAME = "MakeReview"

    def build(self):
        row = QtWidgets.QHBoxLayout()
        self.body = QtWidgets.QComboBox()
        row.addWidget(self.body, 1)
        row.addWidget(self.button("Review", "One verdict on the part: soundness, printability or its process's checks, wall and mass.", self.review))
        self.lay.addLayout(row)
        self.verdict = QtWidgets.QLabel("")
        self.verdict.setWordWrap(True)
        self.lay.addWidget(self.verdict)
        self.findings = self.tree(["", "Finding", "Fix"])
        self.lay.addWidget(self.findings, 1)

    def fill(self):
        _sync(self.body, parts(self.doc_fn()))

    def review(self):
        body = self.body.currentText()
        if not body:
            return
        ok, out = self.runner("part_review", {"body": body})
        self.findings.clear()
        if not ok:
            self.verdict.setText("")
            self.say(ok, out)
            return
        head, role, rows, figs = review_lines(out, body)
        self.verdict.setText(f"<span style='color:{theme.roles(self)[role]}'>{head}</span>")
        for r in rows or [("", "Nothing found", "")]:
            it = QtWidgets.QTreeWidgetItem(list(r))
            it.setToolTip(1, r[1])
            self.findings.addTopLevelItem(it)
        self.say(True, out, figs)


# Agent Link's tabs (hooks.register_tab): title, widget class, order.
HOSTED = (("Setups", SetupsTab, 30), ("Materials", MaterialsTab, 32), ("Fits", FitsTab, 34))
# Make's own dock, alone.
ALONE = (("Setups", SetupsTab), ("Materials", MaterialsTab), ("Fits", FitsTab), ("Review", ReviewTab))


def factory(cls):
    """register_tab's factory(panel): the tab over the panel's _call."""
    def make(panel):
        return cls(runner=panel._call)
    return make


# ---- Make's own dock, alone ----

def _main():
    import FreeCADGui

    return FreeCADGui.getMainWindow()


def _raise_hosted(title):
    """Under Agent Link: bring its panel's tab up, if the panel is open."""
    mw = _main()
    for tw in mw.findChildren(QtWidgets.QTabWidget):
        for k in range(tw.count()):
            if tw.tabText(k) == title and isinstance(tw.widget(k), Tab):
                d = tw.parentWidget()
                while d is not None and not isinstance(d, QtWidgets.QDockWidget):
                    d = d.parentWidget()
                if d is not None:
                    d.show()
                    d.raise_()
                tw.setCurrentIndex(k)
                _fill(tw.widget(k))
                return True
    return False


def dock():
    """Make's own dock (made once), tabbed with the Combo View."""
    mw = _main()
    d = mw.findChild(QtWidgets.QDockWidget, DOCK)
    if d is not None:
        return d
    d = QtWidgets.QDockWidget("Make", mw)
    d.setObjectName(DOCK)
    tabs = QtWidgets.QTabWidget()
    tabs.setUsesScrollButtons(True)
    for title, cls in ALONE:
        tabs.addTab(cls(), title)
    tabs.currentChanged.connect(lambda k: _fill(tabs.widget(k)))
    d.setWidget(tabs)
    mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, d)
    combo = mw.findChild(QtWidgets.QDockWidget, "Combo View") or mw.findChild(QtWidgets.QDockWidget, "Model")
    if combo is not None:
        mw.tabifyDockWidget(combo, d)
    return d


def _fill(w):
    try:
        w.fill()
    except Exception as e:  # noqa: BLE001 — a tab never stops the window
        import FreeCAD

        FreeCAD.Console.PrintLog(f"Workshop Make panel: {e}\n")


def show(title="Setups"):
    """The panel with title's tab in front: Agent Link's, when it hosts
    Make and its panel is open, else Make's own dock."""
    import workshop_make

    if getattr(workshop_make, "_hosted", False) and title != "Review" and _raise_hosted(title):
        return
    d = dock()
    tabs = d.widget()
    for k in range(tabs.count()):
        if tabs.tabText(k) == title:
            tabs.setCurrentIndex(k)
            _fill(tabs.widget(k))
    d.show()
    d.raise_()
