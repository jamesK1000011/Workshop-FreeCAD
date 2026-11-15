# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' panel: the Manual tab, an assembly manual step by step (tick
the parts that go on next, name the step, Add step; then Make manual).

Written against a runner, runner(tool, args) -> (ok, result): under Agent
Link the panel's _call (shown and logged like the agent's work), alone
Documents' own (workshop_documents.runner). Under Agent Link the tab sits in
its panel and "Make manual" first asks for a manual maker service, if an
add-on provides one; without one, and always alone, it makes the manual with
Documents' own drawing_exploded. No Agent Link import here, and no other
add-on or tool named.

The manual maker service: an object with make(runner, rows, title) ->
(ok, answer), rows [{"title", "bodies", "note"}] in order, title the
manual's name or "". The answer may carry "file" (a path, or {"path"}),
"steps" (a count or a list), "credit" (a line shown under the result) and
"lint" (notes on the words)."""
import os

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
DOCK = "WorkshopDocumentsDock"
CSS = "#SELF QPushButton:default {border: 1px solid @accent;}"


# ---- without Qt (tested headless) ----

def parts(doc):
    if doc is None:
        return []
    return [o.Label for o in local_runner.bodies_in(doc)]


def exploded_steps(rows):
    """The rows [{title, bodies, note}] as drawing_exploded's steps, empty
    ones left out."""
    out = []
    for r in rows:
        if not r.get("bodies"):
            continue
        st = {"title": r.get("title") or "", "add": list(r["bodies"])}
        if r.get("note"):
            st["note"] = r["note"]
        out.append(st)
    return out


def make_manual(runner, rows, title="", service=None):
    """(ok, answer, (message, file, credit)): the manual by the service when
    one is given, else by drawing_exploded."""
    if service is not None:
        ok, out = service.make(runner, [dict(r) for r in rows], title or "")
        f = out.get("file") if ok else None
        path = (f or {}).get("path") if isinstance(f, dict) else f
        n = out.get("steps")
        n = len(n) if isinstance(n, list) else (n or 0)
        msg = f"{n} steps — {path or ''}" + (" (see its word notes)" if out.get("lint") else "") if ok else (out.get("error") or {}).get("message", "Refused.")
        return ok, out, (msg, path, out.get("credit") if ok else None)
    steps = exploded_steps(rows)
    args = {"steps": steps}
    if title:
        args["name"] = title
    ok, out = runner("drawing_exploded", args)
    if not ok:
        return ok, out, ((out.get("error") or {}).get("message", "Refused."), None, None)
    return ok, out, (f"{len(out.get('steps') or [])} steps, {len(out.get('bom') or [])} items — {out.get('manual', '')}", out.get("manual"), None)


# ---- the widget ----

def _doc():
    import FreeCAD

    return FreeCAD.ActiveDocument


class ManualTab(_Base):
    """The Manual tab. service: a callable giving the manual maker, or None
    (Agent Link's hooks.service("manual_maker") when hosted)."""

    NAME = "DocumentsManual"

    def __init__(self, runner=None, service=None, doc_fn=None):
        super().__init__()
        self.runner = runner or local_runner.local()
        self.service = service
        self.doc_fn = doc_fn or _doc
        self.rows, self.file = [], None
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel("Tick the parts that go on next, name the step, Add step:"))
        self.parts = QtWidgets.QListWidget()
        lay.addWidget(self.parts, 1)
        row = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLineEdit()
        self.title.setPlaceholderText("Step title (Base, Lid on …)")
        self.note = QtWidgets.QLineEdit()
        self.note.setPlaceholderText("Note (optional)")
        row.addWidget(self.title, 1)
        row.addWidget(self.note, 1)
        row.addWidget(self._button("Add step", "The ticked parts go on in this step", self.add))
        lay.addLayout(row)
        self.steps = QtWidgets.QTreeWidget()
        self.steps.setHeaderLabels(["#", "Step", "Parts", "Note"])
        self.steps.setRootIsDecorated(False)
        lay.addWidget(self.steps, 1)
        row = QtWidgets.QHBoxLayout()
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Manual name")
        self.open = self._button("Open", "Open the manual made", self.show_file)
        self.open.setEnabled(False)
        row.addWidget(self.name, 1)
        row.addWidget(self._button("Drop step", "Drop the step picked (the last one if none)", self.drop))
        row.addWidget(self._button("Make manual", "Exploded views a step, balloons, a bill of materials and the manual", self.make))
        row.addWidget(self.open)
        lay.addLayout(row)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        self.credit = QtWidgets.QLabel("")
        self.credit.setWordWrap(True)
        lay.addWidget(self.credit)
        theme.style(self, self.NAME, CSS)

    def _button(self, text, tip, fn):
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.clicked.connect(fn)
        return b

    def fill(self):
        used = {b for r in self.rows for b in r["bodies"]}
        want = [b for b in parts(self.doc_fn()) if b not in used]
        if [self.parts.item(i).text() for i in range(self.parts.count())] == want:
            return
        self.parts.clear()
        for b in want:
            it = QtWidgets.QListWidgetItem(b)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Unchecked)
            self.parts.addItem(it)

    def _show_rows(self):
        self.steps.clear()
        for k, r in enumerate(self.rows):
            self.steps.addTopLevelItem(QtWidgets.QTreeWidgetItem([str(k + 1), r["title"], ", ".join(r["bodies"]), r["note"]]))
        self.fill()

    def add(self):
        picked = [self.parts.item(i).text() for i in range(self.parts.count()) if self.parts.item(i).checkState() == QtCore.Qt.Checked]
        if not picked:
            self.msg.setText("Tick the parts this step adds.")
            return
        self.rows.append({"title": self.title.text().strip() or f"Step {len(self.rows) + 1}", "bodies": picked, "note": self.note.text().strip()})
        self.title.clear()
        self.note.clear()
        self.msg.setText("")
        self._show_rows()

    def drop(self):
        it = self.steps.currentItem()
        k = self.steps.indexOfTopLevelItem(it) if it else len(self.rows) - 1
        if 0 <= k < len(self.rows):
            del self.rows[k]
            self._show_rows()

    def make(self):
        if not exploded_steps(self.rows):
            self.msg.setText("Add a step first.")
            return
        svc = self.service() if callable(self.service) else self.service
        ok, _out, (text, path, credit) = make_manual(self.runner, self.rows, self.name.text().strip(), svc)
        self.msg.setText(text)
        self.msg.setStyleSheet(f"color: {theme.roles(self)['muted' if ok else 'bad']};")
        self.credit.setText(credit or "")
        self.file = path if ok else None
        self.open.setEnabled(bool(self.file))

    def show_file(self):
        if self.file and os.path.exists(self.file):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.file))


