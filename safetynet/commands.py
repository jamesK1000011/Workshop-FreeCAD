# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's FreeCAD commands: checkpoints, recovered copies, the settings
# log and its rollback, and macros, by hand. Each runs the same handler the
# agent's tool does (local.run: one undo step, the same refusals), with no
# agent and no Agent Link needed. Small dialogs: a pick list or a typed
# confirm where a task panel would be overkill.
import os

import FreeCAD
import FreeCADGui

from . import local
from .panel import when

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _qt():
    from PySide import QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
    return QtWidgets


def _mw():
    try:
        return FreeCADGui.getMainWindow()
    except Exception:
        return None


def say(text, headline, error=False):
    """The Report view line and a message box: a short bold headline, the
    sentence under it."""
    (FreeCAD.Console.PrintError if error else FreeCAD.Console.PrintMessage)(f"SafetyNet: {text}\n")
    try:
        from .panel import message

        message(_qt(), _mw(), text, "warning" if error else "information", headline)
    except Exception:
        pass


def call(tool, args=None, quiet=False):
    """The handler through the local runner; a refusal shown. The answer or None."""
    ok, r = local.run(tool, args or {})
    if not ok:
        if not quiet:
            say((r.get("error") or {}).get("message", str(r)), "Couldn't do that", error=True)
        return None
    return r


def pick(title, label, items):
    """One of items (text, value) picked from a list, or None."""
    if not items:
        return None
    QtWidgets = _qt()
    texts = [t for t, _ in items]
    text, ok = QtWidgets.QInputDialog.getItem(_mw(), title, label, texts, 0, False)
    if not ok:
        return None
    return items[texts.index(text)][1]


def approve_in_window(r, again):
    """A pending answer to the person's own click: Agent Link's Approve
    dialog in the FreeCAD window (only a press by the person counts), and
    again() after the press. False when Agent Link cannot show it."""
    from . import handlers

    show = handlers.APPROVAL_IN_WINDOW
    try:
        return bool(show and show(r, again))
    except Exception:  # noqa: BLE001
        return False


def pending_words(r, shown):
    tool = ((r or {}).get("approve") or {}).get("tool") or "the approval tool"
    return ("Press Approve in the dialog in the FreeCAD window." if shown else
            f"This needs your approval: approve it in Claude ({tool}), or turn on Mod/AgentLink WindowApprove for a dialog here.")


def _with_agentlink():
    from . import handlers

    return handlers.PERSON_OK is not None


def typed(title, want, why=""):
    """The person's typed confirm, when it is word for word; else None."""
    QtWidgets = _qt()
    text, ok = QtWidgets.QInputDialog.getText(_mw(), title, f"{why}\nType  {want}  to confirm:".strip())
    return text if ok and text.strip() == want else None


def has_doc():
    return FreeCAD.ActiveDocument is not None


def show_text(title, text):
    QtWidgets = _qt()
    dlg = QtWidgets.QDialog(_mw())
    dlg.setWindowTitle(title)
    lay = QtWidgets.QVBoxLayout(dlg)
    view = QtWidgets.QPlainTextEdit()
    view.setReadOnly(True)
    view.setPlainText(text)
    lay.addWidget(view)
    close = QtWidgets.QPushButton("Close")
    close.clicked.connect(dlg.accept)
    lay.addWidget(close)
    dlg.resize(560, 420)
    dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()


class _Cmd:
    menu, tip, pixmap = "", "", ""

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tip, "Pixmap": self.pixmap}

    def IsActive(self):
        return True


class Checkpoint(_Cmd):
    menu, pixmap = "Checkpoint Now", "SafetyNet_Checkpoint"
    tip = "Save a copy of the document to come back to later."

    def IsActive(self):
        return has_doc()

    def Activated(self):
        r = call("history_checkpoint", {})
        if r:
            FreeCAD.Console.PrintMessage(f"SafetyNet: checkpoint {r['checkpoint']} of {FreeCAD.ActiveDocument.Label} ({r.get('bytes', 0) // 1024} KB).\n")
            try:
                FreeCADGui.getMainWindow().statusBar().showMessage(f"SafetyNet: checkpoint {r['checkpoint']} saved", 4000)
            except Exception:
                pass


