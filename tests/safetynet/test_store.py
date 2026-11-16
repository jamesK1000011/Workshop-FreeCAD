# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's own modules without FreeCAD or Agent Link: what is kept, what
# is due, what is found; and that they import nothing of Agent Link.
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from safetynet import autosave, checkpoints, files, macros, recovery, settings  # noqa: E402


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._was = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = self.tmp.name

    def tearDown(self):
        if self._was is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._was
        self.tmp.cleanup()


class Checkpoints(Home):
    def test_cap(self):
        self.assertEqual(checkpoints.cap_bytes(10 * 1024 ** 3), 500 * files.MB)
        self.assertEqual(checkpoints.cap_bytes(100 * 1024 ** 3), int(0.02 * 100 * 1024 ** 3))
        self.assertEqual(checkpoints.cap_bytes(100 * 1024 ** 3, 50), 50 * files.MB)

    def test_prune_keeps_named_and_last_ten(self):
        es = [{"n": i, "name": "datum" if i == 1 else None, "bytes": 1} for i in range(1, 16)]
        kept, dropped = checkpoints.cp_prune(es, cap=10 ** 9)
        self.assertEqual([e["n"] for e in kept], [1] + list(range(6, 16)))
        self.assertEqual(len(dropped), 4)
        # over the cap: the oldest unnamed go, the named one and the newest stay
        kept, _ = checkpoints.cp_prune(es, cap=3)
        self.assertIn(1, [e["n"] for e in kept])
        self.assertIn(15, [e["n"] for e in kept])
        self.assertLessEqual(sum(e["bytes"] for e in kept), 3)

    def test_automatic_ones_do_not_pile_up(self):
        es = [{"n": i, "name": f"before macro {i}", "auto": True, "bytes": 1} for i in range(1, 30)]
        kept, dropped = checkpoints.cp_prune(es, cap=10 ** 9)
        self.assertEqual(len(kept), checkpoints.KEEP_UNNAMED)
        self.assertEqual(len(dropped), 29 - checkpoints.KEEP_UNNAMED)

    def test_add_find_and_files(self):
        e = checkpoints.cp_new("My Doc/1", name="before fillet", step=4, undo=3, tx=7)
        os.makedirs(os.path.dirname(e["file"]), exist_ok=True)
        open(e["file"], "wb").write(b"x" * 10)
        checkpoints.cp_add("My Doc/1", e, cap=10 ** 9)
        self.assertEqual(checkpoints.cp_find("My Doc/1", "before fillet")["id"], "cp1")
        self.assertEqual(checkpoints.cp_find("My Doc/1", "cp1")["bytes"], 10)
        self.assertIn("My_Doc_1", e["file"])
        for i in range(12):
            x = checkpoints.cp_new("My Doc/1", step=i)
            open(x["file"], "wb").write(b"y")
            checkpoints.cp_add("My Doc/1", x, cap=10 ** 9)
        names = [x["id"] for x in checkpoints.cp_index("My Doc/1")]
        self.assertEqual(len(names), 11)
        self.assertIn("cp1", names)
        self.assertEqual(len([f for f in os.listdir(checkpoints.cp_dir("My Doc/1")) if f.endswith(".FCStd")]), 11)

    def test_who_took_it_is_written_with_it(self):
        """A checkpoint says who took it: the person (SafetyNet's own
        commands and dock) or an agent's call; one from before says neither
        and recovery passes on what it has."""
        import types

        from safetynet import local

        self.assertEqual(checkpoints.who(local.LocalSession()), "person")
        self.assertEqual(checkpoints.who(types.SimpleNamespace()), "agent")  # Agent Link's session
        for by in ("person", "agent", None):
            e = checkpoints.cp_new("Doc", by=by)
            os.makedirs(os.path.dirname(e["file"]), exist_ok=True)
            with open(e["file"], "wb") as f:
                f.write(b"x")
            checkpoints.cp_add("Doc", e, cap=10 ** 9)
        self.assertEqual([x.get("by") for x in checkpoints.cp_index("Doc")], ["person", "agent", None])
        self.assertNotIn("by", checkpoints.cp_index("Doc")[2])
        srcs = recovery.recovery_sources("Doc")
        self.assertEqual(sorted(str(x.get("by")) for x in srcs), ["None", "agent", "person"])

    def test_undo_reach(self):
        e = {"tx": 5, "undo": 5}
        self.assertTrue(checkpoints.can_undo_back(e, 8, 8))
        self.assertFalse(checkpoints.can_undo_back(e, 30, 20))  # fell off the 20-step stack
        self.assertFalse(checkpoints.can_undo_back(e, 8, 6))  # something else moved the stack
        self.assertTrue(checkpoints.can_undo_back(e, 5, 0))


