# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's panel tabs: Setups (how each part is made), Materials (what it is
made of: Make's printing filaments and the materials each process assumes;
FreeCAD's library through its own Material editor and Material command), Fits (the size to
model a hole or peg at, the printer's calibration) and Review (the verdict,
in Make's own dock only: under Agent Link its Review tab asks Make's
reviewer). Inspired by the ScanRuler fork's panels (Stefan Hermann, CNC
Kitchen).

Each tab is written against a runner, runner(tool, args) -> (ok, result):
under Agent Link it is the panel's _call (the click shown and logged like
the agent's work), alone Make's own (workshop_make.runner, one undo step a
call). Under Agent Link the tabs sit in its panel; alone in a "Make" dock
beside the model tree. No Agent Link import here."""

from workshop import narrow

from . import materials as fil
from . import records as store
from . import results
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
WORKBENCH = "WorkshopMakeWorkbench"
CSS = "#SELF QLabel#msg {color: @muted;} #SELF QLabel#bad {color: @bad;} #SELF QPushButton:default {border: 1px solid @accent;}"


# ---- what the tabs show, without Qt (tested headless) ----

def parts(doc):
    """The parts a person would name in the document."""
    if doc is None:
        return []
    return [o.Label for o in local_runner.bodies_in(doc)]


# A print setup's key settings when it sets none: what Make's checks and
# the slicer take (printability.rules_for, the generic printer).
PRINT_DEFAULTS = {"printer": "generic", "nozzle": 0.4, "layerHeight": 0.2}
PRINTERS = {"generic": "Generic", "bed-slinger": "Bed slinger", "corexy": "CoreXY", "h2d": "H2D"}


def _mm(v):
    return f"{v:g} mm" if isinstance(v, (int, float)) else (f"{v} mm" if str(v).replace(".", "", 1).isdigit() else str(v))


def summary(settings, kind=None):
    """A setup's settings in a line: 'H2D, 0.4 mm nozzle, 0.2 mm layers,
    15% infill'. A print setup always shows its printer, nozzle and layer
    height, the defaults where it sets none ("Defaults: …" when it sets
    nothing); another kind with nothing set says "Defaults"."""
    s = dict(settings or {})
    s.pop("fit", None)
    bits = []
    shown = dict(s)
    if kind == "print":
        shown = {**PRINT_DEFAULTS, **s}
    if shown.get("printer"):
        bits.append(PRINTERS.get(str(shown["printer"]), str(shown["printer"])))
    if shown.get("nozzle"):
        bits.append(f"{_mm(shown['nozzle'])} nozzle")
    if shown.get("layerHeight"):
        bits.append(f"{_mm(shown['layerHeight'])} layers")
    if s.get("infill") is not None:
        v = s["infill"]
        bits.append(f"{v:g}% infill" if isinstance(v, (int, float)) else f"{v} infill")
    rest = [k for k in s if k not in ("printer", "nozzle", "layerHeight", "infill")]
    bits += [f"{k} {s[k]}" for k in rest[:3]]
    line = ", ".join(bits)
    if not any(k in s for k in ("printer", "nozzle", "layerHeight")) and kind == "print" and not rest and s.get("infill") is None:
        return "Defaults: " + line
    return line or "Defaults"


def setup_name(s):
    """A setup's name shown once: its name, its kind only where the name
    doesn't say it ("Print", not "Print (Print)"; "Bracket run (Print)")."""
    label = store.TYPES.get(s.get("type"), {}).get("label", s.get("type", "")) or ""
    name = str(s.get("name") or "").strip() or str(s.get("id") or "")
    return name if not label or label.lower() in name.lower() else f"{name} ({label})"


def setup_rows(out, names):
    """(rows [(id, name, parts, settings)], parts in no setup) from setup
    list's answer."""
    setups = (out or {}).get("setups") or []
    rows = []
    for s in setups:
        rows.append((s.get("id"), setup_name(s), ", ".join(s.get("bodies") or []) or "—",
                     summary({k: v for k, v in s.items() if k not in ("id", "type", "name", "bodies")}, s.get("type"))))
    none = [b for b in names if not any(b in (s.get("bodies") or []) for s in setups)]
    return rows, none


