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
# selected or only one), bodies (comma list), point ([x, y, z], three
# boxes labelled X, Y, Z in mm), depth (a number box and a "Through all"
# check; extra as num's), setup (a setup's id). Titles in Title Case, as
# FreeCAD's task panels have them; command and panel say the same words.
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
        ("depth", "Depth", "depth", "through", (0.1, 10000.0, 2, " mm")),
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
    "slice": ("Slice", "slice", {}, (
        ("body", "Part", "body", "", None),
        ("name", "File name", "text", "", None),
        ("layerHeight", "Layer height", "num", 0.0, (0.0, 1.0, 2, " mm", "From the setup")),
        ("infill", "Infill", "num", 0.0, (0.0, 100.0, 0, " %", "From the setup")),
        ("pauseCommand", "Pause G-code", "text", "", None),
    )),
}

# What a choice's value shows as where capitalising it is not enough.
TEXT = {"corexy": "CoreXY", "h2d": "H2D", "bed-slinger": "Bed slinger", "generic": "Generic",
        "0.2": "0.2 mm", "0.4": "0.4 mm", "0.6": "0.6 mm", "0.8": "0.8 mm", "nut_trap": "Nut trap",
        "-z": "Down (−Z)", "+z": "Up (+Z)", "-x": "Toward −X", "+x": "Toward +X", "-y": "Toward −Y", "+y": "Toward +Y"}

# The one line under each panel's title saying what it does, as the Parts
# panels have.
INTRO = {
    "setup_new": "A setup says how parts are made (printed, cut or milled) and with what settings.",
    "setup_add": "Put a part in a setup, so it is made that way.",
    "setup_remove": "Remove a setup; its parts then have no process.",
    "fit_size": "The size to model a hole or peg at for a bought part, the printer's calibration added.",
    "calibrate": "How much this printer prints holes small and pegs big; every fit sized after takes it.",
    "hole": "A hole for hardware on the face or sketch picked: FreeCAD's own Hole in a Body, the printer allowance, nut traps, inserts and magnets added.",
    "embed": "A pocket for a bought part encased mid-print, and the pause to put it in.",
    "slice": "Slice the part in its print setup with the slicer on this computer.",
}

NO_SETUPS = "No setups yet: Make ▸ New Setup… first."

# Hole for Hardware's "add the matching screw": shown only when Fasteners
# Workbench is installed (workshop_fasteners.detect: folder checks only).
SCREW_LABEL = "Add the matching screw (Fasteners)"
SCREW_TYPES = (("", "Matching the hole"), ("ISO4762", "Socket head cap (ISO 4762)"), ("ISO7380-1", "Button head (ISO 7380-1)"),
               ("ISO10642", "Countersunk (ISO 10642)"), ("ISO4017", "Hex head (ISO 4017)"))


def screw_offered(panel):
    """Whether a panel offers the matching screw: Hole for Hardware, with
    Fasteners Workbench installed."""
    if panel != "hole":
        return False
    try:
        from workshop_fasteners import detect

        return detect.present()
    except Exception:  # noqa: BLE001
        return False


def screw_arg(on, ftype=""):
    """hw_hole's screw argument from the checkbox and the type chosen."""
    if not on:
        return None
    return {"type": ftype} if ftype else True


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
        # The part the picked face or sketch belongs to, though the list
        # left it out (something built from it): it is what was picked.
        parts = [selected] + parts
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


def owner(o, sub=""):
    """The part a picked object belongs to, as a person names it: the
    PartDesign Body a feature, sketch or face is in (by the sub-element path
    too: "Hole.Face5" picked on a Body, "Body.Hole.Face5" on an App::Part),
    else the object itself (a Part feature); None for nothing."""
    if o is None:
        return None
    path = [p for p in str(sub or "").split(".")[:-1] if p]
    if path:
        # An unresolved pick (on a Body or a container): its deepest object.
        try:
            deep = o.getSubObject(".".join(path) + ".", 1)
            if deep is not None and not isinstance(deep, (tuple, list)):
                o = deep
        except Exception:  # noqa: BLE001
            pass
    seen, cur = set(), o
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if _is(cur, "PartDesign::Body"):
            return cur
        try:
            cur = cur.getParentGeoFeatureGroup()
        except Exception:  # noqa: BLE001
            cur = None
    # A Body that holds it, though not as its geo group (an older file).
    for p in getattr(o, "InList", None) or []:
        if _is(p, "PartDesign::Body") and o in (getattr(p, "Group", None) or []):
            return p
    return o


def _is(o, type_id):
    try:
        return bool(o.isDerivedFrom(type_id))
    except Exception:  # noqa: BLE001
        return getattr(o, "TypeId", "") == type_id


