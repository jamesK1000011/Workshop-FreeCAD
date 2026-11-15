# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's task panels (FreeCADGui.Control.showDialog), so its forms sit in
the Tasks tab like FreeCAD's own tools: Setup editor (new, add a body,
remove), Fit size, Calibrate, Hole, Embed hardware and Slice options. Each
is a table of fields; OK turns the values into the tool's arguments and runs
it through Make's runner (one undo step), the same handler the agent's tool
calls. No Agent Link import here."""

from . import records as store

# A field: (argument, label, kind, default, extra). Kinds: num (extra:
# (min, max, decimals, suffix[, what the minimum shows as, e.g. "From the
# setup" for 0 meaning the setup's own])), choice (extra: the options, each
# a value or (value, what it shows as); a value shows capitalised, TEXT
# below, while the tool still gets the value), text, body (a part: the
# selected or only one), bodies (comma list), point ([x, y, z]), setup (a
# setup's id). Titles in Title Case, as FreeCAD's task panels have them.
SETUP_SETTINGS = (
    ("printer", "Printer", "choice", "generic", ("generic", "bed-slinger", "corexy", "h2d")),
    ("nozzle", "Nozzle", "choice", "0.4", ("0.2", "0.4", "0.6", "0.8")),
    ("layerHeight", "Layer height", "num", 0.2, (0.04, 1.0, 2, " mm")),
    ("infill", "Infill", "num", 15.0, (0.0, 100.0, 0, " %")),
)
PRINT_ONLY = ("printer", "nozzle", "layerHeight", "infill")

PANELS = {
    "setup_new": ("New Setup", "setup", {"action": "add"}, (
        ("type", "Made by", "choice", "print", tuple(store.TYPES)),
        ("bodies", "Parts", "bodies", "", None),
        ("name", "Name", "text", "", None),
    ) + SETUP_SETTINGS),
    "setup_add": ("Add Part to Setup", "setup", {"action": "set"}, (
        ("id", "Setup", "setup", "", None),
        ("add", "Parts", "bodies", "", None),
    )),
    "setup_remove": ("Remove Setup", "setup", {"action": "remove"}, (
        ("id", "Setup", "setup", "", None),
    )),
    "fit_size": ("Fit Size", "fit", {"action": "size"}, (
        ("nominal", "Bought part or mate", "num", 5.0, (0.1, 2000.0, 2, " mm")),
        ("of", "Modelling a", "choice", "hole", ("hole", "shaft")),
        ("kind", "Fit", "choice", "", (("", "All fits"), "press", "snug", "slide", "free")),
        ("body", "In part", "body", "", None),
    )),
    "calibrate": ("Calibrate Printer", "fit", {"action": "calibrate"}, (
        ("hole", "Holes print small by", "num", 0.2, (-1.0, 1.0, 2, " mm")),
        ("shaft", "Pegs print big by", "num", 0.0, (-1.0, 1.0, 2, " mm")),
    )),
    "hole": ("Hole for Hardware", "hw_hole", {}, (
        ("body", "Part", "body", "", None),
        ("kind", "Kind", "choice", "clearance", ("clearance", "counterbore", "countersink", "nut_trap", "insert", "magnet")),
        ("size", "Size", "text", "M3", None),
        ("at", "Enters at", "point", None, None),
        ("dir", "Into the material", "choice", "-z", ("-z", "+z", "-x", "+x", "-y", "+y")),
        ("depth", "Depth (mm or through)", "text", "through", None),
        ("fit", "Fit", "choice", "normal", ("close", "normal", "loose")),
    )),
    "embed": ("Embed Hardware", "hw_embed", {}, (
        ("body", "Part", "body", "", None),
        ("kind", "Kind", "choice", "magnet", ("nut", "magnet", "bearing", "insert", "weight", "box", "cylinder")),
        ("size", "Size (M3, 6x2, 608 …)", "text", "6x2", None),
        ("at", "Floor centre at", "point", None, None),
        ("turn", "Turn about Z", "num", 0.0, (-360.0, 360.0, 1, " °")),
        ("fit", "Fit", "choice", "slide", ("press", "snug", "slide", "free")),
        ("note", "Note", "text", "", None),
    )),
    "slice": ("Slice Options", "slice", {}, (
        ("body", "Part", "body", "", None),
        ("name", "File name", "text", "", None),
        ("layerHeight", "Layer height", "num", 0.0, (0.0, 1.0, 2, " mm", "From the setup")),
        ("infill", "Infill", "num", 0.0, (0.0, 100.0, 0, " %", "From the setup")),
        ("pauseCommand", "Pause G-code", "text", "", None),
    )),
}

# What a choice's value shows as where capitalising it is not enough.
TEXT = {"corexy": "CoreXY", "h2d": "H2D", "bed-slinger": "Bed slinger", "generic": "Generic",
        "0.2": "0.2 mm", "0.4": "0.4 mm", "0.6": "0.6 mm", "0.8": "0.8 mm", "nut_trap": "Nut trap"}


def options(extra):
    """[(value, text)] for a choice's options."""
    out = []
    for o in extra or ():
        v, t = o if isinstance(o, tuple) else (o, None)
        out.append((v, t or shown(v)))
    return out