class AutoSave(Home):
    def test_due(self):
        now = time.time()
        self.assertFalse(autosave.autosave_due(now - 10, 0, now, 3))
        self.assertTrue(autosave.autosave_due(now - 400, 0, now, 1))
        self.assertTrue(autosave.autosave_due(now - 10, 0, now, 10))
        self.assertFalse(autosave.autosave_due(now - 400, 5, now, 5))  # nothing changed

    def test_prune_and_recovery_order(self):
        d = autosave.autosave_dir("Doc")
        os.makedirs(d)
        for i in range(7):
            p = os.path.join(d, f"2026111{i}-000000.FCStd")
            open(p, "w").write("x")
            os.utime(p, (1000 + i, 1000 + i))
        self.assertEqual(len(autosave.autosave_prune("Doc")), 2)
        fc = os.path.join(self.tmp.name, "fc.fcstd")
        open(fc, "w").write("x")
        src = recovery.recovery_sources("Doc", [(fc, 5000)])
        self.assertEqual(src[0]["source"], "freecad")
        self.assertEqual(len(src), 6)

    def test_freecad_recovery_scan(self):
        root = os.path.join(self.tmp.name, "cache")
        d = os.path.join(root, "FreeCAD_Doc_x_1")
        os.makedirs(d)
        open(os.path.join(d, "fc_recovery_file.fcstd"), "w").write("x")
        open(os.path.join(d, "fc_recovery_file.xml"), "w").write("<AutoRecovery><Label>Bracket</Label></AutoRecovery>")
        self.assertEqual(recovery.freecad_recovery_files([root], "Bracket")[0][2], "Bracket")
        self.assertEqual(recovery.freecad_recovery_files([root], "Other"), [])

    def test_saving_flag(self):
        self.assertFalse(autosave.saving())
        autosave.set_saving(True)
        self.assertTrue(autosave.saving())
        autosave.set_saving(False)
        self.assertFalse(autosave.saving())




class Settings(Home):
    def test_snapshot_log_rollback(self):
        cfg = os.path.join(self.tmp.name, "user.cfg")
        open(cfg, "w").write("<cfg>1</cfg>")
        snap = settings.settings_snapshot(cfg)
        settings.settings_log({"tool": "pref_set", "path": "View", "name": "Gradient", "from": True, "to": False, "snapshot": snap})
        h = settings.settings_history()
        self.assertEqual(h[0]["change"], 1)
        self.assertEqual(settings.settings_snapshot_for(1), snap)
        self.assertEqual(open(settings.settings_snapshot_for(os.path.basename(snap)[:8])).read(), "<cfg>1</cfg>")
        for _ in range(25):
            settings.settings_snapshot(cfg)
        self.assertEqual(len(os.listdir(os.path.join(self.tmp.name, "settings"))), settings.SETTINGS_KEEP)


class Macros(Home):
    def test_text_names_the_sizes(self):
        calls = [{"tool": "pd_pad", "args": {"sketch": "S", "length": 60}}, {"tool": "pd_thickness", "args": {"thickness": 2.0, "faces": ["top"]}}]
        t = macros.macro_text("Box", calls, {"wall": 2.0, "length": 60}, ["makes a box"])
        self.assertIn("WALL = 2.0", t)
        self.assertIn("'length': LENGTH", t)
        self.assertIn("'thickness': WALL", t)
        consts, cs = macros.macro_calls(t)
        self.assertEqual(consts, {"WALL": 2.0, "LENGTH": 60})
        self.assertEqual(len(cs), 2)
        compile(t, "m", "exec")

    def test_approval_follows_the_code(self):
        p = os.path.join(self.tmp.name, "Box.FCMacro")
        open(p, "w").write("x = 1\n")
        self.assertEqual(macros.approval_state("Box", p), "no")
        macros.approve("Box", p)
        self.assertEqual(macros.approval_state("Box", p), "approved")
        open(p, "w").write("x = 2\n")
        self.assertEqual(macros.approval_state("Box", p), "changed")
        macros.unapprove("Box")
        self.assertEqual(macros.approval_state("Box", p), "no")

    def test_names(self):
        self.assertTrue(macros.macro_name_ok("Bracket v2"))
        self.assertFalse(macros.macro_name_ok("../evil"))


class Reopen(Home):
    def test_taken_once_and_stale_dropped(self):
        files._save(recovery.reopen_file(), {"t": time.time(), "docs": [{"name": "A", "copy": "/x"}]})
        self.assertEqual([c["name"] for c in recovery.reopen_pending()], ["A"])
        self.assertEqual(recovery.reopen_pending(), [])
        files._save(recovery.reopen_file(), {"t": time.time() - 3600, "docs": [{"name": "A"}]})
        self.assertEqual(recovery.reopen_pending(), [])


