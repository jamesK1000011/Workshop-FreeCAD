# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's GUI layer with FreeCAD absent: every tool has its handler and
# the family binds exactly those; the local runner answers in Agent Link's
# shape (InitGui is the Workshop add-on's: tests/test_loads.py); the theme reads its accents from
# a parameter fixture; the Session widget alone never asks for the rows that
# need Agent Link; the plain modules import nothing of Agent Link.
import ast
import contextlib
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from safetynet import handlers, local, theme  # noqa: E402

FAMS = ("fam_history", "fam_safety")
# Agent Link's source, where it is checked out beside this one (or named).
AGENTLINK = os.environ.get("AGENTLINK_SRC") or os.path.join(os.path.dirname(ROOT), "freecad-agentlink")


def bound_names(fam):
    """(tool name, handler key) for each Tool(...) a family module declares."""
    tree = ast.parse(open(os.path.join(ROOT, "safetynet", fam + ".py"), encoding="utf-8").read())
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "Tool":
            name = n.args[0].value
            fn = n.args[3]
            key = fn.args[0].slice.value if isinstance(fn, ast.Call) and isinstance(fn.args[0], ast.Subscript) else None
            out.append((name, key))
    return out


class FakeDoc:
    def __init__(self, name="Doc"):
        self.Name = self.Label = name
        self.FileName = ""
        self.UndoCount = 0
        self.Objects = []
        self.log = []

    def openTransaction(self, n):
        self.log.append(("open", n))

    def commitTransaction(self):
        self.log.append(("commit",))

    def abortTransaction(self):
        self.log.append(("abort",))


def fake_freecad(doc=None, macro_dir=None):
    fc = types.ModuleType("FreeCAD")
    fc.ActiveDocument = doc
    fc.GuiUp = True
    fc.listDocuments = lambda: {doc.Name: doc} if doc else {}
    fc.getUserMacroDir = lambda *_: macro_dir or tempfile.mkdtemp()
    fc.getUserAppDataDir = lambda: tempfile.mkdtemp()
    fc.getUserCachePath = lambda: tempfile.mkdtemp()

    class Grp:
        def __getattr__(self, n):
            return lambda *a: (a[1] if len(a) > 1 else None)

    fc.ParamGet = lambda *_: Grp()
    fc.Console = types.SimpleNamespace(PrintMessage=lambda *_: None, PrintWarning=lambda *_: None, PrintError=lambda *_: None)
    return fc


class Parity(unittest.TestCase):
    def test_every_tool_has_its_handler(self):
        names = [n for fam in FAMS for n, _ in bound_names(fam)]
        self.assertEqual(sorted(names), sorted(handlers.HANDLERS))
        for fam in FAMS:
            for name, key in bound_names(fam):
                self.assertEqual(name, key, f"{fam}: {name} is bound to {key}")

    def test_with_agent_link_the_family_binds_the_handlers(self):
        sys.path.append(AGENTLINK)
        try:
            from agentlink.protocol import ToolError

            from safetynet import fam_history, fam_safety
        except ImportError:
            self.skipTest("Agent Link is not beside it")
        finally:
            sys.path.remove(AGENTLINK)
        s = types.SimpleNamespace()
        tools = {t.name: t for fam in (fam_history, fam_safety) for t in fam.tools(s)}
        self.assertEqual(sorted(tools), sorted(handlers.HANDLERS))
        # The same refusal either way: Agent Link's ToolError from the tool,
        # the local runner's error from the handler.
        for name, args in (("macro_show", {"name": "../x"}), ("macro_approve", {"name": "a/b", "confirm": ""})):
            with self.assertRaises(ToolError) as e:
                tools[name].fn(args)
            ok, r = local.run(name, args)
            self.assertFalse(ok)
            self.assertEqual((e.exception.code, e.exception.message), (r["error"]["code"], r["error"]["message"]))
        for fam in (fam_history, fam_safety):
            self.assertTrue(set(fam.AREAS) <= {"history_", "app_recover", "pref_", "macro_"})
            self.assertFalse(getattr(fam, "WORKBENCHES", None), "a safety call never switches the bench")


