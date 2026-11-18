# SPDX-License-Identifier: LGPL-2.1-or-later
# The Session panel: what keeps the work safe while nobody watches — the
# document the agent works in, heavy jobs held for the person's go,
# recovered copies, settings changes and macros. One widget, two hosts,
# written against a runner(tool, args) -> (ok, result):
# - under Agent Link, a tab in its panel (register_tab) running Agent Link's
#   panel._call, so what the person does here is shown and logged like the
#   agent's work;
# - alone, SafetyNet's own dock running local.run over the same handlers
#   (one undo step each). The rows that need Agent Link (the document the
#   agent works in, jobs held for a go) hide there.
import json
import os

from .files import _load, path


def _qt():
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
    return QtCore, QtWidgets


NAME = "SafetyNetSession"
TITLE = "SafetyNet"


# ---- what a person reads: one date format, settings in words ---------------------------

_STAMPS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y%m%d-%H%M%S")


def when(text, now=None):
    """A time as SafetyNet's tools give it (2026-11-15 12:41 or
    20261115-124100) in one readable local form: 15 Nov 12:41, with the
    year when it is not this one. Text it cannot read comes back as is."""
    import datetime

    t = str(text or "").strip()
    for f in _STAMPS:
        try:
            d = datetime.datetime.strptime(t, f)
        except ValueError:
            continue
        year = (now or datetime.datetime.now()).year
        return f"{d.day} {d:%b}" + (f" {d.year}" if d.year != year else "") + f" {d:%H:%M}"
    return t


def words(name):
    """A parameter's name in words: AutoSaveEnabled -> Auto save enabled."""
    n = str(name or "")
    if " " not in n:
        out = ""
        for i, c in enumerate(n):
            if c.isupper() and i and (n[i - 1].islower() or (i + 1 < len(n) and n[i + 1].islower())):
                out += " "
            out += c
        n = out.replace("_", " ")
        n = " ".join(w if w.isupper() and len(w) > 1 else w.lower() for w in n.split())
    return n[:1].upper() + n[1:]


def value_text(v):
    if v is None:
        return "not set"
    if isinstance(v, bool):
        return "on" if v else "off"
    t = str(v)
    return t if len(t) <= 40 else t[:39] + "…"


def change_text(c):
    """One settings-log entry as a person reads it: the setting's group and
    name in words with its real before and after; a rollback or a snapshot
    with nothing changed said as such, never "None → None"."""
    to, frm, name = c.get("to"), c.get("from"), c.get("name")
    if c.get("tool") == "pref_rollback":
        ref = str(to or "")
        text = f"Settings rolled back to before change {ref}" if ref.isdigit() else f"Settings rolled back to {when(ref)}"
    elif frm is None and to is None:
        text = "Settings snapshot" + (f" {name}" if name and " " in str(name) else f": {words(name)}" if name else "")
    else:
        group = str(c.get("path") or "").rstrip("/").split("/")[-1]
        label = words(name) if name else "Settings"
        if group and group not in ("Preferences", "BaseApp"):
            label = f"{words(group)} › {label}"
        text = f"{label}: {value_text(to)}" if frm is None else f"{label}: {value_text(frm)} → {value_text(to)}"
    return text + (" (restart)" if c.get("restart") else "")


def recovered_rows(documents, per_doc=5):
    """The Recovered Copies rows, newest first: (when, what, data)."""
    rows = []
    for d in documents or []:
        for c in (d.get("copies") or [])[:per_doc]:
            rows.append((str(c.get("time", "")), (when(c.get("time", "")), f"{d.get('label')}: {c.get('source', '')}",
                                                  {"document": d.get("document"), "label": d.get("label")})))
    return [r for _, r in sorted(rows, key=lambda x: x[0], reverse=True)]