EMPTY_SETUPS = "No setups yet: Make ▸ New Setup…"


def said(ok, out, good=""):
    """(text, is_bad) for a message line under a tab."""
    if ok:
        return good, False
    return (out.get("error") or {}).get("message", "Refused."), True


def material_rows(doc):
    """[(part, material name, density)] — what each part is recorded as:
    Make's filament, else the FreeCAD material it was given (Std_SetMaterial),
    else PLA assumed."""
    from . import fcmaterials

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
            try:
                objs = doc.getObjectsByLabel(b)
                fc = fcmaterials.of(objs[0]) if objs else None
            except Exception:  # noqa: BLE001
                fc = None
            if fc:
                out.append((b, f"{fc['card']} (FreeCAD)", f"{fc['density']:.3g}" if fc.get("density") else ""))
            else:
                out.append((b, "PLA (assumed)", f"{fil.DENSITY.get('pla', 1.24):.3g}"))
    return out


def _shop():
    from . import datafiles

    try:
        return datafiles.load(local_runner._DATA, "shop-materials", package="workshop_make")["entries"]
    except Exception:
        return {}


def shop_name(key, entry=None):
    """A shop material's display name (its data's name, Title Case), else
    its key in Title Case."""
    n = (entry or {}).get("name")
    return n if n else str(key).replace("-", " ").title()


def material_hits(words="", limit=40, library=None):
    """Make's materials matching words: its filaments (a part can be given
    one) and its shop materials (what the cut and mill checks take), each
    by its display name. A spelling of another (aluminium beside aluminum)
    is not listed twice: it finds the one it is the same as. A metal's E and
    yield are FreeCAD's, from its library card (freecadCards), and blank
    where FreeCAD has no card; FreeCAD's whole library is its Material
    editor's (Library…).
    [(id, name, category, density, E, yield, givable, what it is for)]."""
    from . import fcmaterials

    lib = fcmaterials.cards() if library is None else library
    w = [x for x in str(words or "").lower().split() if x]
    out = []
    for k, f in fil.FILAMENTS.items():
        hay = f"{k} {f.get('name', '')} printing filament".lower()
        if all(x in hay for x in w):
            out.append((k, f.get("name", k), "Filament", f.get("density"), f.get("E"), f.get("yield"), True, "Printing filament: a part can be given it."))
    shop = _shop()
    also = {}
    for k, v in shop.items():
        if v.get("sameAs"):
            also.setdefault(v["sameAs"], []).append(k)
    for k, v in shop.items():
        if v.get("sameAs") in shop:
            continue
        uses = [x for x in ("cut" if v.get("cut") else "", "mill" if "millWall" in v else "") if x]
        cat = "Metal" if v.get("metal") else "Non-metal"
        hay = " ".join([k, shop_name(k, v), cat, "shop", *uses, *also.get(k, [])]).lower()
        if all(x in hay for x in w):
            fc = fcmaterials.metal(v.get("freecadCards"), lib) if v.get("metal") and v.get("freecadCards") else None
            fc = fc or {}
            out.append((k, shop_name(k, v), cat, fc.get("density"), fc.get("E"), fc.get("yield"), False,
                        f"Shop material for the {' and '.join(uses) or 'shop'} checks" + (f" (also found as {', '.join(also[k])})" if also.get(k) else "")
                        + (f"; figures from FreeCAD's card {fc['card']}" if fc.get("card") else "") + "."))
    return out[:limit]


NOT_GIVABLE = ("A shop material is what a cut or mill setup assumes (its Material setting). "
               "To give the part a material from FreeCAD's library, use FreeCAD Material….")


def freecad_command(name, label=None, doc=None):
    """Run one of FreeCAD's own commands (its Material editor, its Material
    command on the part labelled label, selected for it). (ok, why not)."""
    try:
        import FreeCADGui

        if label is not None:
            objs = doc.getObjectsByLabel(label) if doc is not None else []
            if not objs:
                return False, f"No part called {label}."
            before = _selected()
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(objs[0])
            lend_selection(before, doc, label)
        FreeCADGui.runCommand(name)
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"FreeCAD's {name} could not be run here ({e})."


