# SPDX-License-Identifier: LGPL-2.1-or-later
# Restart and crash recovery bring back only the documents open at the crash,
# never a "(recovered …)" copy of a copy: a recovered copy comes back only
# from changes made in it after it opened (its auto-save folder, named like
# every earlier copy, also holds theirs), one nobody changed not at all; and
# temporary recovered files older than the crash that FreeCAD opened again,
# unchanged, are closed. Stand-ins for FreeCAD.
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

from safetynet import autosave, recovery  # noqa: E402


class Doc:
    def __init__(self, name, label, file="", meta=None, modified=False):
        self.Name, self.Label, self.FileName = name, label, file
        self.Meta = dict(meta or {})
        self.modified = modified

    def isTouched(self):
        return self.modified

    def recompute(self):
        pass


class FakeFreeCAD(types.ModuleType):
    def __init__(self, docs, cache):
        super().__init__("FreeCAD")
        self.docs = {d.Name: d for d in docs}
        self.cache, self.closed, self.opened = cache, [], []
        self.GuiUp = False
        self.Console = types.SimpleNamespace(PrintMessage=lambda *_: None, PrintWarning=lambda *_: None)

    def listDocuments(self):
        return dict(self.docs)

    def closeDocument(self, n):
        self.closed.append(n)
        self.docs.pop(n, None)

    def openDocument(self, f):
        n = os.path.splitext(os.path.basename(f))[0]
        while n in self.docs:
            n += "1"
        d = Doc(n, n, f)
        self.docs[n] = d
        self.opened.append(f)
        return d

    def getDocument(self, n):
        return self.docs[n]

    def getUserCachePath(self):
        return self.cache

    def ParamGet(self, *_):
        return types.SimpleNamespace(GetInt=lambda n, d=0: 4, GetString=lambda n, d="": d, GetBool=lambda n, d=False: d)