HOSTED = (("Manual", ManualTab, 40),)


def factory(cls, service=None):
    """register_tab's factory(panel): the tab over the panel's _call."""
    def make(panel):
        return cls(runner=panel._call, service=service)
    return make


# ---- Documents' own dock, alone ----

def _main():
    import FreeCADGui

    return FreeCADGui.getMainWindow()


def _raise_hosted(title):
    for tw in _main().findChildren(QtWidgets.QTabWidget):
        for k in range(tw.count()):
            if tw.tabText(k) == title and isinstance(tw.widget(k), ManualTab):
                d = tw.parentWidget()
                while d is not None and not isinstance(d, QtWidgets.QDockWidget):
                    d = d.parentWidget()
                if d is not None:
                    d.show()
                    d.raise_()
                tw.setCurrentIndex(k)
                return True
    return False


def dock():
    mw = _main()
    d = mw.findChild(QtWidgets.QDockWidget, DOCK)
    if d is not None:
        return d
    d = QtWidgets.QDockWidget("Documents", mw)
    d.setObjectName(DOCK)
    tabs = QtWidgets.QTabWidget()
    tabs.addTab(ManualTab(), "Manual")
    d.setWidget(tabs)
    mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, d)
    combo = mw.findChild(QtWidgets.QDockWidget, "Combo View") or mw.findChild(QtWidgets.QDockWidget, "Model")
    if combo is not None:
        mw.tabifyDockWidget(combo, d)
    return d


def show(title="Manual"):
    """The Manual tab in front: Agent Link's when it hosts Documents and its
    panel is open, else Documents' own dock."""
    import workshop_documents

    if getattr(workshop_documents, "_hosted", False) and _raise_hosted(title):
        return
    d = dock()
    try:
        d.widget().widget(0).fill()
    except Exception:
        pass
    d.show()
    d.raise_()