# (Copies pruned by cleanup.py; the panel shows open documents and the
# last crash, the rest under Older.)
SOURCES = {"freecad": "FreeCAD autosave", "autosave": "SafetyNet autosave", "checkpoint": "Checkpoint"}
# A checkpoint by who took it (checkpoints.who); one from before says neither.
CHECKPOINT_BY = {"person": "My checkpoint", "agent": "Agent checkpoint"}
def source_words(source, by=None):
    """Where a copy came from, in words: freecad -> FreeCAD autosave; a
    checkpoint by who took it: My checkpoint, Agent checkpoint, or plain
    Checkpoint for one written before it said."""
    s = str(source or "")
    if s == "checkpoint" and by in CHECKPOINT_BY:
        return CHECKPOINT_BY[by]
    return SOURCES.get(s, s)


def recovered_groups(documents, open_names=(), per_doc=8):
    """The Recovered Copies by original document, newest first: copies of
    "Box", "Box_recovered", "Box_recovered1" and "Box (recovered 18:48)"
    are one group, its newest copy, how many it has and the rest under it.
    [{"label", "document", "latest": (when, what, data), "count", "rest":
    [(when, what, data)], "time", "open", "crash", "older", "expanded"}].
    Shown: the groups of documents open now and of the copies the last
    crash or forced restart of this FreeCAD brought back ("crash"); every
    other group is "older" (folded under one Older row)."""
    from .recovery import original_label, original_name

    opened = set(open_names or ())
    groups = {}
    for d in documents or []:
        if not d.get("copies"):
            continue
        key = original_name(d.get("document") or d.get("label"))
        g = groups.setdefault(key, {"copies": [], "open": False, "crash": False, "labels": []})
        data = {"document": d.get("document"), "label": d.get("label")}
        g["open"] = g["open"] or d.get("document") in opened
        g["crash"] = g["crash"] or any(c.get("crash") for c in d.get("copies"))
        g["labels"].append(original_label(d.get("label") or d.get("document")))
        g["copies"] += [(str(c.get("time", "")), c, data) for c in d.get("copies")]
    out = []
    for key, g in groups.items():
        copies = sorted(g["copies"], key=lambda x: x[0], reverse=True)
        label = g["labels"][0] if g["labels"] else key
        for lab in g["labels"]:  # the shortest: the original's own label
            label = lab if len(lab) < len(label) else label
        rows = [(when(t), source_words(c.get("source"), c.get("by")), data) for t, c, data in copies[:per_doc]]
        latest = copies[0][0]
        out.append({"label": label, "document": key, "latest": rows[0], "count": len(copies), "rest": rows[1:],
                    "time": latest, "open": g["open"], "crash": g["crash"], "older": not (g["open"] or g["crash"]),
                    "expanded": g["open"]})
    out.sort(key=lambda g: g["time"], reverse=True)
    return out


def group_text(g):
    """A document's row: WindowTest — FreeCAD autosave (6 copies)."""
    n = g["count"]
    return f"{g['label']} — {g['latest'][1]}" + (f" ({n} copies)" if n > 1 else "")


# ---- message boxes: SafetyNet's title, a short bold line, the rest under it ------------

HEADLINES = {"information": "Done", "warning": "Couldn't do that", "question": "Are you sure?"}


def message(QtWidgets, parent, text, kind="information", headline=None, title=TITLE):
    """A message box as FreeCAD's own are laid out: the window titled
    SafetyNet (macOS shows no title on a message box, set anyway), a short
    bold first line, and the sentence under it as the informative text."""
    from html import escape

    icons = {"information": "Information", "warning": "Warning", "question": "Question"}
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(getattr(QtWidgets.QMessageBox, icons.get(kind, "Information")))
    box.setWindowTitle(title)
    box.setText(f"<b>{escape(headline or HEADLINES.get(kind, TITLE))}</b>")
    box.setInformativeText(str(text))
    if kind == "question":
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setDefaultButton(QtWidgets.QMessageBox.No)
    run = getattr(box, "exec", None) or box.exec_
    return run()


def never_saved(name):
    """What to say when a recovered copy opened that has no file of its own:
    (headline, text)."""
    return "Recovered copy opened", f"{name} is open. It has never been saved, so save it where you like."