class LocalRunner(unittest.TestCase):
    def test_refusals_and_answers_in_agent_links_shape(self):
        doc = FakeDoc()
        mdir = tempfile.mkdtemp()
        with mock.patch.dict(sys.modules, {"FreeCAD": fake_freecad(doc, mdir)}):
            ok, r = local.run("macro_list", {})
            self.assertTrue(ok, r)
            self.assertEqual(r, {"folder": mdir, "macros": []})
            self.assertEqual(doc.log[-2:], [("open", "SafetyNet: macro_list"), ("commit",)])
            ok, r = local.run("macro_show", {"name": "nope"})
            self.assertFalse(ok)
            self.assertEqual(r["error"]["code"], "not_found")
            self.assertEqual(doc.log[-1], ("abort",))
            ok, r = local.run("queue_go", {})
            self.assertEqual((ok, r["error"]["code"]), (False, "not_found"))
            ok, r = local.run("macro_save", {"name": "m"})
            self.assertEqual((ok, r["error"]["code"]), (False, "invalid_state"))  # no agent calls to save alone

    def test_no_document(self):
        with mock.patch.dict(sys.modules, {"FreeCAD": fake_freecad(None)}):
            ok, r = local.run("history_checkpoint", {})
        self.assertEqual((ok, r["error"]["code"]), (False, "invalid_state"))

    def test_sessions_never_share_an_id(self):
        a, b = local.LocalSession(), local.LocalSession()
        self.assertNotEqual(id(a), id(b))
        self.assertTrue(a.in_place)
        self.assertIsNone(a.server)


class Theme(unittest.TestCase):
    def test_accents_from_a_parameter_file(self):
        a = theme.accents(os.path.join(HERE, "data", "theme.cfg"))
        self.assertEqual(a, ["#3f93d6", "#b477ff", None])

    def test_accents_from_a_parameter_group(self):
        grp = types.SimpleNamespace(GetUnsigned=lambda n, d=0: {"ThemeAccentColor1": 0x112233FF}.get(n, d))
        r = theme.roles(params=grp)
        self.assertEqual((r["accent"], r["accent2"], r["accent3"]), ("#112233",) * 3)
        for k in ("muted", "ok", "warn", "bad"):
            self.assertRegex(r[k], r"^#[0-9a-f]{6}$")

    def test_no_accent_falls_back(self):
        grp = types.SimpleNamespace(GetUnsigned=lambda n, d=0: 0)
        self.assertEqual(theme.accents(grp), [None, None, None])
        self.assertRegex(theme.roles(params=grp)["accent"], r"^#[0-9a-f]{6}$")
        self.assertIsNone(theme.hex_of("x"))
        self.assertIsNone(theme.hex_of(2 ** 33))


# ---- stub FreeCADGui and Qt ------------------------------------------------------------------

class Anything:
    """A stand-in for any Qt object: every attribute a recording callable."""

    def __init__(self, *a, **k):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Member(self, name)

    def __bool__(self):
        return True


class Member:
    """owner.name, owner.name.sub, …: a call records ("name.sub", args) on owner."""

    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def __getattr__(self, sub):
        if sub.startswith("__"):
            raise AttributeError(sub)
        return Member(self.owner, f"{self.name}.{sub}")

    def __call__(self, *a, **k):
        self.owner.calls.append((self.name, a))
        return Anything()


def fake_qt():
    pyside = types.ModuleType("PySide")
    qtcore = types.ModuleType("PySide.QtCore")
    qtgui = types.ModuleType("PySide.QtGui")
    for mod in (qtcore, qtgui):
        mod.__getattr__ = lambda n: Anything
    qtcore.QObject = Anything
    qtcore.Qt = types.SimpleNamespace(UserRole=32, LeftDockWidgetArea=1, ElideMiddle=2)
    qtcore.QEvent = types.SimpleNamespace(PaletteChange=39)
    qtcore.QTimer = types.SimpleNamespace(singleShot=lambda ms, fn: None)
    qtgui.QWidget = Anything
    pyside.QtCore, pyside.QtGui = qtcore, qtgui
    return {"PySide": pyside, "PySide.QtCore": qtcore, "PySide.QtGui": qtgui}