def fit_rows(out):
    """[(fit, size to model at, with its unit)] from fit size's answer."""
    return [(k, results.length(v)) for k, v in ((out or {}).get("model") or {}).items() if isinstance(v, (int, float))]


# How a part is made, as the verdict line says it.
MADE = {"printed": "printed", "print": "printed", "cut": "cut", "mill": "milled", "milled": "milled"}


def review_lines(out, body):
    """(verdict text, colour role, [(mark, finding, fix)], figures line)."""
    v = str(out.get("verdict", "?"))
    role = {"pass": "ok", "warn": "warn", "fix": "bad", "fail": "bad"}.get(v, "muted")
    proc = str(out.get("process") or "unknown")
    how = MADE.get(proc, "process not set" if proc == "unknown" else f"made by {proc}")
    head = f"{v.upper()} — {body}, {how}"
    rows = []
    for f in out.get("findings") or []:
        sev = {"error": "✗", "warning": "!", "info": "·"}.get(str(f.get("severity", "")).lower(), "·")
        rows.append((sev, str(f.get("says") or f.get("message") or f.get("what") or f.get("id", "")), str(f.get("fix") or f.get("do") or "")))
    return head, role, rows, results.figures_line(out.get("figures") or {})


EMPTY_REVIEW = "No review yet: pick a part, then press Review."


# ---- a selection the panel made is not left behind ----

# [(document name, object name, the selection before the click)]
_LENT = []


def _selected():
    """{(document name, object name)} selected now."""
    import FreeCADGui

    out = set()
    for o in FreeCADGui.Selection.getSelection():
        d = getattr(o, "Document", None)
        out.add((getattr(d, "Name", ""), getattr(o, "Name", "")))
    return out


def lend_selection(before, doc, label):
    """After a click on label's part: note that its selection is the
    panel's (shown while Make is up) unless the person had it already."""
    try:
        objs = doc.getObjectsByLabel(label) if doc is not None else []
    except Exception:  # noqa: BLE001
        objs = []
    for o in objs:
        key = (getattr(doc, "Name", ""), o.Name)
        if key not in before:
            _LENT.append((key[0], key[1], set(before)))


def put_back_selection():
    """Leaving Make: the parts the panel selected and the person left as
    they were are unselected; a selection the person made stays."""
    if not _LENT:
        return
    try:
        import FreeCADGui

        now = _selected()
        for dn, on, before in list(_LENT):
            if (dn, on) in now and now <= (before | {(dn, on)} | {(a, b) for a, b, _ in _LENT}):
                FreeCADGui.Selection.removeSelection(dn, on)
    except Exception:  # noqa: BLE001 — never stop a workbench switch
        pass
    del _LENT[:]


# ---- the widgets ----

def fit_columns(tree, n, stretch=(0,)):
    """Columns fitted to a narrow dock (see Tab.tree)."""
    try:
        Mode = getattr(QtWidgets.QHeaderView, "ResizeMode", QtWidgets.QHeaderView)
        h = tree.header()
        h.setStretchLastSection(False)
        h.setMinimumSectionSize(24)
        for i in range(n):
            h.setSectionResizeMode(i, Mode.Stretch if i in stretch else Mode.ResizeToContents)
        Policy = getattr(QtCore.Qt, "ScrollBarPolicy", QtCore.Qt)
        tree.setHorizontalScrollBarPolicy(Policy.ScrollBarAlwaysOff)
        Elide = getattr(QtCore.Qt, "TextElideMode", QtCore.Qt)
        tree.setTextElideMode(Elide.ElideRight)
    except Exception:  # noqa: BLE001 — an older Qt: its defaults
        pass


def item(texts, tips=None):
    """A row whose every cell carries its full text as its tooltip (a cell
    may be elided in the narrow dock)."""
    texts = [str(t) for t in texts]
    it = QtWidgets.QTreeWidgetItem(texts)
    for i, t in enumerate(texts):
        tip = (tips or {}).get(i) or t
        if tip:
            it.setToolTip(i, tip)
    return it


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


def _narrow_form(form):
    """A form for a narrow dock: a long row puts its label above its box."""
    narrow.form(form)