# ---- the buttons: each acts on one kind of row ------------------------------------------

BUTTONS = (("Use Copy", "recover", "Open the picked copy and offer to save it over its file."),
           ("Roll Back", "pref", "Put the settings back as they were before the picked change."),
           ("Approve Macro", "macro", "Let the picked macro run from SafetyNet and Agent Link."),
           ("Run Macro", "macro", "Run the picked macro as FreeCAD's Macro dialog does."))
# Run Macro runs any approved macro alone too; one made of Agent Link calls
# is refused there with why.
NEEDS_AGENT_LINK = set()
MACRO_DIALOG = "Std_DlgMacroExecute"


def open_macro_dialog():
    """FreeCAD's own Macro ▸ Macros… dialog."""
    import FreeCADGui

    FreeCADGui.runCommand(MACRO_DIALOG, 0)


def buttons_for(kind, hosted):
    """The buttons that act on a row of this kind (recover, pref, macro;
    None for a section title or the Older row)."""
    return {label for label, k, _ in BUTTONS if k == kind and (hosted or label not in NEEDS_AGENT_LINK)}


def qss(r):
    """SafetyNet's rules, scoped to its own widget by object name."""
    return (f"#{NAME} QLabel#SafetyNetPinned {{ color: {r['accent']}; font-weight: bold; }}\n"
            f"#{NAME} QLabel#SafetyNetHeld {{ color: {r['muted']}; }}\n"
            f"#{NAME} QPushButton#SafetyNetGo:enabled {{ color: {r['accent']}; font-weight: bold; }}\n"
            f"#{NAME} QTreeWidget {{ selection-background-color: {r['accent']}; }}\n")


def make(panel):
    """factory(panel) for Agent Link's register_tab: the tab's widget, whose
    fill() Agent Link calls each time the tab comes up."""
    return widget(panel._call, hosted=True)