class Restore(_Cmd):
    menu, pixmap = "Restore Checkpoint…", "SafetyNet_Restore"
    tip = "Go back to one of this document's checkpoints."

    def IsActive(self):
        return has_doc()

    def Activated(self):
        r = call("history_checkpoint", {"list": True})
        if r is None:
            return
        rows = [(f"{c['checkpoint']}{' · ' + c['name'] if c.get('name') else ''} · {when(c.get('time', ''))}{' · auto' if c.get('auto') else ''}", c["checkpoint"])
                for c in reversed(r.get("checkpoints") or [])]
        if not rows:
            say(f"{r.get('document')} has no checkpoints yet. Checkpoint Now takes one.", "No checkpoints yet")
            return
        cp = pick("Restore Checkpoint", f"Back to which checkpoint of {r.get('document')}?", rows)
        if cp:
            out = call("history_restore", {"checkpoint": cp})
            if out:
                say(f"Back at {cp}." + (f" The state before is {out['before']}." if out.get("before") else ""), "Checkpoint restored")


class Recover(_Cmd):
    menu, pixmap = "Recovered Copies…", "SafetyNet_Recover"
    tip = "Open a saved copy of a document after a crash."

    def Activated(self):
        r = call("app_recover", {"action": "list"})
        if r is None:
            return
        docs = r.get("documents") or []
        rows = []
        for d in docs:
            newest = (d.get("copies") or [{}])[0]
            rows.append((f"{d.get('label')} · {len(d.get('copies') or [])} copies · newest {newest.get('source', '')} {when(newest.get('time', ''))}", d))
        if not rows:
            say("No saved copies of any document here.", "No recovered copies")
            return
        d = pick("Recovered Copies", "Open the newest good copy of which document (beside its file)?", rows)
        if not d:
            return
        out = call("app_recover", {"action": "auto", "documents": [{"name": d["document"], "label": d.get("label")}]})
        rec = (out or {}).get("recovered") or []
        if not rec:
            if out and out.get("failed"):
                say(f"No copy of {d.get('label')} opened: {out['failed']}", "Copy not opened", error=True)
            return
        rec = rec[0]
        if not rec.get("file"):
            from .panel import never_saved

            headline, text = never_saved(rec.get("as"))
            say(text, headline)
            return
        def accept(confirm=None):
            done = call("app_recover", {"action": "accept", "document": rec["document"], **({"confirm": confirm} if confirm else {})})
            if done and done.get("pending"):
                # Agent Link: the approval, never typed words (an agent can type).
                say(pending_words(done, approve_in_window(done, accept)), "Approve the recovered copy")
            elif done:
                say(f"Saved over {done['saved']}." + (f" The old file is kept at {done['previousFile']}." if done.get("previousFile") else ""), "Recovered copy saved")

        if _with_agentlink():
            accept()
            return
        want = f"save over {os.path.basename(rec['file'])}"
        t = typed("Use Recovered Copy", want, f"{rec.get('as')} is open beside your file. To make it the file (the old one is kept):")
        if t:
            accept(t)


def _changes(limit=20):
    r = call("pref_history", {"limit": limit})
    return (r or {}).get("changes") or []


def _change_text(c):
    from .panel import change_text

    return f"#{c['change']} · {when(c.get('time', ''))} · {change_text(c)}"


class CleanUp(_Cmd):
    menu, pixmap = "Clean Up Copies…", "SafetyNet_Recover"
    tip = "Remove old recovered copies, after showing what would go."

    def Activated(self):
        from . import cleanup
        from .panel import message

        s = cleanup.settings()
        dry = cleanup.prune(dry_run=True)
        rules = (f"Kept: the newest {s['CopiesKeep']} copies of each document, none older than {s['CopiesMaxAgeDays']} days "
                 f"({s['ScratchMaxAgeDays']} for never-saved documents), and always open documents, the last crash and copies used this week.")
        if not dry["count"]:
            say(f"Nothing to clean up. {rules}", "No old copies")
            return
        QtWidgets = _qt()
        sure = message(QtWidgets, _mw(), f"{dry['count']} old copies ({dry['mb']} MB) go to the Trash, or are removed where there is none. {rules}", "question",
                       f"Remove {dry['count']} old copies?")
        if sure != QtWidgets.QMessageBox.Yes:
            return
        out = cleanup.prune(dry_run=False)
        where = "moved to the Trash" if out.get("trashed") == out.get("removed") else "removed"
        text = f"{out.get('removed', 0)} copies ({out.get('mb', 0)} MB) {where}."
        if out.get("failed"):
            text += f" {len(out['failed'])} could not be moved."
        say(text, "Copies cleaned up", error=bool(out.get("failed")))


class SettingsHistory(_Cmd):
    menu, pixmap = "Settings History…", "preferences-system"
    tip = "Show the logged settings changes, newest first."

    def Activated(self):
        rows = _changes(50)
        show_text("Settings History", "\n".join(_change_text(c) for c in rows) if rows else "No settings changes logged.")