class RecoveredNames(unittest.TestCase):
    """A recovered copy is named after its original once, one per original."""
    TMP = os.path.join(tempfile.gettempdir(), recovery.TMP_PREFIX + "abc", "AgentLink_recovered.FCStd")

    def test_original_name_and_label(self):
        self.assertEqual(recovery.original_name("AgentLink_recovered_recovered1_recovered_recovered"), "AgentLink")
        self.assertEqual(recovery.original_name("AgentLink"), "AgentLink")
        self.assertEqual(recovery.original_label("AgentLink_recovered_recovered1_recovered_recovered"), "AgentLink")
        self.assertEqual(recovery.original_label("Bracket (recovered 10:02) (recovered 10:05)"), "Bracket")
        self.assertEqual(recovery.original_label("Bracket_recovered (recovered 10:02)"), "Bracket")
        self.assertEqual(recovery.original_label("Bracket (v2)"), "Bracket (v2)")
        self.assertEqual(recovery.copy_label("Bracket (recovered 10:02) (recovered 10:05)"), "Bracket (recovered 10:05)")
        self.assertEqual(recovery.copy_label("Bracket_recovered1"), "Bracket (recovered)")

    def test_is_recovered(self):
        self.assertTrue(recovery.is_recovered({"name": "X", "file": self.TMP}))
        self.assertTrue(recovery.is_recovered({"name": "X", "recovered": True}))
        self.assertTrue(recovery.is_recovered({"name": "X_recovered", "file": ""}))
        # a person's own saved file is theirs, whatever its name
        self.assertFalse(recovery.is_recovered({"name": "X_recovered", "file": "/work/X_recovered.FCStd"}))
        self.assertFalse(recovery.is_recovered({"name": "X", "file": "/work/X.FCStd"}))

    def test_dedupe_by_original(self):
        docs = [{"name": "AgentLink_recovered", "label": "AgentLink (recovered 10:00)", "file": self.TMP},
                {"name": "AgentLink", "label": "AgentLink", "file": "/work/AgentLink.FCStd"},
                {"name": "AgentLink_recovered1", "label": "AgentLink (recovered 10:05)", "file": "", "recovered": True, "original": "/work/AgentLink.FCStd"},
                {"name": "Unnamed_recovered1", "label": "Unnamed (recovered 1:00)", "file": ""},
                {"name": "Unnamed_recovered_recovered", "label": "Unnamed_recovered (recovered 2:00)", "file": ""},
                {"name": "Bracket", "label": "Bracket", "file": ""}]
        out = recovery.dedupe(docs)
        self.assertEqual([d["name"] for d in out], ["AgentLink", "Unnamed_recovered1", "Bracket"])
        self.assertEqual([(d["base"], d["baseLabel"]) for d in out], [("AgentLink", "AgentLink"), ("Unnamed", "Unnamed"), ("Bracket", "Bracket")])

    def test_a_copy_alone_is_recovered_for_its_original_file(self):
        out = recovery.dedupe([{"name": "AgentLink_recovered", "label": "AgentLink (recovered 10:00)", "file": self.TMP,
                                "recovered": True, "original": "/work/AgentLink.FCStd"}])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["base"], out[0]["baseLabel"], out[0]["file"]), ("AgentLink", "AgentLink", "/work/AgentLink.FCStd"))

    def test_reopen_list_skips_copies_of_open_originals(self):
        others = [{"name": "AgentLink", "label": "AgentLink", "file": "/work/AgentLink.FCStd"}]
        kept = [{"name": "AgentLink_recovered", "label": "AgentLink (recovered 10:00)", "file": self.TMP, "copy": "/c/1"},
                {"name": "Bracket", "label": "Bracket", "file": "/work/Bracket.FCStd", "copy": "/c/2"},
                {"name": "Bracket_recovered", "label": "Bracket (recovered 9:00)", "file": "", "copy": "/c/3"}]
        self.assertEqual([e["copy"] for e in recovery.reopen_list(others, kept)], ["/c/2"])

    def test_recent_files_lose_the_copies(self):
        self.assertEqual(recovery.recent_without_copies(["/work/A.FCStd", self.TMP, ""]), ["/work/A.FCStd"])

    def test_forget_recent_rewrites_the_list(self):
        import types
        from unittest import mock

        vals = {"MRU0": self.TMP, "MRU1": "/work/A.FCStd", "MRU2": self.TMP.replace("abc", "def"), "MRU3": "/work/B.FCStd"}
        grp = types.SimpleNamespace(GetInt=lambda n, d=0: 4, GetString=lambda n, d="": vals.get(n, d),
                                    SetString=lambda n, v: vals.__setitem__(n, v), RemString=lambda n: vals.pop(n, None))
        fc = types.SimpleNamespace(ParamGet=lambda *_: grp)
        with mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            self.assertEqual(recovery.forget_recent(), 2)
            self.assertEqual(recovery.forget_recent(), 0)
        self.assertEqual(vals, {"MRU0": "/work/A.FCStd", "MRU1": "/work/B.FCStd"})

    def test_listing_newest_first(self):
        rows = recovery.newest_first([{"document": "A", "t": 1}, {"document": "B", "t": 3}, {"document": "C", "t": 2}])
        self.assertEqual([r["document"] for r in rows], ["B", "C", "A"])
        self.assertNotIn("t", rows[0])


