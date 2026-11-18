# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's macros on FreeCAD's own macro tools, without FreeCAD: the
# macros listed are the files FreeCAD's Macro dialog lists in its macro
# folder; one runs as FreeCAD runs a macro file (its globals, __name__,
# __file__, the folder importable) and only once the person approved it,
# with a checkpoint before when a document is open; a macro of Agent Link
# calls needs Agent Link; the panel opens FreeCAD's Macro dialog.
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from safetynet import local, macros  # noqa: E402
from test_gui import FakeDoc, fake_freecad, gui_stubs  # noqa: E402


def write(folder, name, text):
    p = os.path.join(folder, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def person(press=True, seen=None):
    """A stand-in Agent Link whose OK dialog the person presses (press) or
    leaves (the agent alone): sys.modules entries for mock.patch.dict."""
    hooks = types.ModuleType("agentlink.hooks")

    def person_ok(kind, name, title, lines, sha=None, on_ok=None):
        if seen is not None:
            seen.append({"kind": kind, "name": name, "sha": sha, "lines": lines})
        if press and on_ok:
            on_ok()
        return {"pending": True, "next": "press Approve"}

    hooks.person_ok = person_ok
    from safetynet import handlers

    handlers.PERSON_OK = person_ok
    return {}


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.mdir = os.path.join(self.tmp.name, "Macro")
        os.makedirs(self.mdir)
        self.env = mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.home})
        self.env.start()
        from safetynet import handlers

        self.addCleanup(setattr, handlers, "PERSON_OK", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def freecad(self, doc=None, macro_path=None):
        fc = fake_freecad(doc, self.mdir)
        if macro_path is not None:
            class Grp:
                def GetString(self, k, d=""):
                    return macro_path if k == "MacroPath" else d

                def __getattr__(self, n):
                    return lambda *a: (a[1] if len(a) > 1 else None)

            fc.ParamGet = lambda *_: Grp()
        return fc


class Listing(Home):
    def test_freecads_macro_folder_and_its_files(self):
        other = os.path.join(self.tmp.name, "MyMacros")
        os.makedirs(other)
        write(other, "Bracket.FCMacro", '__Comment__ = "Makes a bracket"\nx = 1\n')
        write(other, "helper.py", "# A helper module\n")
        write(other, "notes.txt", "not a macro")
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(macro_path=other)}):
            d, rows = macros.listing()
        self.assertEqual(d, other)  # Preferences ▸ Macro ▸ MacroPath, as FreeCAD's dialog lists
        self.assertEqual([(r["name"], r["state"], r.get("about")) for r in rows],
                         [("Bracket", "no", "Makes a bracket"), ("helper.py", "no", "A helper module")])

    def test_names_and_paths(self):
        self.assertTrue(macros.macro_name_ok("helper.py"))
        self.assertFalse(macros.macro_name_ok("../x.py"))
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad()}):
            self.assertEqual(macros.macro_path("Box"), os.path.join(self.mdir, "Box.FCMacro"))
            self.assertEqual(macros.macro_path("helper.py"), os.path.join(self.mdir, "helper.py"))

    def test_agent_link_macros_told_apart(self):
        self.assertTrue(macros.uses_agentlink("import agentlink\nagentlink.run('pd_pad', {})\n"))
        self.assertFalse(macros.uses_agentlink("import FreeCAD\nFreeCAD.newDocument()\n"))


class RunFile(Home):
    def test_as_freecad_runs_a_macro(self):
        write(self.mdir, "mymod.py", "VALUE = 42\n")
        p = write(self.mdir, "Probe.FCMacro",
                  "import mymod\nimport sys\nRESULT.update(name=__name__, file=__file__, value=mymod.VALUE)\n")
        seen = {}
        before = list(sys.path)
        with mock.patch.dict(sys.modules, {"__main__": types.SimpleNamespace(RESULT=seen)}):
            sys.modules.pop("mymod", None)
            macros.run_file(open(p).read(), p)
        sys.modules.pop("mymod", None)
        self.assertEqual(seen, {"name": "__main__", "file": p, "value": 42})
        self.assertEqual(sys.path, before)  # the folder taken off again