def _combo():
    """A combo that fits the narrow dock (narrow.combo): a long part name
    elided rather than widening the tab past it."""
    return narrow.combo(QtWidgets.QComboBox())


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

    def read(self, tool, args):
        """The tab's own refresh: under Agent Link quiet (not the agent's
        work: nothing shown, nothing in Activity); a click goes through
        self.runner and shows."""
        if getattr(self.runner, "quiet_ok", False):
            return self.runner(tool, args, quiet=True)
        return self.runner(tool, args)

    def button(self, text, tip, fn):
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.clicked.connect(fn)
        return b

    def tree(self, heads, stretch=(0,)):
        """A table fitted to the dock: the stretch columns share the width
        and elide (the full text in each cell's tooltip), the rest sized
        to their contents; never a horizontal scrollbar."""
        t = QtWidgets.QTreeWidget()
        t.setHeaderLabels(heads)
        t.setRootIsDecorated(False)
        fit_columns(t, len(heads), stretch)
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
        self.setups = self.tree(["Setup", "Parts", "Settings"], stretch=(1, 2))
        self.lay.addWidget(self.setups, 1)
        self.none = self.empty_line(EMPTY_SETUPS)
        self.lay.addWidget(self.none)
        # The two picks on one line, the keys on the next: one row of all
        # five was cut off in a 330 px dock (live on the Mac).
        row = self.pick_row = QtWidgets.QHBoxLayout()
        self.kind = _combo()
        self.kind.addItems([store.TYPES[k]["label"] for k in store.TYPES])
        self.kind.setToolTip("How the part is made.")
        self.body = _combo()
        self.body.setToolTip("The part.")
        row.addWidget(self.kind, 1)
        row.addWidget(self.body, 1)
        self.lay.addLayout(row)
        row = self.key_row = QtWidgets.QHBoxLayout()
        for b in (self.button("New", "A new setup of this kind with the part in it.", self.new),
                  self.button("Add to Setup", "Put the part in the setup picked above.", self.add),
                  self.button("Remove", "Remove the setup picked above (its parts then have no process).", self.remove)):
            row.addWidget(b)
        self.lay.addLayout(row)

    def fill(self):
        ok, out = self.read("setup", {"action": "list"})
        self.setups.clear()
        names = parts(self.doc_fn())
        _sync(self.body, names)
        if not ok:
            self.say(ok, out)
            return
        rows, none = setup_rows(out, names)
        self.none.setVisible(not rows)
        for sid, name, ps, sets in rows:
            it = item([name, ps, sets])
            it.setData(0, QtCore.Qt.UserRole, sid)
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
        self.parts = self.tree(["Part", "Material", "g/cm³"], stretch=(0, 1))
        self.lay.addWidget(self.parts, 1)
        row = QtWidgets.QHBoxLayout()
        self.find = QtWidgets.QLineEdit()
        self.find.setPlaceholderText("Find a material (PLA, PETG, steel …)")
        self.find.returnPressed.connect(self.search)
        row.addWidget(self.find, 1)
        row.addWidget(self.button("Find", "Make's filaments and shop materials.", self.search))
        self.lay.addLayout(row)
        self.hits = self.tree(["Material", "Kind", "g/cm³", "E, MPa", "Yield, MPa"], stretch=(0,))
        self.lay.addWidget(self.hits, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.button("Give to Part", "The filament picked below, for the part picked above (FreeCAD's material set to match).", self.give))
        row.addWidget(self.button("Forget", "The part picked above goes back to no material (PLA assumed, and said).", self.forget))
        self.lay.addLayout(row)
        # FreeCAD's own library: browsed and edited in its Material editor,
        # given to a part with its own Material command.
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.button("Library…", "FreeCAD's material library, in its Material editor.", self.library))
        row.addWidget(self.button("FreeCAD Material…", "Give the part picked above a material from FreeCAD's library (FreeCAD's Material command).", self.set_freecad))
        self.lay.addLayout(row)

    def fill(self):
        self.parts.clear()
        for row in material_rows(self.doc_fn()):
            self.parts.addTopLevelItem(item(row, {2: f"Density {row[2]} g/cm³" if row[2] else ""}))
        if not self.hits.topLevelItemCount():
            self.search()

    def search(self):
        self.hits.clear()
        for mid, name, cat, d, e, y, give, what in material_hits(self.find.text().strip()):
            it = item([str(name), cat] + ["" if v is None else f"{v:g}" for v in (d, e, y)], {0: f"{name}: {what}", 1: f"{cat}: {what}"})
            it.setData(0, QtCore.Qt.UserRole, mid)
            it.setData(1, QtCore.Qt.UserRole, bool(give))
            self.hits.addTopLevelItem(it)
        self.msg.setText("")

    def give(self):
        part, hit = self.parts.currentItem(), self.hits.currentItem()
        if part is None or hit is None:
            self.msg.setText("Pick a part above and a material below.")
            return
        if hit.data(1, QtCore.Qt.UserRole) is False:
            self.msg.setText(NOT_GIVABLE)
            return
        ok, out = self.runner("part_spec", {"bodies": [part.text(0)], "material": hit.data(0, QtCore.Qt.UserRole)})
        self.fill()
        self.say(ok, out, f"{part.text(0)}: {hit.text(0)}")

    def library(self):
        ok, why = freecad_command("Material_Edit")
        self.msg.setText("" if ok else why)

    def set_freecad(self):
        part = self.parts.currentItem()
        if part is None:
            self.msg.setText("Pick a part above.")
            return
        ok, why = freecad_command("Std_SetMaterial", part.text(0), self.doc_fn())
        self.msg.setText("" if ok else why)
        self.fill()

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
        _narrow_form(form)
        self.nominal = QtWidgets.QDoubleSpinBox()
        self.nominal.setRange(0.1, 2000)
        self.nominal.setDecimals(2)
        self.nominal.setValue(5.0)
        self.nominal.setSuffix(" mm")
        self.of = _combo()
        self.of.addItems(["Hole", "Shaft"])
        self.body = _combo()
        self.nominal.setToolTip("The bought part's size, or the mating part's.")
        self.body.setToolTip("The part, so its print setup's calibration is used (else the document's).")
        form.addRow("Bought part size", self.nominal)
        form.addRow("Modelling a", self.of)
        form.addRow("In part", self.body)
        self.lay.addLayout(form)
        self.lay.addWidget(self.button("Size It", "The size to model at, each fit.", self.size))
        self.table = self.tree(["Fit", "Model at"], stretch=(0,))
        self.lay.addWidget(self.table, 1)
        # The printer's calibration as a form (label above its box when
        # narrow), Keep under it: one row of five was cut off.
        cal = self.cal_form = QtWidgets.QFormLayout()
        _narrow_form(cal)
        self.cal_hole = QtWidgets.QDoubleSpinBox()
        self.cal_shaft = QtWidgets.QDoubleSpinBox()
        for sb, tip in ((self.cal_hole, "How much smaller a printed hole comes out, diametral mm."), (self.cal_shaft, "How much bigger a printed peg comes out, diametral mm.")):
            sb.setRange(-1, 1)
            sb.setDecimals(2)
            sb.setSingleStep(0.05)
            sb.setSuffix(" mm")
            sb.setToolTip(tip)
        self.cal_hole.setValue(0.2)
        cal.addRow("Printer: holes small by", self.cal_hole)
        cal.addRow("Pegs big by", self.cal_shaft)
        self.lay.addLayout(cal)
        self.lay.addWidget(self.button("Keep", "Every hole and fit sized from now on takes it.", self.calibrate))

    def fill(self):
        # The document's parts, the first picked: a blank first item read as
        # an empty box with a body in the document (live on the Mac).
        _sync(self.body, parts(self.doc_fn()))

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
            self.table.addTopLevelItem(item([k, v]))
        from . import api

        self.say(True, out, f"Printer calibration: {api.calibration_said(out.get('printerFit', ''))}.")

    def calibrate(self):
        ok, out = self.runner("fit", {"action": "calibrate", "hole": round(self.cal_hole.value(), 3), "shaft": round(self.cal_shaft.value(), 3)})
        self.say(ok, out, "Kept: " + str(out.get("calibration", "")))


