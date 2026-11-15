# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' task panels (FreeCADGui.Control.showDialog), so its forms sit
in the Tasks tab like FreeCAD's own tools: Drawing and Exploded drawing.
Each is a table of fields; OK turns the values into the tool's arguments and
runs it through Documents' runner (one undo step), the same handler the
agent's tool calls. Its own copy of Make's form panel (no shared library).
No Agent Link import here."""

# A field: (argument, label, kind, default, extra). Kinds: num (extra:
# (min, max, decimals, suffix)), choice (extra: the options; "" first means
# "left out"), text, body, bodies and list (comma lists), steps
# ("Title: part, part; Title: part" — one step a part selected by default).
VIEWS = ("front", "back", "top", "bottom", "right", "left", "iso")

PANELS = {
    "drawing": ("Drawing", "drawing_make", {}, (
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("views", "Views (front, top, right, iso …)", "list", "front, top, right, iso", None),
        ("projection", "Projection", "choice", "", ("", "first", "third")),
        ("paper", "Sheet", "choice", "", ("", "A4", "A3", "auto")),
        ("scale", "Scale (0 fits the sheet)", "num", 0.0, (0.0, 100.0, 3, "")),
        ("name", "Name", "text", "", None),
    )),
    "exploded": ("Exploded drawing", "drawing_exploded", {}, (
        ("steps", "Steps", "steps", "", None),
        ("explode", "Spacing (0: chosen for you)", "num", 0.0, (0.0, 5000.0, 1, " mm")),
        ("direction", "Moved", "choice", "", ("", "up", "out")),
        ("name", "Manual name", "text", "", None),
    )),
    "library": ("Library pack", "library_pack", {}, (
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("license", "Licence", "choice", "CC-BY-4.0", ("CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0", "MIT")),
        ("name", "Pack name", "text", "", None),
        ("description", "What it is", "text", "", None),
        ("author", "Author (as credited)", "text", "", None),
    )),
    "patent": ("Patent draft", "patent_draft", {}, (
        ("title", "Title of the invention", "text", "", None),
        ("field", "Field", "text", "", None),
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("name", "Name", "text", "", None),
    )),
}

SETTINGS = {}
OPTIONAL_ZERO = ("scale", "explode")


def parse_steps(text):
    """'Base: Box; Lid on: Lid, Screws' as drawing_exploded's steps."""
    out = []
    for k, part in enumerate(x for x in str(text or "").split(";") if x.strip()):
        title, _, names = part.partition(":") if ":" in part else (f"Step {k + 1}", ":", part)
        bodies = [n.strip() for n in names.split(",") if n.strip()]
        if bodies:
            out.append({"title": title.strip() or f"Step {k + 1}", "add": bodies})
    return out


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
        if kind == "steps":
            v = parse_steps(v)
            if not v:
                continue
        elif kind in ("bodies", "list"):
            v = [x.strip() for x in (v if isinstance(v, list) else str(v).split(",")) if x.strip()]
            if not v:
                continue
        elif kind == "num":
            v = round(float(v), 4)
            if (key in under or key in OPTIONAL_ZERO) and not v:
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
                lo, hi, dec, suf = extra
                w.setRange(lo, hi)
                w.setDecimals(dec)
                w.setSuffix(suf)
                w.setValue(default)
                self.get[key] = w.value
            elif kind in ("choice", "body", "setup"):
                w = QtWidgets.QComboBox()
                if kind == "choice":
                    items = list(extra)
                elif kind == "body":
                    items = [""] + P.parts(P._doc())
                else:
                    items = []
                w.addItems(items)
                want = body if kind == "body" and body in items else default
                if want in items:
                    w.setCurrentIndex(items.index(want))
                self.get[key] = (lambda w=w: w.currentText().split(" — ")[0]) if kind == "setup" else w.currentText
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
                sel = selected_labels()
                w.setText(", ".join(sel) if kind == "bodies" else "; ".join(f"Step {k + 1}: {b}" for k, b in enumerate(sel)) if kind == "steps" else str(default or ""))
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


def show(panel, runner=None, done=None):
    import FreeCADGui

    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    FreeCADGui.Control.showDialog(FormPanel(panel, runner, done))
