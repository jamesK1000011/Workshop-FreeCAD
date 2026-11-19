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


def label_of(name, labels=None):
    """A field's label: the one given, else the parameter's name in words
    (dividersX -> Dividers x), never the raw name."""
    if labels and name in labels:
        return labels[name]
    words = "".join(" " + c.lower() if c.isupper() else c for c in name).replace("_", " ").strip()
    return words[:1].upper() + words[1:]


def shown(value):
    """An option as it shows: capitalised (the table keeps its value)."""
    v = str(value).replace("_", " ")
    return v[:1].upper() + v[1:]


class Pair:
    """Two sizes side by side, X × Y in mm (a board's size)."""

    def __init__(self, Q, spec, tips=("Length (X)", "Width (Y)")):
        self.widget = Q.QWidget()
        h = Q.QHBoxLayout(self.widget)
        h.setContentsMargins(0, 0, 0, 0)
        self.boxes = []
        for k, v in enumerate(list(spec.get("default") or [0, 0])[:2]):
            sb = Q.QDoubleSpinBox()
            sb.setDecimals(2)
            sb.setRange(float(spec.get("min", 1)), float(spec.get("max", 1000)))
            sb.setValue(float(v))
            sb.setSuffix(" mm")
            sb.setToolTip(tips[k])
            if k:
                h.addWidget(Q.QLabel("×"))
            h.addWidget(sb, 1)
            self.boxes.append(sb)

    def connect(self, fn):
        for b in self.boxes:
            _connect(b, "valueChanged", fn)

    def get(self):
        return [float(b.value()) for b in self.boxes]


class Rows:
    """A list of rows (holes, openings): a table of number boxes and
    choices, one row each, with Add and Remove. columns: [(key, header,
    "num" or the choices)]."""

    def __init__(self, Q, columns, add="Add", tip=""):
        self.Q, self.columns, self.rows, self.fns = Q, list(columns), [], []
        self.widget = Q.QWidget()
        v = Q.QVBoxLayout(self.widget)
        v.setContentsMargins(0, 0, 0, 0)
        self.table = Q.QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([c[1] for c in self.columns])
        if tip:
            self.table.setToolTip(tip)
        v.addWidget(self.table)
        h = Q.QHBoxLayout()
        b_add, b_rm = Q.QPushButton(add), Q.QPushButton("Remove")
        b_add.setToolTip("Add a row.")
        b_rm.setToolTip("Remove the selected row. With no row selected, remove the last row.")
        _connect(b_add, "clicked", lambda *_: self.add())
        _connect(b_rm, "clicked", lambda *_: self.remove())
        h.addStretch(1)
        h.addWidget(b_add)
        h.addWidget(b_rm)
        v.addLayout(h)

    def connect(self, fn):
        self.fns.append(fn)

    def _changed(self, *_a):
        for fn in self.fns:
            fn()

    def add(self, values=None):
        values = values or {}
        r = len(self.rows)
        self.table.insertRow(r)
        cells = []
        for c, (key, header, kind) in enumerate(self.columns):
            if kind == "num":
                w = self.Q.QDoubleSpinBox()
                w.setDecimals(2)
                w.setRange(-1000.0, 1000.0)
                w.setSuffix(" mm")
                w.setValue(float(values.get(key, 0.0)))
                _connect(w, "valueChanged", self._changed)
            else:
                w = self.Q.QComboBox()
                w.addItems([shown(x) for x in kind])
                w.setCurrentIndex(list(kind).index(values[key]) if values.get(key) in kind else 0)
                _connect(w, "currentIndexChanged", self._changed)
            w.setToolTip(header)
            self.table.setCellWidget(r, c, w)
            cells.append(w)
        self.rows.append(cells)
        self._changed()

    def remove(self):
        if not self.rows:
            return
        r = self.table.currentRow()
        r = r if isinstance(r, int) and 0 <= r < len(self.rows) else len(self.rows) - 1
        self.table.removeRow(r)
        del self.rows[r]
        self._changed()

    def get(self):
        out = []
        for cells in self.rows:
            row = {}
            for (key, _h, kind), w in zip(self.columns, cells):
                row[key] = float(w.value()) if kind == "num" else list(kind)[w.currentIndex()]
            out.append(row)
        return out