def shown(value):
    """A choice's value as it shows: TEXT's, else capitalised."""
    v = str(value)
    if v in TEXT:
        return TEXT[v]
    v = v.replace("_", " ")
    return v[:1].upper() + v[1:]


def chosen(combo, items):
    """The value behind a combo's current entry ("" for none)."""
    i = combo.currentIndex()
    return items[i][0] if isinstance(i, int) and 0 <= i < len(items) else ""


def body_items(parts, selected=None):
    """[(value, text)] for a part combo and the index to start on: the
    part selected, else the only one; a prompt first when there are several
    and none is selected (blank: the tool's own "the one there is")."""
    parts = list(parts)
    if selected in parts:
        return [(p, p) for p in parts], parts.index(selected)
    if len(parts) == 1:
        return [(parts[0], parts[0])], 0
    if not parts:
        return [("", "No parts in the document")], 0
    return [("", "Choose a part")] + [(p, p) for p in parts], 0


# Fields that go under the tool's settings {} rather than at the top.
SETTINGS = {"setup_new": PRINT_ONLY, "slice": ("layerHeight", "infill")}


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def args_of(panel, values):
    """The tool and its arguments for a panel's values ({argument: value}).
    Blank values are left out (the tool's own default); number settings of 0
    mean "the setup's"."""
    _title, tool, fixed, fields = PANELS[panel]
    args = dict(fixed)
    settings = {}
    under = SETTINGS.get(panel, ())
    for key, _label, kind, _d, _x in fields:
        v = values.get(key)
        if v in (None, "", []):
            continue
        if panel == "setup_new" and key in PRINT_ONLY and values.get("type", "print") != "print":
            continue
        if kind == "bodies":
            v = [x.strip() for x in (v if isinstance(v, list) else str(v).split(",")) if x.strip()]
            if not v:
                continue
        elif kind == "num":
            v = round(float(v), 4)
            if key in under and not v:
                continue
        elif kind == "point":
            v = [float(x) for x in v]
        elif key == "depth":
            v = "through" if str(v).strip().lower() == "through" else _num(v)
        if key in under:
            settings[key] = _num(v) if key == "nozzle" else v
        else:
            args[key] = v
    if settings:
        args["settings"] = settings
    return tool, args


def picked():
    """(the part, the point) the person has selected: a part's label and the
    picked point on it [x, y, z], or None for either."""
    try:
        import FreeCADGui

        sel = list(FreeCADGui.Selection.getSelectionEx())
        if not sel:
            return None, None
        s = sel[0]
        o = s.Object
        try:
            body = o.getParentGeoFeatureGroup() or o
        except Exception:
            body = o
        pts = list(getattr(s, "PickedPoints", None) or [])
        at = [round(pts[0].x, 3), round(pts[0].y, 3), round(pts[0].z, 3)] if pts else None
        label = getattr(body, "Label", None)
        return (label if isinstance(label, str) else None), at
    except Exception:
        return None, None