def picked():
    """(the part, the point) the person has selected: the label of the part
    the pick belongs to (a face's Body, owner()) and the picked point on it
    [x, y, z], or None for either."""
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


def axis_into(normal):
    """The axis a hole goes along into a face whose outward normal is
    normal ([x, y, z]): "-z" for a top face; None unless the face is square
    to an axis."""
    try:
        n = [float(v) for v in normal][:3]
    except (TypeError, ValueError):
        return None
    if len(n) != 3:
        return None
    k = max(range(3), key=lambda i: abs(n[i]))
    if abs(n[k]) < 0.999:
        return None
    return ("+" if n[k] < 0 else "-") + "xyz"[k]


def picked_normal():
    """The picked face's outward normal at the picked point ([x, y, z]),
    or None."""
    try:
        import FreeCADGui

        s = list(FreeCADGui.Selection.getSelectionEx())[0]
        name = [str(n) for n in s.SubElementNames][0].split(".")[-1]
        face = s.Object.Shape.getElement(name)
        p = list(s.PickedPoints)[0]
        u, v = face.Surface.parameter(p)
        n = face.normalAt(u, v)
        return [n.x, n.y, n.z]
    except Exception:  # noqa: BLE001
        return None


def picked_entry():
    """What the person picked for a hole to start on, as hw_hole takes it:
    {"face": "Face6"} for a flat face of a PartDesign Body's solid, or
    {"sketch": label} for a sketch (its circles are the holes); {} else."""
    try:
        import FreeCADGui

        sel = list(FreeCADGui.Selection.getSelectionEx())
    except Exception:
        return {}
    if not sel:
        return {}
    s = sel[0]
    o = s.Object
    try:
        if o.isDerivedFrom("Sketcher::SketchObject"):
            return {"sketch": o.Label}
    except Exception:
        return {}
    subs = [str(n) for n in (getattr(s, "SubElementNames", None) or []) if str(n).split(".")[-1].startswith("Face")]
    if not subs:
        return {}
    body = None
    try:
        if o.isDerivedFrom("PartDesign::Body"):
            body = o
        else:
            p = o.getParentGeoFeatureGroup()
            body = p if p is not None and p.isDerivedFrom("PartDesign::Body") else None
    except Exception:
        body = None
    if body is None:
        return {}
    # A face's name is the Body's tip's: picked on the tip, or on the Body
    # by a path through its tip ("Pad.Face3"), only.
    tip = getattr(body, "Tip", None)
    path = subs[0].split(".")
    if o is body:
        owner = path[-2] if len(path) > 1 else None
        if tip is None or (owner is not None and owner != getattr(tip, "Name", None)):
            return {}
    elif o is not tip:
        return {}
    return {"face": path[-1]}