def widget(runner, hosted=False):
    """The Session widget over a runner; hosted: Agent Link runs the calls."""
    QtCore, QtWidgets = _qt()
    from PySide import QtGui

    from . import theme

    STATE = {"approved": "ok", "changed": "warn"}

    class SessionTab(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setObjectName(NAME)
            self.hosted = hosted
            lay = QtWidgets.QVBoxLayout(self)
            self.pinned = QtWidgets.QLabel("")
            self.pinned.setObjectName("SafetyNetPinned")
            self.pinned.setWordWrap(True)
            self.pinned.setToolTip("The document the agent works in.")
            lay.addWidget(self.pinned)
            held = QtWidgets.QHBoxLayout()
            self.held = QtWidgets.QLabel("")
            self.held.setObjectName("SafetyNetHeld")
            self.held.setWordWrap(True)
            held.addWidget(self.held, 1)
            self.go = QtWidgets.QPushButton("Go")
            self.go.setObjectName("SafetyNetGo")
            self.go.setToolTip("Run the heavy jobs held for you.")
            self.go.clicked.connect(lambda: self.do("queue_go", {}))
            held.addWidget(self.go)
            lay.addLayout(held)
            self.agent_rows = (self.pinned, self.held, self.go)
            for w in self.agent_rows:
                w.setVisible(hosted)
            self.tree = QtWidgets.QTreeWidget()
            self.tree.setHeaderLabels(["", "When", "What"])
            self.tree.setRootIsDecorated(True)
            # Long names cut in the middle, the full name in the tooltip.
            self.tree.setWordWrap(False)
            self.tree.setTextElideMode(QtCore.Qt.ElideMiddle)
            try:
                # Group titles span the row; When fits its dates; What takes
                # the rest. No fixed widths to clip them.
                head = self.tree.header()
                fit = QtWidgets.QHeaderView.ResizeToContents
                head.setSectionResizeMode(0, fit)
                head.setSectionResizeMode(1, fit)
                head.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
                head.setStretchLastSection(True)
            except Exception:
                pass
            lay.addWidget(self.tree, 1)
            # Two by two: four in a row were cut off in a narrow dock. The
            # copies' and settings' buttons on the first row, the macros' on
            # the second; each enabled only when the picked row is its kind.
            row = QtWidgets.QGridLayout()
            self.buttons = {}
            acts = {"Use Copy": self.accept, "Roll Back": self.rollback, "Approve Macro": self.approve, "Run Macro": self.run}
            for label, _kind, tip in BUTTONS:
                b = QtWidgets.QPushButton(label)
                b.setToolTip(tip)
                b.clicked.connect(acts[label])
                b.setEnabled(False)
                row.addWidget(b, len(self.buttons) // 2, len(self.buttons) % 2)
                self.buttons[label] = b
            lay.addLayout(row)
            # FreeCAD's own macro tools, a click away: SafetyNet lists the
            # same folder and adds the approval and the checkpoint.
            self.macro_link = QtWidgets.QLabel("<a href=\"macros\">Open in FreeCAD's Macro dialog</a>")
            self.macro_link.setToolTip("FreeCAD's Macro dialog, to record, edit or run macros by hand.")
            self.macro_link.linkActivated.connect(lambda *_: open_macro_dialog())
            self.tree.itemSelectionChanged.connect(self.picked)
            lay.addWidget(self.macro_link)
            self.roles = theme.roles(self)
            theme.follow(self, self._styled)

        def _styled(self, r):
            self.roles = r
            return qss(r)

        def say(self, text, kind="information", headline=None):
            message(QtWidgets, self, text, kind, headline)

        def kind_of(self, it):
            raw = it.data(0, QtCore.Qt.UserRole) if it is not None else None
            try:
                return (json.loads(raw) or {}).get("kind") if isinstance(raw, str) and raw else None
            except ValueError:
                return None

        def enable_for(self, kind):
            """Only the buttons that act on a row of this kind enabled."""
            on = buttons_for(kind, self.hosted)
            for label, b in self.buttons.items():
                b.setEnabled(label in on)
            return on

        def picked(self):
            return self.enable_for(self.kind_of(self.tree.currentItem()))

        def do(self, tool, args):
            ok, r = runner(tool, args)
            if not ok:
                self.say((r.get("error") or {}).get("message", str(r)), "warning", "Couldn't do that")
            self.fill()
            return ok, r

        def read(self, tool, args):
            """The panel's own refresh: under Agent Link quiet (not the
            agent's work: nothing shown, nothing in Activity); the person's
            clicks go through do() and show."""
            if getattr(runner, "quiet_ok", False):
                return runner(tool, args, quiet=True)
            return runner(tool, args)

        def fill(self):
            from . import layout

            with layout.keep_marks():  # a refresh changes nothing: the "*" as it was
                self._fill()

        def _fill(self):
            if self.hosted:
                ok, d = self.read("doc_switch", {})
                name = (d.get("label") or d.get("document")) if ok else None
                self.pinned.setText(f"Agent works in: {name}" if name else "Agent works in: the document in front")
                q = _load(path("queue.json"), {}) or {}
                held = q.get("held") or []
                self.held.setText(f"Held for your go: {q.get('notice') or len(held)}" if held else "Nothing held.")
                self.go.setEnabled(bool(held))
            self.tree.clear()
            self.enable_for(None)

            def section(title, rows, kind):
                top = QtWidgets.QTreeWidgetItem([title, "", ""])
                top.setForeground(0, QtGui.QBrush(QtGui.QColor(self.roles["accent"])))
                for r in rows:
                    it = QtWidgets.QTreeWidgetItem(["", str(r[0]), str(r[1])])
                    it.setToolTip(2, str(r[1]))
                    it.setData(0, QtCore.Qt.UserRole, json.dumps({"kind": kind, **r[2]}))
                    it.setForeground(1, QtGui.QBrush(QtGui.QColor(self.roles[STATE.get(r[0], "muted") if kind == "macro" else "muted"])))
                    top.addChild(it)
                self.tree.addTopLevelItem(top)
                top.setFirstColumnSpanned(True)
                top.setExpanded(bool(rows))

            ok, rec = self.read("app_recover", {"action": "list"})
            self.recovered(recovered_groups(rec.get("documents") if ok else [], _open_names()))
            ok, ph = self.read("pref_history", {"limit": 10})
            section("Settings Changes", [(when(c.get("time", "")), change_text(c), {"to": c.get("change")})
                                         for c in (ph.get("changes") or [])] if ok else [], "pref")
            ok, ml = self.read("macro_list", {})
            section("Macros", [(m.get("state", ""), m.get("name"), {"name": m.get("name")})
                               for m in (ml.get("macros") or [])] if ok else [], "macro")

        def recovered(self, groups):
            """Recovered Copies by original document: a row a document (its
            newest copy and the count, which Use Copy acts on as well), its
            other copies under it, unfolded only for open documents; those
            the last crash brought back under Last crash; the rest under
            one folded Older row."""
            top = QtWidgets.QTreeWidgetItem(["Recovered Copies", "", ""])
            top.setForeground(0, QtGui.QBrush(QtGui.QColor(self.roles["accent"])))
            muted = QtGui.QBrush(QtGui.QColor(self.roles["muted"]))
            older = [g for g in groups if g.get("older")]
            fold = crash = None
            if older:
                fold = QtWidgets.QTreeWidgetItem(["", "Older", f"{len(older)} closed documents"])
                fold.setToolTip(2, "Copies of documents that are not open now.")
                fold.setForeground(1, muted)
            if any(g.get("crash") for g in groups):
                crash = QtWidgets.QTreeWidgetItem(["", "Last crash", "Copies brought back after it"])
                crash.setToolTip(2, "Copies opened after the last crash or forced restart.")
                top.addChild(crash)
            for g in groups:
                when_, what, data = g["latest"]
                n = g["count"]
                head = QtWidgets.QTreeWidgetItem(["", str(when_), group_text(g)])
                head.setToolTip(2, f"{g['label']}: {n} saved copies, newest first")
                head.setData(0, QtCore.Qt.UserRole, json.dumps({"kind": "recover", **data}))
                for r in g["rest"]:
                    it = QtWidgets.QTreeWidgetItem(["", str(r[0]), str(r[1])])
                    it.setToolTip(2, f"{r[2].get('label')}: {r[1]}")
                    it.setData(0, QtCore.Qt.UserRole, json.dumps({"kind": "recover", **r[2]}))
                    it.setForeground(1, muted)
                    head.addChild(it)
                (fold if g.get("older") else crash if g.get("crash") else top).addChild(head)
                head.setExpanded(bool(g["expanded"]) and bool(g["rest"]))
            if crash is not None:
                crash.setExpanded(True)
            if fold is not None:
                top.addChild(fold)
                fold.setExpanded(False)
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            top.setExpanded(bool(groups))
            return top

        def pick(self, kind):
            it = self.tree.currentItem()
            raw = it.data(0, QtCore.Qt.UserRole) if it else None
            d = json.loads(raw) if raw else None
            if not d or d.get("kind") != kind:
                self.say(f"Pick a line under {dict(recover='Recovered Copies', pref='Settings Changes', macro='Macros')[kind]} first.", headline="Nothing picked")
                return None
            return d

        def typed(self, title, want):
            text, ok = QtWidgets.QInputDialog.getText(self, title, f"Type  {want}  to confirm:")
            return text if ok and text.strip() == want else None

        def accept(self):
            d = self.pick("recover")
            if d:
                ok, r = self.do("app_recover", {"action": "auto", "documents": [{"name": d["document"], "label": d.get("label")}]})
                rec = (r.get("recovered") or [None])[0] if ok else None
                if rec:
                    if not rec.get("file"):
                        headline, text = never_saved(rec["as"])
                        self.say(text, headline=headline)
                        return
                    from .commands import approve_in_window, pending_words
                    from . import handlers

                    def again(confirm=None):
                        ok2, r2 = self.do("app_recover", {"action": "accept", "document": rec["document"], **({"confirm": confirm} if confirm else {})})
                        if ok2 and r2.get("pending"):
                            # Agent Link: the approval, never typed words (an agent can type).
                            self.say(pending_words(r2, approve_in_window(r2, again)), "warning", "Approve the recovered copy")

                    if handlers.PERSON_OK is not None:
                        again()
                    else:
                        typed = self.typed("Use Recovered Copy", f"save over {os.path.basename(rec['file'])}")
                        if typed:
                            again(typed)

        def rollback(self):
            d = self.pick("pref")
            if d and d.get("to") is not None:
                self.do("pref_rollback", {"to": d["to"]})

        def approve(self):
            d = self.pick("macro")
            if d:
                from .commands import approve_in_window, pending_words

                ok, r = self.do("macro_approve", {"name": d["name"]})
                if ok and r.get("pending"):
                    self.say(pending_words(r, approve_in_window(r, self.fill)), "warning", "Approve the macro")

        def run(self):
            d = self.pick("macro")
            if d:
                self.do("macro_run", {"name": d["name"]})

    return SessionTab()


# ---- SafetyNet's own dock (Agent Link not loaded) ------------------------------------------

DOCK = "SafetyNetDock"
# The workbench its hosted tab belongs to: SafetyNet has none of its own
# since it joined Workshop, so it goes with Make.
WORKBENCH = "WorkshopMakeWorkbench"


def _open_names():
    """The documents open in FreeCAD now (none without it)."""
    try:
        import FreeCAD

        return list(FreeCAD.listDocuments())
    except Exception:  # noqa: BLE001
        return []


def _main():
    import FreeCADGui

    return FreeCADGui.getMainWindow()


def _raise_hosted_tab(mw):
    """Agent Link's panel tab holding the Session widget, brought to front;
    False when its panel is not open."""
    _, QtWidgets = _qt()
    for tabs in mw.findChildren(QtWidgets.QTabWidget):
        for i in range(tabs.count()):
            if tabs.widget(i) is not None and tabs.widget(i).objectName() == NAME:
                tabs.setCurrentIndex(i)
                w = tabs.parentWidget()
                while w is not None and not isinstance(w, QtWidgets.QDockWidget):
                    w = w.parentWidget()
                if w is not None:
                    w.show()
                    w.raise_()
                fill = getattr(tabs.widget(i), "fill", None)
                if fill:
                    fill()
                return True
    return False


def show():
    """The Panel command: Agent Link's Session tab when Agent Link hosts
    SafetyNet (put in its bar for now outside the Make workbench), else
    SafetyNet's own dock, placed by the panel layout setting (layout.py)
    for the workbench it was opened in (Tools ▸ SafetyNet reaches it from
    any)."""
    import importlib

    import safetynet

    from . import layout

    _, QtWidgets = _qt()
    mw = _main()
    if getattr(safetynet, "_hosted", False) and layout.in_agentlink_panel("Session"):
        try:
            importlib.import_module("agentlink.panel").show(tab="Session")
            return "hosted"
        except Exception:  # noqa: BLE001 — an Agent Link before tabs per workbench
            if _raise_hosted_tab(mw):
                return "hosted"
    dock = mw.findChild(QtWidgets.QDockWidget, DOCK)
    if dock is None:
        from . import local

        dock = QtWidgets.QDockWidget("SafetyNet", mw)
        dock.setObjectName(DOCK)
        # Under Agent Link its clicks run through it (shown and logged as
        # the agent's are) and the rows that need it show; alone, local.
        c = layout.caller() if getattr(safetynet, "_hosted", False) else None
        dock.setWidget(widget(c._call, hosted=True) if c is not None else widget(local.run, hosted=False))
    content = getattr(dock, "_content", None) or dock.widget()
    dock._content = content  # kept: in the Combo View or the slide-out it is not the dock's
    p = layout.placer()
    p.show(DOCK, dock, layout.active_workbench() or WORKBENCH, "SafetyNet")
    p.reveal(DOCK)
    fill = getattr(content, "fill", None)
    if fill:
        fill()
    return "dock"