def selected_labels():
    try:
        import FreeCADGui

        return [o.Label for o in list(FreeCADGui.Selection.getSelection()) if isinstance(o.Label, str)]
    except Exception:
        return []


class FormPanel:
    """A task panel of one PANELS form. OK runs it; a refusal stays open
    with what to do instead; done(ok, out) is told the answer."""

    def __init__(self, panel, runner=None, done=None):
        from PySide import QtGui

        try:
            from PySide import QtWidgets
        except ImportError:
            QtWidgets = QtGui
        from . import panel as P
        from . import runner as R

        self.panel, self.done = panel, done
        self.runner = runner or R.local()
        title, _tool, _fixed, fields = PANELS[panel]
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(title)
        lay = QtWidgets.QFormLayout(self.form)
        body, at = picked()
        self.get = {}
        for key, label, kind, default, extra in fields:
            if kind == "num":
                w = QtWidgets.QDoubleSpinBox()
                lo, hi, dec, suf = extra[:4]
                w.setRange(lo, hi)
                w.setDecimals(dec)
                w.setSuffix(suf)
                if len(extra) > 4:
                    w.setSpecialValueText(extra[4])
                w.setValue(default)
                self.get[key] = w.value
            elif kind in ("choice", "body", "setup"):
                w = QtWidgets.QComboBox()
                start = 0
                if kind == "choice":
                    items = options(extra)
                    start = next((i for i, (v, _t) in enumerate(items) if v == default), 0)
                elif kind == "body":
                    items, start = body_items(P.parts(P._doc()), body)
                else:
                    ok, out = self.runner("setup", {"action": "list"})
                    items = [(s.get("id"), f"{s.get('name')} ({s.get('id')})") for s in (out.get("setups") or [])] if ok else []
                    items = items or [("", "No setups yet")]
                w.addItems([t for _v, t in items])
                w.setCurrentIndex(start)
                self.get[key] = lambda w=w, items=items: chosen(w, items)
            elif kind == "point":
                row = QtWidgets.QWidget()
                h = QtWidgets.QHBoxLayout(row)
                h.setContentsMargins(0, 0, 0, 0)
                boxes = []
                for k in range(3):
                    sb = QtWidgets.QDoubleSpinBox()
                    sb.setRange(-100000, 100000)
                    sb.setDecimals(3)
                    sb.setValue((at or [0, 0, 0])[k])
                    h.addWidget(sb)
                    boxes.append(sb)
                w = row
                self.get[key] = lambda boxes=boxes: [b.value() for b in boxes]
            else:
                w = QtWidgets.QLineEdit()
                w.setText(", ".join(selected_labels()) if kind == "bodies" else str(default or ""))
                self.get[key] = w.text
            lay.addRow(label, w)
        self.msg = QtWidgets.QLabel("")
        self.msg.setWordWrap(True)
        lay.addRow(self.msg)

    def values(self):
        return {k: g() for k, g in self.get.items()}

    def accept(self):
        import FreeCADGui

        tool, args = args_of(self.panel, self.values())
        ok, out = self.runner(tool, args)
        if not ok:
            from . import theme

            self.msg.setText((out.get("error") or {}).get("message", "Refused."))
            self.msg.setStyleSheet(f"color: {theme.roles(self.msg)['bad']};")
            return False
        FreeCADGui.Control.closeDialog()
        if self.done:
            self.done(ok, out)
        return True

    def reject(self):
        import FreeCADGui

        FreeCADGui.Control.closeDialog()
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
        from PySide import QtGui

        try:
            from PySide import QtWidgets
        except ImportError:
            QtWidgets = QtGui
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Workshop Make", BUSY)
    except Exception:
        pass
    return True


def show(panel, runner=None, done=None):
    import FreeCADGui

    if busy():
        return None
    p = FormPanel(panel, runner, done)
    FreeCADGui.Control.showDialog(p)
    return p