class ReviewTab(Tab):
    """The verdict on a part (Make's dock only; Agent Link has its own)."""

    NAME = "MakeReview"

    def build(self):
        row = QtWidgets.QHBoxLayout()
        self.body = _combo()
        row.addWidget(self.body, 1)
        row.addWidget(self.button("Review", "One verdict on the part: soundness, printability or its process's checks, wall and mass.", self.review))
        self.lay.addLayout(row)
        self.verdict = QtWidgets.QLabel("")
        self.verdict.setWordWrap(True)
        self.lay.addWidget(self.verdict)
        self.findings = self.tree(["", "Finding", "Fix"], stretch=(1, 2))
        self.lay.addWidget(self.findings, 1)
        self.none = self.empty_line(EMPTY_REVIEW)
        self.none.setVisible(True)
        self.lay.addWidget(self.none)

    def fill(self):
        _sync(self.body, parts(self.doc_fn()))

    def review(self):
        body = self.body.currentText()
        if not body:
            self.msg.setText("Pick a part first.")
            return
        try:
            before = _selected()
        except Exception:  # noqa: BLE001 — no Gui
            before = None
        ok, out = self.runner("part_review", {"body": body})
        if before is not None:
            lend_selection(before, self.doc_fn(), body)
        self.findings.clear()
        if not ok:
            self.verdict.setText("")
            self.none.setVisible(True)
            self.say(ok, out)
            return
        head, role, rows, figs = review_lines(out, body)
        self.verdict.setText(f"<span style='color:{theme.roles(self)[role]}'>{head}</span>")
        self.none.setVisible(False)
        for r in rows or [("", "Nothing found", "")]:
            self.findings.addTopLevelItem(item(r))
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
    """Make's own dock (made once), placed by show() (layout.py)."""
    mw = _main()
    d = mw.findChild(QtWidgets.QDockWidget, DOCK)
    if d is not None:
        return d
    d = QtWidgets.QDockWidget("Make", mw)
    d.setObjectName(DOCK)
    tabs = QtWidgets.QTabWidget()
    tabs.setUsesScrollButtons(True)
    from . import layout

    # Under Agent Link its clicks run through it (shown and logged as the
    # agent's are); alone, Make's own runner.
    c = layout.caller() if getattr(__import__("workshop_make"), "_hosted", False) else None
    for title, cls in ALONE:
        tabs.addTab(cls(runner=c._call) if c is not None else cls(), title)
    tabs.currentChanged.connect(lambda k: _fill(tabs.widget(k)))
    d.setWidget(tabs)
    d._tabs = tabs  # kept: in the Combo View or the slide-out it is not the dock's widget
    # Placed by show() through layout.py (the panel layout setting).
    return d