def fake_gui(manipulators=True):
    g = types.ModuleType("FreeCADGui")
    g.registered = {"icons": [], "commands": {}, "benches": [], "manipulators": []}

    class Workbench:
        def appendToolbar(self, name, cmds):
            g.registered.setdefault("toolbars", []).append((name, list(cmds)))

        def appendMenu(self, name, cmds):
            g.registered.setdefault("menus", []).append((name, list(cmds)))

    g.Workbench = Workbench
    g.addIconPath = g.registered["icons"].append
    g.addCommand = lambda n, c: g.registered["commands"].__setitem__(n, c)
    g.addWorkbench = g.registered["benches"].append
    if manipulators:
        g.addWorkbenchManipulator = g.registered["manipulators"].append
    mw = Anything()
    g.getMainWindow = lambda: mw
    g.mw = mw
    return g


@contextlib.contextmanager
def gui_stubs(manipulators=True):
    mods = {"FreeCAD": fake_freecad(FakeDoc()), "FreeCADGui": fake_gui(manipulators), **fake_qt()}
    import safetynet

    # Fresh copies under the stubs: neither the module table nor the
    # package's attributes keep one made under another test's stubs.
    for k in ("commands", "panel"):
        sys.modules.pop("safetynet." + k, None)
        safetynet.__dict__.pop(k, None)
    with mock.patch.dict(sys.modules, mods):
        yield mods["FreeCADGui"]
    for k in ("commands", "panel"):
        sys.modules.pop("safetynet." + k, None)
        safetynet.__dict__.pop(k, None)


# InitGui (the one Workshop add-on's) is tested in tests/test_loads.py.


class SessionWidget(unittest.TestCase):
    def build(self, hosted):
        asked = []

        def runner(tool, args):
            asked.append(tool)
            return True, {}

        with gui_stubs():
            from safetynet import panel

            w = panel.widget(runner, hosted=hosted)
            w.fill()
        return w, asked

    def test_alone_hides_agent_rows_and_never_asks_for_them(self):
        w, asked = self.build(False)
        for row in w.agent_rows:
            self.assertIn(("setVisible", (False,)), row.calls)
        self.assertNotIn("doc_switch", asked)
        self.assertEqual(asked, ["app_recover", "pref_history", "macro_list"])
        self.assertIn(("setEnabled", (False,)), w.buttons["Run Macro"].calls)  # nothing picked yet
        self.assertEqual(w.enable_for("macro"), {"Approve Macro", "Run Macro"})  # runs alone as FreeCAD does

    def test_hosted_shows_them(self):
        w, asked = self.build(True)
        for row in w.agent_rows:
            self.assertIn(("setVisible", (True,)), row.calls)
        self.assertEqual(asked[0], "doc_switch")

    def test_own_refresh_is_quiet_under_agent_link(self):
        """The panel's own refresh is not the agent's work: with Agent
        Link's caller every read goes quiet (nothing shown, nothing in
        Activity); a click (do) does not."""
        seen = []

        def runner(tool, args, quiet=False):
            seen.append((tool, quiet))
            return True, {}

        runner.quiet_ok = True
        with gui_stubs():
            from safetynet import panel

            w = panel.widget(runner, hosted=True)
            w.fill()
            self.assertEqual(seen, [(t, True) for t in ("doc_switch", "app_recover", "pref_history", "macro_list")])
            del seen[:]
            w.do("queue_go", {})
        self.assertEqual(seen[0], ("queue_go", False))

    def test_group_titles_span_the_row(self):
        w, _ = self.build(False)
        tops = [c[1][0] for c in w.tree.calls if c[0] == "addTopLevelItem"]
        self.assertEqual(len(tops), 3)
        for top in tops:
            self.assertIn(("setFirstColumnSpanned", (True,)), top.calls)
        src = open(os.path.join(ROOT, "safetynet", "panel.py"), encoding="utf-8").read()
        for t in ('"Recovered Copies"', 'section("Settings Changes"', 'section("Macros"'):
            self.assertIn(t, src)
        # Long names cut in the middle (no wrapping, which would turn eliding off).
        self.assertIn(("setWordWrap", (False,)), w.tree.calls)
        self.assertIn("setTextElideMode", [c[0] for c in w.tree.calls])

    def test_recovered_rows_newest_first(self):
        from safetynet import panel

        docs = [{"document": "A", "label": "A", "copies": [{"time": "2026-11-15 09:00", "source": "autosave"}, {"time": "2026-11-14 09:00", "source": "checkpoint"}]},
                {"document": "B", "label": "B", "copies": [{"time": "2026-11-15 10:00", "source": "autosave"}]}]
        rows = panel.recovered_rows(docs)
        self.assertEqual([r[2]["document"] for r in rows], ["B", "A", "A"])
        self.assertEqual(rows[-1][1], "A: checkpoint")


