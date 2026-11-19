# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' task panels (FreeCADGui.Control.showDialog), so its forms sit
in the Tasks tab like FreeCAD's own tools: Drawing and Exploded drawing.
Each is a table of fields; OK turns the values into the tool's arguments and
runs it through Documents' runner (one undo step), the same handler the
agent's tool calls. Its own copy of Make's form panel (no shared library).
No Agent Link import here."""

# A field: (argument, label, kind, default, extra). Kinds: num (extra:
# (min, max, decimals, suffix[, what the minimum shows as, e.g. "Fit to
# sheet" for a scale of 0])), choice (extra: the options, each a value or
# (value, what it shows as); a value shows capitalised, TEXT below, while
# the tool still gets the value), text, body, bodies and list (comma lists),
# steps ("Title: part, part; Title: part" — one step a part selected by
# default). Titles in Title Case, as FreeCAD's task panels have them.
VIEWS = ("front", "back", "top", "bottom", "right", "left", "iso")

PANELS = {
    "drawing": ("Drawing", "drawing_make", {}, (
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("views", "Views (front, top, right, iso …)", "list", "front, top, right, iso", None),
        ("projection", "Projection", "choice", "first", ("first", "third")),
        ("paper", "Sheet", "choice", "auto", ("auto", "A4", "A3")),
        ("scale", "Scale", "num", 0.0, (0.0, 100.0, 3, "", "Fit to sheet")),
        ("name", "Name", "text", "", None),
    )),
    "exploded": ("Exploded Drawing", "drawing_exploded", {}, (
        ("steps", "Steps", "steps", "", None),
        ("explode", "Spacing", "num", 0.0, (0.0, 5000.0, 1, " mm", "Chosen for you")),
        ("direction", "Moved", "choice", "up", ("up", "out")),
        ("name", "Manual name", "text", "", None),
    )),
    "library": ("Library Pack", "library_pack", {}, (
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("license", "Licence", "choice", "CC-BY-4.0", ("CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0", "MIT")),
        ("name", "Pack name", "text", "", None),
        ("description", "What it is", "text", "", None),
        ("author", "Author (as credited)", "text", "", None),
    )),
    "patent": ("Patent Draft", "patent_draft", {}, (
        ("title", "Title of the invention", "text", "", None),
        ("field", "Field", "text", "", None),
        ("bodies", "Parts (all when blank)", "bodies", "", None),
        ("name", "Name", "text", "", None),
    )),
}

# The one line under each panel's title saying what it does, as the Parts
# panels have.
INTRO = {
    "drawing": "A TechDraw page of the parts in the views you pick, on TechDraw's own template: edit it in TechDraw after.",
    "exploded": "An assembly manual: each step's parts moved apart, balloons and a bill of materials.",
    "library": "A pack of the parts to share: STEP and STL files, a readme and a licence.",
    "patent": "Patent figures of the parts: black line art with reference numerals.",
}

# What a choice's value shows as where capitalising it is not enough.
TEXT = {"first": "First angle (ISO)", "third": "Third angle (ASME)", "auto": "Smallest that fits",
        "up": "Up, over its place", "out": "Out, from the middle"}


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
    if selected and selected not in parts:
        # The part the pick belongs to, though the list left it out.
        parts = [selected] + parts
    if selected in parts:
        return [(p, p) for p in parts], parts.index(selected)
    if len(parts) == 1:
        return [(parts[0], parts[0])], 0
    if not parts:
        return [("", "No parts in the document")], 0
    return [("", "Choose a part")] + [(p, p) for p in parts], 0


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
        subs = [str(n) for n in (getattr(s, "SubElementNames", None) or [])]
        body = owner(s.Object, subs[0] if subs else "")
        pts = list(getattr(s, "PickedPoints", None) or [])
        at = [round(pts[0].x, 3), round(pts[0].y, 3), round(pts[0].z, 3)] if pts else None
        label = getattr(body, "Label", None)
        return (label if isinstance(label, str) else None), at
    except Exception:
        return None, None


def owner(o, sub=""):
    """The part a picked object belongs to: the PartDesign Body a feature,
    sketch or face is in (by the sub-element path too), else the object."""
    if o is None:
        return None
    path = [p for p in str(sub or "").split(".")[:-1] if p]
    if path:
        try:
            deep = o.getSubObject(".".join(path) + ".", 1)
            if deep is not None and not isinstance(deep, (tuple, list)):
                o = deep
        except Exception:  # noqa: BLE001
            pass
    seen, cur = set(), o
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        try:
            if cur.isDerivedFrom("PartDesign::Body"):
                return cur
        except Exception:  # noqa: BLE001
            if getattr(cur, "TypeId", "") == "PartDesign::Body":
                return cur
        try:
            cur = cur.getParentGeoFeatureGroup()
        except Exception:  # noqa: BLE001
            cur = None
    return o


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
        from workshop import narrow

        from . import panel as P
        from . import runner as R

        self.panel, self.done = panel, done
        self.runner = runner or R.local()
        title, _tool, _fixed, fields = PANELS[panel]
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(title)
        # It fits the Tasks dock (narrow.WIDTH): long labels above their
        # fields, combos asking for a few characters.
        lay = narrow.form(QtWidgets.QFormLayout(self.form))
        intro = narrow.label(QtWidgets.QLabel(INTRO.get(panel, "")))
        lay.addRow(intro)
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
                narrow.grow(w)
                self.get[key] = w.value
            elif kind in ("choice", "body"):
                w = narrow.combo(QtWidgets.QComboBox())
                start = 0
                if kind == "choice":
                    items = options(extra)
                    start = next((i for i, (v, _t) in enumerate(items) if v == default), 0)
                else:
                    items, start = body_items(P.parts(P._doc()), body)
                w.addItems([t for _v, t in items])
                w.setCurrentIndex(start)
                self.get[key] = lambda w=w, items=items: chosen(w, items)
            elif kind == "point":
                row = QtWidgets.QWidget()
                h = QtWidgets.QVBoxLayout(row)
                h.setContentsMargins(0, 0, 0, 0)
                boxes = []
                for k in range(3):
                    sb = narrow.grow(QtWidgets.QDoubleSpinBox())
                    sb.setRange(-100000, 100000)
                    sb.setDecimals(3)
                    sb.setToolTip(f"Type the {'XYZ'[k]} value of the point, in the document's coordinates. Unit: mm.")
                    sb.setValue((at or [0, 0, 0])[k])
                    h.addWidget(sb)
                    boxes.append(sb)
                w = row
                self.get[key] = lambda boxes=boxes: [b.value() for b in boxes]
            else:
                w = narrow.grow(QtWidgets.QLineEdit())
                sel = selected_labels()
                w.setText(", ".join(sel) if kind == "bodies" else "; ".join(f"Step {k + 1}: {b}" for k, b in enumerate(sel)) if kind == "steps" else str(default or ""))
                self.get[key] = w.text
            if kind != "point":  # the X, Y and Z boxes have their own tips
                w.setToolTip(narrow.field_tip(label, kind, extra[3] if kind == "num" else ""))
            lay.addRow(label, w)
        self.msg = narrow.label(QtWidgets.QLabel(""))
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
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Workshop Documents", BUSY)
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