class Rollback(_Cmd):
    menu, pixmap = "Roll Back Setting…", "edit-undo"
    tip = "Put FreeCAD's settings back as they were before a change."

    def Activated(self):
        rows = _changes(20)
        if not rows:
            say("No settings changes logged to roll back.", "No settings changes")
            return
        ch = pick("Roll Back Setting", "Put the settings back as they were before which change?", [(_change_text(c), c["change"]) for c in rows])
        if ch is None:
            return
        from .panel import message

        QtWidgets = _qt()
        sure = message(QtWidgets, _mw(), f"All of FreeCAD's settings go back to how they were before change #{ch}. The settings now are snapshotted first.", "question", "Roll back settings?")
        if sure != QtWidgets.QMessageBox.Yes:
            return
        out = call("pref_rollback", {"to": ch})
        if out:
            say(out.get("note") or f"Rolled back to {out.get('rolledBackTo')}.", "Settings rolled back")


class Macros(_Cmd):
    menu, pixmap = "Macros…", "SafetyNet_Macros"
    tip = "Show, approve, run or unapprove the macros in FreeCAD's folder."

    def Activated(self):
        r = call("macro_list", {})
        if r is None:
            return
        rows = [(f"{m['name']} · {m.get('state', '')}{' · ' + m['about'] if m.get('about') else ''}", m["name"]) for m in r.get("macros") or []]
        dialog = "Open in FreeCAD's Macro dialog"
        rows.append((dialog, dialog))
        name = pick("Macros", f"Macros in FreeCAD's macro folder, {r.get('folder')}:", rows)
        if not name:
            return
        if name == dialog:
            from .panel import open_macro_dialog

            open_macro_dialog()
            return
        what = pick(name, "Do what with it?", [("Show", "show"), ("Approve…", "approve"), ("Run", "run"), ("Take approval back", "unapprove")])
        if what == "show":
            m = call("macro_show", {"name": name})
            if m:
                show_text(f"{name} · {m.get('state')}", m.get("text", ""))
        elif what == "approve":
            m = call("macro_show", {"name": name})
            if m:
                show_text(f"{name} · read before approving", m.get("text", ""))
                # The approval is Agent Link's (approve_code, or a press on its
                # Approve dialog in the window for this click of the person's).
                r = call("macro_approve", {"name": name})
                if r and r.get("approved"):
                    say(f"{name} is approved. It runs until its file changes.", "Macro approved")
                elif r and r.get("pending"):
                    say(pending_words(r, approve_in_window(r, lambda: say(f"{name} is approved. It runs until its file changes.", "Macro approved"))), "Approve the macro")
        elif what == "run":
            done = call("macro_run", {"name": name})
            if done:
                say(f"{name} ran." + (f" Checkpoint {done['checkpoint']} goes back to before it." if done.get("checkpoint") else ""), "Macro ran")
        elif what == "unapprove":
            if call("macro_unapprove", {"name": name}) is not None:
                say(f"{name} is off the approved list.", "Approval taken back")


class Panel(_Cmd):
    menu, pixmap = "SafetyNet Panel", "SafetyNet_Workbench"
    tip = "Show recovered copies, settings changes and macros."

    def Activated(self):
        from . import layout, panel

        # Slid out over the 3D view (PanelLayout left-slide): opens and
        # closes it; else shows the panel.
        layout.toggle_or(panel.show)


class Menu:
    """Tools ▸ SafetyNet in every workbench: the commands as one submenu."""

    def GetCommands(self):
        return tuple(NAMES)

    def GetResources(self):
        return {"MenuText": "SafetyNet", "ToolTip": "Checkpoints, recovered copies, settings and macros.", "Pixmap": "SafetyNet_Workbench",
                "DropDownMenu": True, "Exclusive": False}

    def IsActive(self):
        return True


COMMANDS = {
    "SafetyNet_Checkpoint": Checkpoint,
    "SafetyNet_Restore": Restore,
    "SafetyNet_Recover": Recover,
    "SafetyNet_CleanUp": CleanUp,
    "SafetyNet_SettingsHistory": SettingsHistory,
    "SafetyNet_Rollback": Rollback,
    "SafetyNet_Macros": Macros,
    "SafetyNet_Panel": Panel,
}
NAMES = list(COMMANDS)
TOOLBAR = [n for n in NAMES if n != "SafetyNet_CleanUp"]  # a menu command
MENU = "SafetyNet_Menu"

_done = []


def register():
    """Each command added once (InitGui runs this at start)."""
    if _done:
        return
    for name, cls in COMMANDS.items():
        FreeCADGui.addCommand(name, cls())
    FreeCADGui.addCommand(MENU, Menu())
    _done.append(True)