class RecoveredByDocument(unittest.TestCase):
    """About forty rows of a day's autosaves on the Mac, copies of copies
    ("OpTest_recovered1") apart from their document: one row a original
    document with its count, newest first; shown only for open documents
    and the last crash, the rest folded under Older; sources in words."""

    def docs(self):
        def copies(day, hours, source="autosave"):
            return [{"time": f"{day} {h:02d}:00", "source": source} for h in hours]

        return [{"document": "WindowTest", "label": "WindowTest", "copies": copies("2026-11-15", (18, 17), "freecad")},
                {"document": "WindowTest_recovered", "label": "WindowTest (recovered 18:48)", "copies": copies("2026-11-15", (16, 15))},
                {"document": "WindowTest_recovered1", "label": "WindowTest_recovered (recovered 17:02) (recovered 18:48)",
                 "copies": [{"time": "2026-11-15 14:00", "source": "checkpoint", "by": "person"},
                            {"time": "2026-11-15 13:00", "source": "checkpoint", "by": "agent"},
                            {"time": "2026-11-15 12:00", "source": "checkpoint"}]},
                {"document": "OpTest_recovered_recovered1", "label": "OpTest_recovered1", "copies": copies("2026-11-15", (10,))},
                {"document": "OpTest", "label": "OpTest", "copies": copies("2026-11-15", (9, 8))},
                {"document": "Box", "label": "Box", "copies": copies("2026-11-14", (9,))},
                {"document": "Crashed", "label": "Crashed", "copies": [{"time": "2026-11-13 09:00", "source": "autosave", "crash": True}]},
                {"document": "Empty", "label": "Empty", "copies": []}]

    def test_one_row_an_original_document_newest_first(self):
        from safetynet import panel

        g = panel.recovered_groups(self.docs(), open_names=["Box"])
        self.assertEqual([x["label"] for x in g], ["WindowTest", "OpTest", "Box", "Crashed"])
        win, op, box, crashed = g
        self.assertEqual(win["count"], 7)
        self.assertEqual(win["latest"][1], "FreeCAD autosave")
        self.assertEqual(win["latest"][2], {"document": "WindowTest", "label": "WindowTest"})  # Use Copy acts on the row
        self.assertEqual([r[1] for r in win["rest"]], ["FreeCAD autosave", "SafetyNet autosave", "SafetyNet autosave",
                                                       "My checkpoint", "Agent checkpoint", "Checkpoint"])
        self.assertEqual(panel.group_text(win), "WindowTest — FreeCAD autosave (7 copies)")
        self.assertEqual(op["count"], 3)
        self.assertTrue(win["older"])  # closed, however recent
        self.assertTrue(op["older"])
        self.assertFalse(box["older"])  # open now, though a day old
        self.assertTrue(box["expanded"])
        self.assertFalse(crashed["older"])  # the last crash brought it back
        self.assertTrue(crashed["crash"])
        self.assertEqual(panel.group_text(box), "Box — SafetyNet autosave")

    def test_in_the_panel(self):
        from safetynet import panel

        with gui_stubs():
            w = panel.widget(lambda t, a: (True, {}), hosted=False)
            top = w.recovered(panel.recovered_groups(self.docs(), open_names=["Box"]))
        rows = [c[1][0] for c in top.calls if c[0] == "addChild"]
        self.assertEqual(len(rows), 3)  # Last crash first, Box, Older last
        crash, fold = rows[0], rows[-1]
        self.assertEqual(len([c for c in crash.calls if c[0] == "addChild"]), 1)
        self.assertIn(("setExpanded", (True,)), crash.calls)
        self.assertEqual(len([c for c in fold.calls if c[0] == "addChild"]), 2)  # WindowTest, OpTest
        self.assertIn(("setExpanded", (False,)), fold.calls)


class CheckpointWords(unittest.TestCase):
    def test_by_who_took_it(self):
        from safetynet import panel

        self.assertEqual(panel.source_words("checkpoint", "person"), "My checkpoint")
        self.assertEqual(panel.source_words("checkpoint", "agent"), "Agent checkpoint")
        self.assertEqual(panel.source_words("checkpoint"), "Checkpoint")  # written before it said
        self.assertEqual(panel.source_words("freecad", "person"), "FreeCAD autosave")


