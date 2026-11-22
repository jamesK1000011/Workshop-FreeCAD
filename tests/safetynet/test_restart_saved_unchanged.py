# SPDX-License-Identifier: LGPL-2.1-or-later
# After a watchdog or crash restart a person's saved, unchanged document
# comes back as itself from its own file, once — never as a "(recovered …)"
# copy — and copies SafetyNet opens or renames are marked unchanged, so two
# restarts never make a copy of a copy. hidden.json's modified, headless,
# comes from the changes calls made, not FreeCAD 1.1's touched-on-open.
# Stand-ins for FreeCAD.
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

from safetynet import autosave, recovery  # noqa: E402
from test_recover_only_open import Doc, FakeFreeCAD, put  # noqa: E402


class OpensTouched(FakeFreeCAD):
    """FreeCAD 1.1: a document reads touched as soon as it is opened."""

    def openDocument(self, f):
        d = super().openDocument(f)
        d.modified = True
        return d


class GuiDoc:
    def __init__(self):
        self.Modified = True


class SavedUnchanged(unittest.TestCase):
    def setUp(self):
        recovery._CHANGED.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self._was = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = os.path.join(self.tmp.name, "home")
        self.cache = os.path.join(self.tmp.name, "cache")
        os.makedirs(self.cache)
        self.now = time.time()
        self.file = put(os.path.join(self.tmp.name, "work", "Bracket.FCStd"), self.now - 100)

    def tearDown(self):
        if self._was is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._was
        self.tmp.cleanup()

    def autosave(self, doc, t):
        return put(os.path.join(autosave.autosave_dir(doc), f"{int(t)}.FCStd"), t)

    def run_fc(self, fc, fn):
        with mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            return fn()

    def hidden(self, fc):
        self.run_fc(fc, recovery.write_hidden)
        with open(recovery.path("hidden.json")) as f:
            return json.load(f)["docs"]

    def test_restart_reopens_a_saved_unchanged_document_once_as_itself(self):
        self.autosave("Bracket", self.now - 200)  # older than the file: nothing more in it
        fc = OpensTouched([], self.cache)
        docs = [{"name": "Bracket", "label": "Bracket", "file": self.file, "modified": False}]
        reopened = []
        rec, failed = self.run_fc(fc, lambda: recovery.recover_docs(docs, since=self.now, reopened=reopened))
        self.assertEqual((rec, failed), ([], []))
        self.assertEqual(fc.opened, [self.file])
        self.assertEqual(len(reopened), 1)
        self.assertNotIn("recovered", reopened[0]["label"])
        nd = fc.docs[reopened[0]["document"]]
        self.assertFalse(nd.modified)  # settled: the open's touch is no change
        self.assertNotIn(recovery.RECOVERED_FOR, nd.Meta)
        # Asked again (or after Agent Link's restart opened it): not opened twice.
        again = []
        rec, failed = self.run_fc(fc, lambda: recovery.recover_docs(docs, since=self.now, reopened=again))
        self.assertEqual((rec, failed, fc.opened), ([], [], [self.file]))
        self.assertTrue(again[0]["already"])

    def test_already_open_from_agent_link_restart_is_left(self):
        fc = FakeFreeCAD([Doc("Bracket", "Bracket", self.file)], self.cache)
        reopened = []
        rec, _ = self.run_fc(fc, lambda: recovery.recover_docs([{"name": "Bracket", "label": "Bracket", "file": self.file}], since=self.now, reopened=reopened))
        self.assertEqual((rec, fc.opened), ([], []))
        self.assertEqual(len(reopened), 1)

    def test_a_copy_newer_than_the_file_is_recovered(self):
        self.autosave("Bracket", self.now - 10)  # written inside the call that hung
        fc = FakeFreeCAD([], self.cache)
        reopened = []
        rec, _ = self.run_fc(fc, lambda: recovery.recover_docs([{"name": "Bracket", "label": "Bracket", "file": self.file, "modified": False}], since=self.now, reopened=reopened))
        # Its own file opens too, beside the copy (live, 22 Nov: the original seemed gone).
        self.assertEqual([r["why"] for r in reopened], [recovery.BESIDE_COPY])
        self.assertEqual(len(rec), 1)
        self.assertTrue(rec[0]["as"].startswith("Bracket (recovered "))
        # The copy is beside the file, so an assembly's relative links still resolve.
        copy_file = fc.docs[rec[0]["document"]].FileName
        self.assertEqual(os.path.dirname(copy_file), os.path.dirname(self.file))
        self.assertIn(recovery.BESIDE_MARK, os.path.basename(copy_file))
        self.assertTrue(recovery.from_copy_folder(copy_file))

    def test_a_missing_file_comes_back_from_its_copy(self):
        os.remove(self.file)
        self.autosave("Bracket", self.now - 200)
        fc = FakeFreeCAD([], self.cache)
        rec, _ = self.run_fc(fc, lambda: recovery.recover_docs([{"name": "Bracket", "label": "Bracket", "file": self.file}], since=self.now, reopened=[]))
        self.assertEqual(len(rec), 1)

    def test_two_restarts_make_no_copy_of_a_copy(self):
        # Restart 1: Lid had unsaved changes, Bracket was saved and unchanged.
        lid = put(os.path.join(self.tmp.name, "work", "Lid.FCStd"), self.now - 500)
        self.autosave("Lid", self.now - 30)
        fc = OpensTouched([], self.cache)
        docs = [{"name": "Bracket", "label": "Bracket", "file": self.file, "modified": False},
                {"name": "Lid", "label": "Lid", "file": lid, "modified": True}]
        reopened = []
        rec, failed = self.run_fc(fc, lambda: recovery.recover_docs(docs, since=self.now, reopened=reopened))
        self.assertEqual([r["label"] for r in rec], ["Lid"])
        self.assertEqual([r["label"] for r in reopened], ["Bracket", "Lid"])  # Lid's own file beside its copy
        copy = fc.docs[rec[0]["document"]]
        self.assertFalse(copy.modified)  # relabel, recompute and record settled
        # What the restarted FreeCAD holds, as the next restart reads it.
        held = self.hidden(fc)
        self.assertEqual({d["label"]: d["modified"] for d in held}, {"Bracket": False, "Lid": False, copy.Label: False})
        # Restart 2: from that list; nothing changed in between.
        later = time.time() + 5
        fc2 = OpensTouched([], self.cache)
        reopened = []
        rec, failed = self.run_fc(fc2, lambda: recovery.recover_docs(held, since=later, reopened=reopened))
        self.assertEqual(rec, [])
        self.assertEqual(sorted(fc2.opened), sorted([self.file, lid]))  # Bracket and Lid as themselves, once
        # The unchanged copy is not recovered again (with its original open
        # beside it, it is dropped as one of that original's); its file stays
        # beside the original's.
        self.assertTrue(all(f.get("notAgain") for f in failed))
        self.assertFalse(any("(recovered" in d.Label for d in fc2.docs.values()))

    def test_hidden_modified_headless_is_the_calls_changes(self):
        d = Doc("Bracket", "Bracket", self.file)
        d.modified = True  # touched by opening it in FreeCAD 1.1
        fc = FakeFreeCAD([d], self.cache)
        self.assertFalse(self.hidden(fc)[0]["modified"])
        recovery.note_change(types.SimpleNamespace(doc=d))
        self.assertTrue(self.hidden(fc)[0]["modified"])
        t = time.time() + 2  # saved after the change
        os.utime(self.file, (t, t))
        self.assertFalse(self.hidden(fc)[0]["modified"])
        # never saved: touched is all there is
        n = Doc("Unnamed", "Unnamed", "", modified=True)
        self.assertTrue(self.hidden(FakeFreeCAD([n], self.cache))[0]["modified"])

    def test_tidy_rename_leaves_an_unchanged_copy_unchanged(self):
        f = put(os.path.join(self.tmp.name, recovery.TMP_PREFIX + "l", "Lid_recovered.FCStd"), self.now - 30)
        c = Doc("Lid_recovered", "Lid (recovered 08:00) (recovered 08:30)", f)
        self.run_fc(FakeFreeCAD([c], self.cache), recovery.tidy)
        self.assertEqual(c.Label, "Lid (recovered 08:30)")
        self.assertEqual(c.purged, 1)

    def test_in_the_window_open_copy_clears_the_modified_mark(self):
        src = self.autosave("Bracket", self.now - 30)
        fc = FakeFreeCAD([], self.cache)
        fc.GuiUp = True
        guis = {}
        gui = types.ModuleType("FreeCADGui")
        gui.getDocument = lambda n: guis.setdefault(n, GuiDoc())
        with mock.patch.dict(sys.modules, {"FreeCAD": fc, "FreeCADGui": gui}):
            nd = recovery.open_copy(src, "Bracket", "Bracket", self.now - 30)
            self.assertFalse(guis[nd.Name].Modified)
            self.assertFalse(recovery._changed(nd))


if __name__ == "__main__":
    unittest.main()
