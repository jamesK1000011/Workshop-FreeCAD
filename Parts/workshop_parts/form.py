# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.ui.form, retired 14 Nov 2026.
# A task panel built from a parameter table ({name: {kind, min, max, default,
# values, tip}}), the same tables the add-ons check an agent's values
# against: one field per parameter, its range and tip shown, a live summary
# line under them. It sits in FreeCAD's Tasks tab like FreeCAD's own tools
# (no modal dialog): OK commits the document's transaction, Cancel aborts
# it. The person's way into the same function an agent calls.


def _qt():
    """PySide's widget module (QtWidgets on Qt 6 builds, QtGui on Qt 5)."""
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets
    return QtWidgets


def _connect(w, signal, fn):
    try:
        getattr(w, signal).connect(fn)
    except Exception:  # a widget without that signal: no live update from it
        pass


def build(table, intro="", qt=None):
    """(form widget, its layout, fields {name: (kind, widget, spec)}) for a
    parameter table: one row per parameter it knows how to ask for."""
    Q = qt or _qt()
    form = Q.QWidget()
    lay = Q.QFormLayout(form)
    if intro:
        lab = Q.QLabel(intro)
        lab.setWordWrap(True)
        lay.addRow(lab)
    fields = {}
    for k, spec in table.items():
        kind, d = spec.get("kind"), spec.get("default")
        if kind == "bool":
            w = Q.QCheckBox()
            w.setChecked(bool(d))
        elif kind == "enum":
            w = Q.QComboBox()
            w.addItems([str(v) for v in spec["values"]])
            if d in spec["values"]:
                w.setCurrentIndex(list(spec["values"]).index(d))
        elif kind == "int":
            w = Q.QSpinBox()
            w.setRange(int(spec["min"]), int(spec["max"]))
            w.setValue(int(d if d is not None else spec["min"]))
        elif kind == "num":
            w = Q.QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(float(spec["min"]), float(spec["max"]))
            w.setValue(float(d if d is not None else spec["min"]))
            w.setSuffix(" mm" if "mm" in (spec.get("tip") or "") else "")
        else:
            continue
        if spec.get("tip"):
            w.setToolTip(spec["tip"])
        lay.addRow(k, w)
        fields[k] = (kind, w, spec)
    return form, lay, fields


def read(fields):
    """The values in the fields, typed as the table says."""
    out = {}
    for k, (kind, w, spec) in fields.items():
        if kind == "bool":
            out[k] = bool(w.isChecked())
        elif kind == "enum":
            out[k] = list(spec["values"])[w.currentIndex()]
        elif kind == "int":
            out[k] = int(w.value())
        else:
            out[k] = float(w.value())
    return out


class TaskPanel:
    """A parameter table as a task panel. run(values) -> (ok, message) does
    the work on OK; a refusal stays open with its message. summary(values)
    -> str fills the live line under the fields. doc: the transaction
    opened when the panel opens, committed on OK, aborted on Cancel."""

    def __init__(self, title, table, intro="", run=None, summary=None, doc=None, qt=None):
        Q = qt or _qt()
        self.run, self.summary, self.doc = run, summary, doc
        self.form, lay, self.fields = build(table, intro, Q)
        self.form.setWindowTitle(title)
        self.line = Q.QLabel("")
        self.line.setWordWrap(True)
        lay.addRow(self.line)
        self.msg = Q.QLabel("")
        self.msg.setWordWrap(True)
        lay.addRow(self.msg)
        for _k, (kind, w, _s) in self.fields.items():
            _connect(w, {"bool": "toggled", "enum": "currentIndexChanged"}.get(kind, "valueChanged"), self.update)
        if doc is not None:
            doc.openTransaction(title)
        self.update()

    def values(self):
        return read(self.fields)

    def update(self, *_a):
        """The summary line for the values now (and any refusal cleared)."""
        if self.summary is None:
            return
        try:
            text = self.summary(self.values())
        except Exception as e:  # noqa: BLE001 — a summary never breaks the form
            text = str(e)
        self.line.setText(text or "")

    def _close(self):
        try:
            import FreeCADGui

            FreeCADGui.Control.closeDialog()
        except Exception:
            pass

    def accept(self):
        ok, message = self.run(self.values()) if self.run else (True, "")
        if not ok:
            self.msg.setText(message or "Refused.")
            return False
        if self.doc is not None:
            self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        if self.doc is not None:
            self.doc.abortTransaction()
        self._close()
        return True


def show(title, table, intro="", run=None, summary=None, doc=None):
    """Open the panel in the Tasks tab (closing any other task first)."""
    import FreeCADGui

    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    panel = TaskPanel(title, table, intro, run, summary, doc)
    FreeCADGui.Control.showDialog(panel)
    return panel
