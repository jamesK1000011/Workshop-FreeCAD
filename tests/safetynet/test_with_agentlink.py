# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet on a real FreeCAD with Agent Link beside it: checkpoints as
# saved copies, auto-save copies, recovery beside the file, the settings log
# and rollback, macros, and a checkpoint before a heavy change. Skipped where
# FreeCAD or Agent Link cannot be imported (the run on its own).
import json
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401
    import Part  # noqa: F401
    import agentlink.tools  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False

_HOME = tempfile.mkdtemp(prefix="safetynet-home-")


@unittest.skipUnless(HAVE, "FreeCAD and Agent Link are not both importable here")
class WithAgentLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._was_home = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = _HOME
        from agentlink.tools import Session, build_server

        cls.dir = tempfile.mkdtemp()
        cls.session = Session(out_dir=cls.dir)
        cls.server = build_server(cls.session, lean=False)

    @classmethod
    def tearDownClass(cls):
        try:
            FreeCAD.closeDocument(cls.session.doc.Name)
        except Exception:
            pass
        if cls._was_home is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = cls._was_home

    def call(self, name, args=None):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})["result"]
        return r.get("isError", False), json.loads(r["content"][0]["text"])

    def ok(self, name, args=None):
        err, out = self.call(name, args)
        self.assertFalse(err, f"{name}: {out}")
        return out

    def refused(self, name, args=None):
        err, out = self.call(name, args)
        self.assertTrue(err, f"{name} should be refused: {out}")
        return out["error"]

    def box(self, name, size):
        return self.ok("part_primitive", {"kind": "box", "size": size, "name": name})

    def vol(self, label):
        return self.session.doc.getObjectsByLabel(label)[0].Shape.Volume

    def test_0_loaded(self):
        from agentlink import hooks

        for t in ("history_checkpoint", "history_restore", "app_recover", "macro_run", "pref_history", "pref_rollback"):
            self.assertIn(t, self.server.tools)
        self.assertEqual(self.server.tools["history_checkpoint"].group, "core")
        self.assertIsNotNone(hooks.service("checkpoints"))
        self.assertIsNotNone(hooks.service("reopen"))
        self.assertIn("Session", [t["title"] for t in hooks.TABS])
        if hasattr(hooks, "TAB_WORKBENCHES"):  # only while Make is the workbench in front
            self.assertEqual(hooks.TAB_WORKBENCHES.get("Session"), {"WorkshopMakeWorkbench"})

    def test_1_checkpoint_by_undo(self):
        self.box("U a", [10, 10, 10])
        cp = self.ok("history_checkpoint", {"name": "start"})
        self.assertTrue(os.path.isfile(cp["file"]))
        self.assertTrue(cp["file"].startswith(_HOME))
        self.ok("object_set", {"object": "U a", "values": {"Length": 20}})
        self.ok("object_set", {"object": "U a", "values": {"Width": 20}})
        self.assertAlmostEqual(self.vol("U a"), 4000, places=3)
        d = self.ok("history_diff", {"since": "start"})
        self.assertTrue(d["changed"])
        r = self.ok("history_restore", {"checkpoint": "start"})
        self.assertEqual(r["how"], "undo")
        self.assertAlmostEqual(self.vol("U a"), 1000, places=3)
        self.assertIn("start", [c.get("name") for c in self.ok("history_checkpoint", {"list": True})["checkpoints"]])

    def test_2_checkpoint_past_the_undo_stack(self):
        from safetynet import checkpoints

        self.box("U b", [10, 10, 10])
        cp = self.ok("history_checkpoint", {"name": "before many"})
        limit = checkpoints.undo_limit()
        for i in range(limit + 5):
            self.ok("object_set", {"object": "U b", "values": {"Height": 11 + i}})
        name = self.session.doc.Name
        r = self.ok("history_restore", {"checkpoint": cp["checkpoint"]})
        self.assertEqual(r["how"], "file")
        self.assertEqual(self.session.doc.Name, name)
        self.assertAlmostEqual(self.vol("U b"), 1000, places=3)
        back = self.ok("history_restore", {"checkpoint": r["before"]})
        self.assertEqual(back["how"], "file")
        self.assertAlmostEqual(self.vol("U b"), 10 * 10 * (11 + limit + 4), places=3)
        # history_diff reads an old checkpoint from its saved copy
        for e in checkpoints._mine(self.session).values():
            e["session"] = 0
        idx = checkpoints.cp_index(self.session.doc.Name)
        for e in idx:
            e["session"] = 0
        checkpoints.cp_save_index(self.session.doc.Name, idx)
        d = self.ok("history_diff", {"since": cp["checkpoint"]})
        self.assertEqual(d["from"], "its saved copy")
        self.assertIn("U b", d["bodies"])

    def test_5_autosave(self):
        from safetynet import autosave

        s = self.session
        s.__dict__.setdefault("_safetynet_autosaved", {})[s.doc.Name] = (0, s.tx)
        self.box("U c", [5, 5, 5])
        files = [f for f in os.listdir(autosave.autosave_dir(s.doc.Name)) if f.endswith(".FCStd")]
        self.assertTrue(files)
        self.assertFalse(autosave.saving())

    def test_6_checkpoint_is_no_macro_call(self):
        self.box("U d", [3, 3, 3])
        n = len(self.session.calls)
        self.ok("history_checkpoint")
        self.assertEqual(len(self.session.calls), n)

    def test_7_recover_beside_the_file(self):
        from safetynet import autosave

        s = self.session
        self.box("U r", [8, 8, 8])
        path = os.path.join(self.dir, "recover_me.FCStd")
        self.ok("doc_save", {"path": path})
        # Changed after the save: a saved file with no changes since only
        # opens again from itself (recovery.saved_unchanged).
        self.box("U r2", [4, 4, 4])
        autosave.now(s)
        name, label = s.doc.Name, s.doc.Label
        listed = self.ok("app_recover")
        self.assertIn(name, [d["document"] for d in listed["documents"]])
        r = self.ok("app_recover", {"action": "auto", "documents": [{"name": name, "label": label, "file": path, "modified": True}], "since": time.time() + 120})
        rec = r["recovered"][0]
        self.assertIn("(recovered", rec["as"])
        self.assertEqual(rec["file"], path)
        self.assertIn("lostMinutes", rec)
        nd = FreeCAD.getDocument(rec["document"])
        self.assertNotEqual(os.path.abspath(nd.FileName), os.path.abspath(path))
        # The original is still open: refused before any approval is asked.
        self.assertIn("close it first", self.refused("app_recover", {"action": "accept", "document": rec["document"]})["message"])
        FreeCAD.closeDocument(name)
        # The approval is approve_file (the client's tool permission), never typed words.
        self.assertTrue(self.ok("app_recover", {"action": "accept", "document": rec["document"], "confirm": "save over recover_me.FCStd"})["pending"])
        pending = self.ok("app_recover", {"action": "accept", "document": rec["document"]})
        self.assertTrue(pending["pending"])
        self.assertEqual(pending["approve"]["tool"], "approve_file")
        self.assertEqual(pending["approve"]["arguments"]["file"], path)
        self.assertTrue(self.ok("approve_file", pending["approve"]["arguments"])["approved"])
        ok = self.ok("app_recover", {"action": "accept", "document": rec["document"]})
        self.assertEqual(ok["saved"], path)
        self.assertTrue(os.path.isfile(ok["previousFile"]))

    def test_8_settings_logged_and_snapshotted(self):
        from safetynet.files import path

        r = self.ok("pref_set", {"path": "BaseApp/Preferences/Mod/AgentLinkTest", "name": "Probe", "value": 3})
        self.assertIn("Probe", r["set"])
        h = self.ok("pref_history", {"limit": 5})["changes"]
        self.assertEqual((h[0]["tool"], h[0]["name"], h[0]["to"]), ("pref_set", "Probe", 3))
        if os.path.isfile(os.path.join(FreeCAD.getUserConfigDir(), "user.cfg")):
            self.assertTrue(os.listdir(path("settings")))
            if not os.environ.get("AGENTLINK_SUPERVISED"):
                self.assertEqual(self.refused("pref_rollback", {"to": h[0]["change"]})["code"], "unavailable")
        self.assertEqual(self.refused("pref_rollback", {"to": 99999})["code"], "not_found")

    def test_11_macros(self):
        mdir = tempfile.mkdtemp(prefix="safetynet-macros-")
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Macro").SetString("MacroPath", mdir)
        s = self.session
        self.ok("history_checkpoint", {"name": "macro start"})
        self.ok("part_primitive", {"kind": "box", "size": [60, 20, 2], "name": "M plate"})
        saved = self.ok("macro_save", {"name": "Plate test", "from": "macro start", "params": {"length": 60, "wall": 2}})
        self.assertEqual(saved["calls"], 1)
        self.assertEqual(saved["constants"], {"LENGTH": 60, "WALL": 2})
        text = open(saved["path"]).read()
        self.assertIn("[LENGTH, 20, WALL]", text)
        self.assertEqual(self.refused("macro_run", {"name": "Plate test"})["code"], "not_allowed")
        # The OK is approve_code, which the client asks the person for: the
        # call is pending and approves nothing by itself.
        p = self.ok("macro_approve", {"name": "Plate test"})
        self.assertTrue(p.get("pending"), p)
        self.assertEqual(p["approve"]["tool"], "approve_code")
        self.assertNotEqual([m["state"] for m in self.ok("macro_list")["macros"] if m["name"] == "Plate test"], ["approved"])
        from safetynet import macros as _macros

        _macros.approve("Plate test", saved["path"])  # the person's press, stood in
        self.assertEqual([m["state"] for m in self.ok("macro_list")["macros"] if m["name"] == "Plate test"], ["approved"])
        n = len(s.bodies())
        r = self.ok("macro_run", {"name": "Plate test", "params": {"LENGTH": 30}})
        self.assertEqual(r["calls"], 1)
        vols = sorted(round(o.Shape.Volume) for o in s.bodies())
        self.assertIn(1200, vols)
        self.assertEqual(len(s.bodies()), n + 1)
        n = len(s.bodies())
        e = self.refused("macro_run", {"name": "Plate test", "params": {"LENGTH": -5}})
        self.assertIn("Rolled back", e["message"])
        self.assertEqual(len(s.bodies()), n)
        self.assertIn("params", self.refused("macro_run", {"name": "Plate test", "params": {"NOPE": 1}})["message"])
        with open(saved["path"], "a") as f:
            f.write("# edited\n")
        self.assertIn("changed", self.refused("macro_run", {"name": "Plate test"})["message"])
        self.assertEqual(self.ok("macro_show", {"name": "Plate test"})["state"], "changed")
        self.ok("macro_unapprove", {"name": "Plate test"})

    def test_13_checkpoint_before_a_heavy_change(self):
        import types

        from agentlink.heavy import Gate

        from safetynet import checkpoints

        n = len(checkpoints.cp_index(self.session.doc.Name))
        os.environ["AGENTLINK_GATE"] = "1"
        try:
            Gate(self.session).before(types.SimpleNamespace(name="part_extract", changes=True), {})
        finally:
            os.environ.pop("AGENTLINK_GATE", None)
        idx = checkpoints.cp_index(self.session.doc.Name)
        self.assertEqual(len(idx), n + 1)
        self.assertEqual(idx[-1]["name"], "before part_extract")


if __name__ == "__main__":
    unittest.main()