def put(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write("x")
    os.utime(p, (t, t))
    return p


class OnlyOpenAtTheCrash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._was = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = os.path.join(self.tmp.name, "home")
        self.cache = os.path.join(self.tmp.name, "cache")
        os.makedirs(self.cache)
        self.now = time.time()
        # A temporary folder an earlier recovery opened a copy from, an hour ago.
        self.old_dir = os.path.join(self.tmp.name, recovery.TMP_PREFIX + "old")
        self.old_copy = put(os.path.join(self.old_dir, "Bracket_recovered.FCStd"), self.now - 3600)
        os.utime(self.old_dir, (self.now - 3600, self.now - 3600))

    def tearDown(self):
        if self._was is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._was
        self.tmp.cleanup()

    def autosave(self, doc, t):
        return put(os.path.join(autosave.autosave_dir(doc), f"{int(t)}.FCStd"), t)

    def run_fc(self, docs, fn):
        fc = FakeFreeCAD(docs, self.cache)
        with mock.patch.dict(sys.modules, {"FreeCAD": fc}):
            out = fn()
        return fc, out

    def test_unchanged_copy_is_not_recovered_again(self):
        # The copy's own folder holds an earlier copy's auto-save (before it opened).
        self.autosave("Bracket_recovered", self.now - 4000)
        docs = [{"name": "Bracket_recovered", "label": "Bracket (recovered 09:00)", "file": self.old_copy, "recovered": True,
                 "original": "/work/Bracket.FCStd"}]
        fc, (rec, failed) = self.run_fc([], lambda: recovery.recover_docs(docs, since=self.now))
        self.assertEqual(rec, [])
        self.assertEqual(fc.opened, [])
        self.assertTrue(failed and failed[0]["notAgain"])
        # modified false: not recovered either, even with newer copies
        self.autosave("Bracket_recovered", self.now - 60)
        fc, (rec, failed) = self.run_fc([], lambda: recovery.recover_docs([dict(docs[0], modified=False)], since=self.now))
        self.assertEqual((rec, fc.opened), ([], []))
        self.assertTrue(failed[0]["notAgain"])

    def test_changed_copy_comes_back_from_its_own_changes_once(self):
        self.autosave("Bracket_recovered", self.now - 4000)  # an earlier copy's
        mine = self.autosave("Bracket_recovered", self.now - 60)  # made in the copy after it opened
        docs = [{"name": "Bracket_recovered", "label": "Bracket (recovered 09:00)", "file": self.old_copy, "recovered": True,
                 "original": "/work/Bracket.FCStd", "modified": True}]
        fc, (rec, failed) = self.run_fc([], lambda: recovery.recover_docs(docs, since=self.now))
        self.assertEqual(failed, [])
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["file"], "/work/Bracket.FCStd")
        self.assertTrue(rec[0]["as"].startswith("Bracket (recovered "), rec[0]["as"])
        self.assertNotIn("(recovered", rec[0]["as"][len("Bracket (recovered"):])
        self.assertEqual(len(fc.opened), 1)
        # the opening time is kept with the copy, for the next crash
        meta = json.loads(fc.docs[rec[0]["document"]].Meta[recovery.RECOVERED_FOR])
        self.assertGreaterEqual(meta["opened"], self.now)
        self.assertTrue(os.path.getmtime(mine))

    def test_original_comes_back_and_stale_temp_copies_close(self):
        self.autosave("Bracket", self.now - 30)
        # FreeCAD opened the old temporary copy again on its own; nobody changed it.
        stray = Doc("Bracket_recovered", "Bracket (recovered 09:00)", self.old_copy)
        # A temporary copy changed since: kept, named once.
        kept = Doc("Lid_recovered", "Lid (recovered 08:00) (recovered 08:30)", put(os.path.join(self.tmp.name, recovery.TMP_PREFIX + "l", "Lid_recovered.FCStd"), self.now - 3000), modified=True)
        docs = [{"name": "Bracket", "label": "Bracket", "file": "/work/Bracket.FCStd"}]
        fc, (rec, failed) = self.run_fc([stray, kept], lambda: recovery.recover_docs(docs, since=self.now))
        self.assertEqual([r["label"] for r in rec], ["Bracket"])
        self.assertIn("Bracket_recovered", fc.closed)
        self.assertNotIn("Lid_recovered", fc.closed)
        self.assertEqual(kept.Label, "Lid (recovered 08:30)")

    def test_a_temp_copy_open_at_the_crash_is_not_closed_as_stale(self):
        other = Doc("Lid_recovered", "Lid (recovered 08:00)", put(os.path.join(self.tmp.name, recovery.TMP_PREFIX + "l", "Lid_recovered.FCStd"), self.now - 3000))
        fc, _ = self.run_fc([other], lambda: recovery.tidy(since=self.now, open_at=[{"name": "Lid_recovered", "file": other.FileName}]))
        self.assertEqual(fc.closed, [])
        fc, _ = self.run_fc([other], lambda: recovery.tidy(since=self.now, open_at=[]))
        self.assertEqual(fc.closed, ["Lid_recovered"])

    def test_restart_reopen_closes_old_temp_copies_reopened(self):
        copy = self.autosave("Bracket", self.now - 5)
        recovery._save(recovery.reopen_file(), {"t": self.now, "docs": [{"name": "Bracket", "label": "Bracket", "file": "", "copy": copy, "t": self.now}]})
        stray = Doc("Bracket_recovered", "Bracket (recovered 09:00)", self.old_copy)
        fc, opened = self.run_fc([stray], recovery.reopen_now)
        self.assertEqual(len(opened), 1)
        self.assertEqual(fc.closed, ["Bracket_recovered"])

    def test_freecad_recovery_files_only_the_documents_own(self):
        def rec_dir(n, label, fname, t):
            d = os.path.join(self.cache, n)
            put(os.path.join(d, "fc_recovery_file.fcstd"), t)
            if label is not None:
                with open(os.path.join(d, "fc_recovery_file.xml"), "w") as f:
                    f.write(f"<AutoRecovery><Label>{label}</Label><FileName>{fname}</FileName></AutoRecovery>")
        rec_dir("a", "Bracket", "/work/Bracket.FCStd", self.now - 10)
        rec_dir("b", "Bracket", self.old_copy, self.now - 5)  # an old copy relabelled as its original
        rec_dir("c", None, "", self.now - 1)  # no .xml: no document's
        rec_dir("d", "Bracket (recovered 09:00)", self.old_copy, self.now - 2)
        mine = recovery.freecad_recovery_files([self.cache], "Bracket")
        self.assertEqual([os.path.basename(os.path.dirname(p)) for p, _, _ in mine], ["a"])
        theirs = recovery.freecad_recovery_files([self.cache], "Bracket (recovered 09:00)")
        self.assertEqual([os.path.basename(os.path.dirname(p)) for p, _, _ in theirs], ["d"])
        self.assertEqual(len(recovery.freecad_recovery_files([self.cache])), 4)

    def test_list_offers_a_copy_only_with_its_own_changes(self):
        self.autosave("Bracket", self.now - 100)
        self.autosave("Bracket_recovered", self.now - 4000)  # an earlier copy's, before this one opened
        recovery._save(os.path.join(autosave.autosave_dir("Bracket_recovered"), "about.json"), {"label": "Bracket (recovered 09:00)", "fileName": self.old_copy})
        self.autosave("Unnamed_recovered", self.now - 50)  # no record of when it opened
        fc, rows = self.run_fc([], recovery.listing)
        self.assertEqual([r["document"] for r in rows], ["Bracket"])
        self.autosave("Bracket_recovered", self.now - 20)  # changed after it opened
        fc, rows = self.run_fc([], recovery.listing)
        self.assertEqual(sorted(r["document"] for r in rows), ["Bracket", "Bracket_recovered"])
        row = next(r for r in rows if r["document"] == "Bracket_recovered")
        self.assertEqual(len(row["copies"]), 1)

    def test_hidden_list_says_modified(self):
        d = Doc("Bracket", "Bracket", "/work/Bracket.FCStd", modified=True)
        c = Doc("Lid_recovered", "Lid (recovered 08:00)", self.old_copy.replace("Bracket", "Lid"))
        self.run_fc([d, c], recovery.write_hidden)
        with open(recovery.path("hidden.json")) as f:
            docs = {x["name"]: x for x in json.load(f)["docs"]}
        self.assertTrue(docs["Bracket"]["modified"])
        self.assertFalse(docs["Lid_recovered"]["modified"])
        self.assertTrue(docs["Lid_recovered"]["recovered"])
        self.assertAlmostEqual(docs["Lid_recovered"]["opened"], self.now - 3600, delta=2)


if __name__ == "__main__":
    unittest.main()