class Run(Home):
    def test_only_once_approved_then_as_freecad_does(self):
        p = write(self.mdir, "Mark.FCMacro", "import FreeCAD\nFreeCAD.ran = __name__\n")
        fc = self.freecad(None)
        with mock.patch.dict(sys.modules, {"FreeCAD": fc, **person()}):
            ok, r = local.run("macro_run", {"name": "Mark"})
            self.assertEqual((ok, r["error"]["code"]), (False, "not_allowed"))
            ok, r = local.run("macro_approve", {"name": "Mark"})
            self.assertTrue(ok, r)
            ok, r = local.run("macro_run", {"name": "Mark"})
            self.assertTrue(ok, r)
        self.assertEqual(fc.ran, "__main__")
        self.assertEqual(r["ran"], "Mark")
        self.assertNotIn("checkpoint", r)  # no document open: nothing to go back to
        with open(p, "a") as f:
            f.write("x = 1\n")
        with mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            ok, r = local.run("macro_run", {"name": "Mark"})
        self.assertEqual((ok, r["error"]["code"]), (False, "not_allowed"))  # changed: approve again

    def test_the_person_approves_never_the_agent(self):
        # Red team, 2026-11-18: the typed words are no OK (an agent types
        # them); only the press in the window's dialog approves.
        write(self.mdir, "Mark.FCMacro", "x = 1\n")
        seen = []
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None), **person(press=False, seen=seen)}):
            ok, r = local.run("macro_approve", {"name": "Mark"})
            self.assertTrue(ok, r)
            self.assertTrue(r["pending"])
            self.assertFalse(r["approved"])
            ok, r = local.run("macro_run", {"name": "Mark"})
        self.assertEqual((ok, r["error"]["code"]), (False, "not_allowed"))
        self.assertEqual(seen[0]["kind"], "macro")
        self.assertEqual(seen[0]["sha"], macros.sha256_file(os.path.join(self.mdir, "Mark.FCMacro")))

    def test_the_client_prompt_shows_source_version_and_author(self):
        # The owner, 18 Nov 2026: the approval is approve_code; its arguments
        # (what the client shows the person) name source, version, author.
        p = write(self.mdir, "Mark.FCMacro", "__Author__ = 'Pat'\nx = 1\n")
        from safetynet import handlers

        seen = []

        def person_ok(kind, name, title, lines, sha=None, on_ok=None, shown=None):
            seen.append(shown)
            return {"pending": True, "approve": {"tool": "approve_code", "arguments": {"kind": kind, "id": name}}, "next": "call approve_code"}

        handlers.PERSON_OK = person_ok
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None)}):
            ok, r = local.run("macro_approve", {"name": "Mark"})
        self.assertTrue(ok, r)
        self.assertEqual(r["approve"]["tool"], "approve_code")
        self.assertEqual(seen[0], {"source": p, "version": "sha256 " + macros.sha256_file(p), "author": "Pat"})

    def test_without_the_window_ok_nothing_is_approved(self):
        write(self.mdir, "Mark.FCMacro", "x = 1\n")
        from safetynet import handlers

        handlers.PERSON_OK = None  # an older Agent Link: no OK in the window
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None)}):
            ok, r = local.run("macro_approve", {"name": "Mark"})
        self.assertEqual((ok, r["error"]["code"]), (False, "unavailable"))

    def test_a_file_changed_before_the_press_is_not_approved(self):
        p = write(self.mdir, "Mark.FCMacro", "x = 1\n")
        from safetynet import handlers

        calls = []
        handlers.PERSON_OK = lambda *a, **k: (calls.append((a, k)), {"pending": True})[1]
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None)}):
            local.run("macro_approve", {"name": "Mark"})
            with open(p, "a") as f:
                f.write("import os\n")
            calls[0][0][5]()  # the person presses now: the file is not the one shown
            ok, r = local.run("macro_run", {"name": "Mark"})
        self.assertEqual((ok, r["error"]["code"]), (False, "not_allowed"))

    def test_a_label_cannot_add_code_to_a_saved_macro(self):
        text = macros.macro_text("M", [{"tool": "pd_pad", "args": {}}], {}, ["Makes: Box\nimport os; os.system('x')\r# in Part\u2028y"])
        import ast

        tree = ast.parse(text)
        names = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([a.name for n in names for a in n.names], ["agentlink"])

    def test_checkpoint_before_with_a_document_open(self):
        class Doc(FakeDoc):
            UndoCount = 0

            def saveCopy(self, f):
                with open(f, "wb") as fh:
                    fh.write(b"doc")

        doc = Doc("Part")
        write(self.mdir, "Mark.FCMacro", "x = 1\n")
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(doc), **person()}):
            local.run("macro_approve", {"name": "Mark"})
            ok, r = local.run("macro_run", {"name": "Mark"})
        self.assertTrue(ok, r)
        self.assertEqual(r["checkpoint"], "cp1")
        from safetynet import checkpoints

        self.assertEqual(checkpoints.cp_index("Part")[0]["name"], "before macro Mark")

    def test_agent_link_macro_needs_agent_link(self):
        write(self.mdir, "Calls.FCMacro", "import agentlink\nagentlink.run('pd_pad', {})\n")
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None), **person()}):
            local.run("macro_approve", {"name": "Calls"})
            ok, r = local.run("macro_run", {"name": "Calls"})
        self.assertEqual((ok, r["error"]["code"]), (False, "invalid_state"))
        self.assertIn("Agent Link", r["error"]["message"])

    def test_a_failure_says_so(self):
        write(self.mdir, "Bad.FCMacro", "raise RuntimeError('boom')\n")
        with mock.patch.dict(sys.modules, {"FreeCAD": self.freecad(None), **person()}):
            local.run("macro_approve", {"name": "Bad"})
            ok, r = local.run("macro_run", {"name": "Bad"})
        self.assertEqual((ok, r["error"]["code"]), (False, "failed"))
        self.assertIn("boom", r["error"]["message"])


class Panel(unittest.TestCase):
    def test_run_alone_and_the_macro_dialog_link(self):
        from safetynet import panel

        self.assertEqual(panel.buttons_for("macro", False), {"Approve Macro", "Run Macro"})
        with gui_stubs() as g:
            ran = []
            g.runCommand = lambda *a: ran.append(a)
            w = panel.widget(lambda t, a: (True, {}), hosted=False)
            self.assertIn("linkActivated.connect", [c[0] for c in w.macro_link.calls])
            panel.open_macro_dialog()
        self.assertEqual(ran, [("Std_DlgMacroExecute", 0)])


if __name__ == "__main__":
    unittest.main()