class Buttons(unittest.TestCase):
    """Each button acts on one kind of row and is enabled only on it."""

    def test_by_kind(self):
        from safetynet import panel

        self.assertEqual(panel.buttons_for("recover", True), {"Use Copy"})
        self.assertEqual(panel.buttons_for("pref", True), {"Roll Back"})
        self.assertEqual(panel.buttons_for("macro", True), {"Approve Macro", "Run Macro"})
        self.assertEqual(panel.buttons_for("macro", False), {"Approve Macro", "Run Macro"})
        self.assertEqual(panel.buttons_for(None, True), set())

    def test_in_the_panel(self):
        from safetynet import panel

        with gui_stubs():
            w = panel.widget(lambda t, a: (True, {}), hosted=True)
            for b in w.buttons.values():
                self.assertIn(("setEnabled", (False,)), b.calls)  # nothing picked yet
            self.assertIn("itemSelectionChanged.connect", [c[0] for c in w.tree.calls])
            w.enable_for("pref")
            for label, b in w.buttons.items():
                self.assertEqual(b.calls[-1], ("setEnabled", (label == "Roll Back",)))

    def test_macro_buttons_say_macro(self):
        from safetynet import panel

        labels = [b[0] for b in panel.BUTTONS]
        self.assertEqual(labels, ["Use Copy", "Roll Back", "Approve Macro", "Run Macro"])
        for _, _, tip in panel.BUTTONS:  # one short sentence each
            self.assertLessEqual(len(tip), 70, tip)
            self.assertEqual(tip.rstrip(".").count(". "), 0, tip)


class Tooltips(unittest.TestCase):
    """FreeCAD's design guide: a tooltip is one short sentence."""

    def strings(self):
        out = []
        for f in ("panel.py", "commands.py", "startup.py"):
            tree = ast.parse(open(os.path.join(ROOT, "safetynet", f), encoding="utf-8").read())
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("tip", "ToolTip") for t in n.targets) and isinstance(n.value, ast.Constant):
                    out.append(n.value.value)
                elif isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "setToolTip" and n.args and isinstance(n.args[-1], ast.Constant):
                    out.append(n.args[-1].value)
                elif isinstance(n, ast.Tuple) and len(n.elts) == 3 and all(isinstance(e, ast.Constant) for e in n.elts[:2]) and isinstance(n.elts[2], ast.Attribute):
                    out.append(n.elts[1].value)
                elif isinstance(n, ast.Dict):
                    for k, v in zip(n.keys, n.values):
                        if isinstance(k, ast.Constant) and k.value == "ToolTip" and isinstance(v, ast.Constant):
                            out.append(v.value)
        return out

    def test_one_short_sentence(self):
        tips = self.strings()
        self.assertGreater(len(tips), 10)
        for t in tips:
            self.assertLessEqual(len(t), 70, t)
            self.assertEqual(t.rstrip(".").count(". "), 0, t)