def _fill(w):
    from . import layout

    try:
        with layout.keep_marks():  # a refresh changes nothing: the "*" as it was
            w.fill()
    except Exception as e:  # noqa: BLE001 — a tab never stops the window
        import FreeCAD

        FreeCAD.Console.PrintLog(f"Workshop Make panel: {e}\n")


def _agentlink_tab(title):
    """Under Agent Link: its panel opened with title's tab in front (put in
    its bar for now outside Make's workbench). False with an older one."""
    try:
        import importlib

        importlib.import_module("agentlink.panel").show(tab=title)
        return True
    except Exception:  # noqa: BLE001 — an Agent Link before tabs per workbench
        return False


def show(title="Setups"):
    """The panel with title's tab in front: Agent Link's, when it hosts
    Make, else Make's own dock, placed by the panel layout setting
    (layout.py)."""
    import workshop_make

    from . import layout

    if (getattr(workshop_make, "_hosted", False) and title != "Review" and layout.in_agentlink_panel(title)
            and (_agentlink_tab(title) or _raise_hosted(title))):
        return
    d = dock()
    tabs = d._tabs
    for k in range(tabs.count()):
        if tabs.tabText(k) == title:
            tabs.setCurrentIndex(k)
            _fill(tabs.widget(k))
    p = layout.placer()
    p.show(DOCK, d, WORKBENCH, "Make")
    p.reveal(DOCK)