def build(table, intro="", qt=None, labels=None, columns=None):
    """(form widget, its layout, fields {name: (kind, widget, spec)}) for a
    parameter table: one row per parameter it knows how to ask for, labelled
    in words with its unit (labels: {name: label}). A list of [x, y] points
    is a table of X and Y; another list a table of the columns given
    (columns: {name: [(key, header, "num" or choices)]}, "pair" for X × Y)."""
    from workshop import narrow

    Q = qt or _qt()
    columns = columns or {}
    form = Q.QWidget()
    # It fits the Tasks dock (narrow.WIDTH): long labels above their
    # fields, combos asking for a few characters.
    lay = narrow.form(Q.QFormLayout(form))
    if intro:
        lay.addRow(narrow.label(Q.QLabel(intro)))
    fields = {}
    for k, spec in table.items():
        kind, d = spec.get("kind"), spec.get("default")
        if kind == "bool":
            w = Q.QCheckBox()
            w.setChecked(bool(d))
        elif kind == "enum":
            w = narrow.combo(Q.QComboBox())
            w.addItems([shown(v) for v in spec["values"]])
            w.setCurrentIndex(list(spec["values"]).index(d) if d in spec["values"] else 0)
        elif kind == "int":
            w = narrow.grow(Q.QSpinBox())
            w.setRange(int(spec["min"]), int(spec["max"]))
            w.setValue(int(d if d is not None else spec["min"]))
        elif kind == "num":
            w = narrow.grow(Q.QDoubleSpinBox())
            w.setDecimals(2)
            w.setRange(float(spec["min"]), float(spec["max"]))
            w.setValue(float(d if d is not None else spec["min"]))
            w.setSuffix(" mm" if "mm" in (spec.get("tip") or "") else "")
        elif kind == "list" and columns.get(k) == "pair":
            w = Pair(Q, spec)
        elif kind == "points" or (kind == "list" and isinstance(columns.get(k), (list, tuple))):
            cols = columns.get(k) or [("x", "X", "num"), ("y", "Y", "num")]
            w = Rows(Q, cols)
            for v in spec.get("default") or []:
                w.add(dict(zip([c[0] for c in cols], v)) if isinstance(v, (list, tuple)) else v)
        else:
            continue
        if isinstance(w, (Pair, Rows)):
            lay.addRow(label_of(k, labels), w.widget)
            fields[k] = (kind, w, spec)
            continue
        if spec.get("tip"):
            w.setToolTip(spec["tip"])
        lay.addRow(label_of(k, labels), w)
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
        elif isinstance(w, (Pair, Rows)):
            v = w.get()
            out[k] = [[p["x"], p["y"]] for p in v] if kind == "points" else v
        else:
            out[k] = float(w.value())
    return out


class TaskPanel:
    """A parameter table as a task panel. run(values) -> (ok, message) does
    the work on OK; a refusal stays open with its message. summary(values)
    -> str fills the live line under the fields. doc: the transaction
    opened when the panel opens, committed on OK, aborted on Cancel."""

    def __init__(self, title, table, intro="", run=None, summary=None, doc=None, qt=None, labels=None, columns=None, needs=None):
        """needs: {field: (other field, the values it is used with)} — a
        field off while the other one makes it unused (a baseplate's magnet
        floor while its style is Open)."""
        Q = qt or _qt()
        self.run, self.summary, self.doc = run, summary, doc
        self.needs = dict(needs or {})
        self.form, lay, self.fields = build(table, intro, Q, labels, columns)
        self.form.setWindowTitle(title)
        self.line = Q.QLabel("")
        self.line.setWordWrap(True)
        lay.addRow(self.line)
        self.msg = Q.QLabel("")
        self.msg.setWordWrap(True)
        lay.addRow(self.msg)
        for _k, (kind, w, _s) in self.fields.items():
            if isinstance(w, (Pair, Rows)):
                w.connect(self.update)
                continue
            _connect(w, {"bool": "toggled", "enum": "currentIndexChanged"}.get(kind, "valueChanged"), self.update)
        if doc is not None:
            doc.openTransaction(title)
        self.update()

    def values(self):
        return read(self.fields)

    def update(self, *_a):
        """The summary line for the values now (and any refusal cleared);
        a field off while what it needs is not chosen."""
        values = self.values()
        for k, (other, when) in self.needs.items():
            if k in self.fields and other in values:
                try:
                    self.fields[k][1].setEnabled(values[other] in when)
                except Exception:  # noqa: BLE001
                    pass
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


BUSY = "Finish or cancel the open task first."


def busy():
    """True (and the person told) when a task panel is open already: as
    FreeCAD's own commands do, a new one is refused rather than replacing
    it."""
    import FreeCADGui

    if not FreeCADGui.Control.activeDialog():
        return False
    try:
        _qt().QMessageBox.information(FreeCADGui.getMainWindow(), "Workshop Parts", BUSY)
    except Exception:
        pass
    return True


def show(title, table, intro="", run=None, summary=None, doc=None, labels=None, columns=None, needs=None):
    """Open the panel in the Tasks tab; refused while another task is open."""
    import FreeCADGui

    if busy():
        return None
    panel = TaskPanel(title, table, intro, run, summary, doc, labels=labels, columns=columns, needs=needs)
    FreeCADGui.Control.showDialog(panel)
    return panel