class Readable(unittest.TestCase):
    """What the Session panel and the menus show a person."""

    def setUp(self):
        from safetynet import panel

        self.P = panel

    def test_one_date_format(self):
        import datetime

        now = datetime.datetime(2026, 11, 15, 13, 0)
        when = self.P.when
        self.assertEqual(when("2026-11-15 12:41", now), "15 Nov 12:41")
        self.assertEqual(when("20261115-124100", now), "15 Nov 12:41")
        self.assertEqual(when("20251231-090000", now), "31 Dec 2025 09:00")
        self.assertEqual(when("", now), "")
        self.assertEqual(when("soon", now), "soon")

    def test_settings_changes_in_words(self):
        ct = self.P.change_text
        self.assertEqual(ct({"tool": "safetynet", "path": "BaseApp/Preferences/Document", "name": "AutoSaveEnabled", "from": False, "to": True}),
                         "Document › Auto save enabled: off → on")
        self.assertEqual(ct({"path": "BaseApp/Preferences/Units", "name": "Decimals", "from": 2, "to": 3, "restart": True}),
                         "Units › Decimals: 2 → 3 (restart)")
        self.assertEqual(ct({"path": "", "name": "before update"}), "Settings snapshot before update")
        self.assertEqual(ct({}), "Settings snapshot")
        self.assertEqual(ct({"tool": "pref_rollback", "to": "4"}), "Settings rolled back to before change 4")
        self.assertEqual(ct({"tool": "pref_rollback", "to": "20261115-124100"})[:30], "Settings rolled back to 15 Nov")
        self.assertEqual(ct({"path": "BaseApp/Preferences", "name": "pack Dark", "from": None, "to": "12 values"}), "Pack Dark: 12 values")
        for c in ({"path": "", "name": "before update"}, {"tool": "pref_rollback", "to": "4"}):
            self.assertNotIn("None", ct(c))
        self.assertEqual(self.P.words("UseVBO"), "Use VBO")

    def test_message_boxes_carry_the_title(self):
        """Titled SafetyNet everywhere (macOS ignores it, set anyway), a
        short bold first line, the sentence as the informative text."""
        made = []

        class Box:
            Information, Warning, Question, Yes, No = 1, 2, 3, 4, 8

            def __init__(self, parent):
                self.calls = []
                made.append(self)

            def __getattr__(self, n):
                return lambda *a: self.calls.append((n, a)) or 0

        qt = types.SimpleNamespace(QMessageBox=Box)
        for platform in ("darwin", "linux", "win32"):
            with mock.patch.object(sys, "platform", platform):
                self.P.message(qt, None, "Hello there.", headline="Recovered copy opened")
            calls = made[-1].calls
            self.assertIn(("setWindowTitle", ("SafetyNet",)), calls)
            self.assertIn(("setText", ("<b>Recovered copy opened</b>",)), calls)
            self.assertIn(("setInformativeText", ("Hello there.",)), calls)

    def test_never_saved_copy(self):
        headline, text = self.P.never_saved("WindowTest (recovered 18:48)")
        self.assertEqual(headline, "Recovered copy opened")
        self.assertEqual(text, "WindowTest (recovered 18:48) is open. It has never been saved, so save it where you like.")

    def test_every_message_has_a_headline(self):
        """Every message box SafetyNet shows names its short first line."""
        for f in ("panel.py", "commands.py"):
            tree = ast.parse(open(os.path.join(ROOT, "safetynet", f), encoding="utf-8").read())
            for n in ast.walk(tree):
                if not isinstance(n, ast.Call):
                    continue
                fn = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
                kw = {k.arg for k in n.keywords}
                if fn == "say" and f == "commands.py":
                    self.assertTrue(len(n.args) >= 2 or "headline" in kw, f"{f}:{n.lineno}")
                elif fn == "say" and f == "panel.py" and isinstance(n.func, ast.Attribute):
                    self.assertTrue(len(n.args) >= 3 or "headline" in kw, f"{f}:{n.lineno}")
                elif fn == "message" and n.args and getattr(n.args[0], "id", "") == "QtWidgets":
                    self.assertTrue(len(n.args) >= 5 or "headline" in kw, f"{f}:{n.lineno}")
            src = open(os.path.join(ROOT, "safetynet", f), encoding="utf-8").read()
            self.assertNotIn("was never saved to a file", src)


class NoAgentLink(unittest.TestCase):
    def test_plain_modules_import_nothing_of_agent_link(self):
        mods = "safetynet, safetynet.handlers, safetynet.local, safetynet.theme, safetynet.panel, safetynet.refusal"
        code = (f"import sys; sys.path[:0] = [{ROOT!r}, {AGENTLINK!r}]; import {mods}; "
                "print(sorted(m for m in sys.modules if m.startswith('agentlink')))")
        out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, "[]")

    def test_no_agentlink_import_statement_outside_the_family_layer(self):
        allowed = {"agentlink_families.py", "families.py", "fam_history.py", "fam_safety.py"}
        for root in (os.path.join(ROOT, "safetynet"), ROOT):
            for f in os.listdir(root):
                if not f.endswith(".py") or f in allowed:
                    continue
                tree = ast.parse(open(os.path.join(root, f), encoding="utf-8").read())
                for n in ast.walk(tree):
                    names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                    self.assertFalse(any(x.split(".")[0] == "agentlink" for x in names), f"{f} imports Agent Link")


if __name__ == "__main__":
    unittest.main()