def entry_text(entry, body=None):
    """What a hole starts on, in words: "Face5 of Body", "Sketch001"."""
    if entry.get("face"):
        return f"{entry['face']} of {body}" if body else str(entry["face"])
    if entry.get("sketch"):
        return f"Sketch {entry['sketch']} (its circles)"
    return ""


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
        # It fits the Tasks dock (narrow.WIDTH): the intro wraps, combos
        # ask for a few characters, a long row's label goes above its field.
        lay = narrow.form(QtWidgets.QFormLayout(self.form))
        intro = narrow.label(QtWidgets.QLabel(INTRO.get(panel, "")))
        lay.addRow(intro)
        body, at = picked()
        # Hole for Hardware starts on the face or sketch picked, as
        # PartDesign's own Hole does: the face shown, the hole going into it.
        self.entry = picked_entry() if panel == "hole" else {}
        into = axis_into(picked_normal()) if self.entry.get("face") else None
        self.get = {}
        self.blocked = ""
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
            elif kind in ("choice", "body", "setup"):
                w = narrow.combo(QtWidgets.QComboBox())
                start = 0
                if kind == "choice":
                    items = options(extra)
                    want = into if key == "dir" and into else default
                    start = next((i for i, (v, _t) in enumerate(items) if v == want), 0)
                elif kind == "body":
                    items, start = body_items(P.parts(P._doc()), body)
                else:
                    # Filling the list, not the person's click: quiet
                    # under Agent Link (nothing shown, nothing in Activity).
                    quiet = {"quiet": True} if getattr(self.runner, "quiet_ok", False) else {}
                    ok, out = self.runner("setup", {"action": "list"}, **quiet)
                    items = [(s.get("id"), f"{s.get('name')} ({s.get('id')})") for s in (out.get("setups") or [])] if ok else []
                    if not items:
                        items = [("", "No setups yet")]
                        self.blocked = NO_SETUPS
                        w.setEnabled(False)
                w.addItems([t for _v, t in items])
                w.setCurrentIndex(start)
                self.get[key] = lambda w=w, items=items: chosen(w, items)
            elif kind == "point":
                # X, Y and Z one under another: three across ran off the
                # dock (live on the Mac).
                row = QtWidgets.QWidget()
                h = QtWidgets.QVBoxLayout(row)
                h.setContentsMargins(0, 0, 0, 0)
                boxes = []
                for k in range(3):
                    sb = narrow.grow(QtWidgets.QDoubleSpinBox())
                    sb.setRange(-100000, 100000)
                    sb.setDecimals(3)
                    sb.setPrefix("XYZ"[k] + " ")
                    sb.setSuffix(" mm")
                    sb.setToolTip(f"Type the {'XYZ'[k]} value of the point, in the document's coordinates. Unit: mm.")
                    sb.setValue((at or [0, 0, 0])[k])
                    h.addWidget(sb)
                    boxes.append(sb)
                w = row
                self.get[key] = lambda boxes=boxes: [b.value() for b in boxes]
            elif kind == "depth":
                row = QtWidgets.QWidget()
                h = QtWidgets.QHBoxLayout(row)
                h.setContentsMargins(0, 0, 0, 0)
                sb = narrow.grow(QtWidgets.QDoubleSpinBox())
                lo, hi, dec, suf = extra[:4]
                sb.setRange(lo, hi)
                sb.setDecimals(dec)
                sb.setSuffix(suf)
                sb.setValue(lo if default == "through" else float(default))
                through = QtWidgets.QCheckBox("Through all")
                through.setToolTip("Make the hole go through the full part.")
                sb.setToolTip(narrow.field_tip(label, "num", suf))
                through.setChecked(default == "through")
                sb.setEnabled(default != "through")
                through.toggled.connect(lambda on, sb=sb: sb.setEnabled(not on))
                h.addWidget(sb, 1)
                h.addWidget(through)
                w = row
                self.get[key] = lambda sb=sb, through=through: "through" if through.isChecked() else sb.value()
            else:
                w = narrow.grow(QtWidgets.QLineEdit())
                w.setText(", ".join(selected_labels()) if kind == "bodies" else str(default or ""))
                self.get[key] = w.text
            if kind not in ("point", "depth"):  # their boxes have their own tips
                w.setToolTip(narrow.field_tip(label, kind, extra[3] if kind == "num" else ""))
            lay.addRow(label, w)
            if key == "body" and self.entry:
                # What the hole starts on, as picked.
                self.on = narrow.label(QtWidgets.QLabel(entry_text(self.entry, body)))
                lay.addRow("Starts on", self.on)
        if screw_offered(panel):
            # The checkbox on a row of its own, the screw's type under it:
            # side by side they ran off the dock (live on the Mac).
            check = QtWidgets.QCheckBox(SCREW_LABEL)
            check.setToolTip("Put a screw from the Fasteners workbench (Shai Seger) in the hole. Its length comes from the plate and matches the hole.")
            kinds = list(SCREW_TYPES)
            combo = narrow.combo(QtWidgets.QComboBox())
            combo.addItems([t for _v, t in kinds])
            combo.setCurrentIndex(0)
            combo.setToolTip("Select the type of screw.")
            combo.setEnabled(False)
            check.toggled.connect(lambda on, combo=combo: combo.setEnabled(on))
            lay.addRow(check)
            lay.addRow("Screw", combo)
            self.screw = check
            self.get["screw"] = lambda check=check, combo=combo, kinds=kinds: screw_arg(check.isChecked(), chosen(combo, kinds))
        self.msg = narrow.label(QtWidgets.QLabel(self.blocked))
        lay.addRow(self.msg)

    def getStandardButtons(self):
        """OK and Cancel; with nothing to act on (no setups yet) OK is
        left out and the reason shown in its place."""
        from PySide import QtGui

        try:
            from PySide import QtWidgets
        except ImportError:
            QtWidgets = QtGui
        B = QtWidgets.QDialogButtonBox
        return B.Cancel if self.blocked else B.Ok | B.Cancel

    def values(self):
        return {k: g() for k, g in self.get.items()}

    def accept(self):
        import FreeCADGui

        if self.blocked:
            self.msg.setText(self.blocked)
            return False
        vals = self.values()
        tool, args = args_of(self.panel, vals)
        args.update(getattr(self, "entry", None) or {})
        if vals.get("screw"):
            args["screw"] = vals["screw"]
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