class EmptyCachedShapes(unittest.TestCase):
    """FreeCAD's autosave writes some cached shapes as empty blobs, which
    reading a copy reports in red: the copy's objects with them rebuilt by a
    recompute (in memory only), and one plain line saying why."""

    def fcstd(self, folder):
        import zipfile

        f = os.path.join(folder, "copy.FCStd")
        with zipfile.ZipFile(f, "w") as z:
            z.writestr("Document.xml", "<Document/>")
            z.writestr("Sketch.InternalShape.bin", b"")
            z.writestr("Pad.SuppressedShape.bin", b"")
            z.writestr("Pad.Shape.brp", b"shape")
            z.writestr("Box.Shape.bin", b"xx")
        return f

    def test_found_from_the_zip_index(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(recovery.empty_shapes(self.fcstd(d)), {"Sketch", "Pad"})
            self.assertEqual(recovery.empty_shapes(os.path.join(d, "none.FCStd")), set())

    def test_opening_a_copy_rebuilds_them_and_says_so(self):
        import types
        from unittest import mock

        printed, log = [], []

        class Obj:
            def __init__(self, n):
                self.n = n

            def touch(self):
                log.append(("touch", self.n))

        class Doc:
            Name, Label, Meta = "WindowTest_recovered", "", {}

            def getObject(self, n):
                return Obj(n) if n in ("Sketch", "Pad") else None

            def recompute(self):
                log.append(("recompute",))

            def save(self):  # never: the copy is not written
                raise AssertionError("saved")

        opened = []
        fc = types.SimpleNamespace(openDocument=lambda f: opened.append(f) or Doc(),
                                   Console=types.SimpleNamespace(PrintMessage=printed.append),
                                   ParamGet=lambda *_: types.SimpleNamespace(GetInt=lambda n, d=0: 4, GetString=lambda n, d="": d))
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            src = self.fcstd(d)
            with open(src, "rb") as f:
                before = f.read()
            nd = recovery.open_copy(src, "WindowTest", "WindowTest", time.time())
            with open(src, "rb") as f:
                self.assertEqual(f.read(), before)  # the source untouched
        self.assertEqual(printed, ["SafetyNet: FreeCAD's autosave left some cached shapes empty; they are rebuilt on recompute.\n"])
        self.assertEqual(log, [("touch", "Pad"), ("touch", "Sketch"), ("recompute",)])
        self.assertTrue(recovery.from_copy_folder(opened[0]))
        self.assertTrue(nd.Label.startswith("WindowTest (recovered "))


class SettingsEvents(Home):
    def test_changed_logs_with_the_snapshot_taken_before(self):
        settings._pending.update({"snapshot": "/snap.cfg", "tool": "pref_set", "t": time.time()})
        e = settings.changed("View", "Gradient", True, False, tool="pref_set", restart=False)
        self.assertEqual(e["snapshot"], "/snap.cfg")
        row = settings.history_rows(1)[0]
        self.assertEqual((row["change"], row["tool"], row["name"], row["to"]), (1, "pref_set", "Gradient", False))


class NoAgent(unittest.TestCase):
    def test_modules_import_nothing_of_agent_link(self):
        code = ("import sys; sys.path.insert(0, %r); import safetynet, safetynet.files, safetynet.checkpoints, safetynet.autosave, "
                "safetynet.recovery, safetynet.settings, safetynet.macros, safetynet.refusal; "
                "print(sorted(m for m in sys.modules if m.startswith('agentlink')))") % ROOT
        out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, "[]")

    def test_helpers_match_agent_link_where_it_is_beside(self):
        try:
            from agentlink import keep
        except ImportError:
            self.skipTest("Agent Link is not beside it")
        self.assertEqual(files.home(), keep.home())


if __name__ == "__main__":
    unittest.main()
