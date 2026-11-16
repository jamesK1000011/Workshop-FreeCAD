# SPDX-License-Identifier: LGPL-2.1-or-later
# Recovered copies pruned without FreeCAD: what is kept (the newest of each
# document, open documents, the last crash, copies used lately, named
# checkpoints), what goes (past the count, past the age, never-saved scratch
# past a day), a dry run that changes nothing, and the move to the Trash.
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from safetynet import cleanup  # noqa: E402

DAY = 86400.0
NOW = 1_800_000_000.0


def copy(doc, days, **k):
    return {"document": doc, "path": f"/c/{doc}/{days}.FCStd", "t": NOW - days * DAY, "size": 1048576, **k}


def gone(p):
    return sorted((c["document"], round((NOW - c["t"]) / DAY, 2)) for c in p["go"])


class Rules(unittest.TestCase):
    def test_newest_three_a_document(self):
        p = cleanup.plan([copy("A", d) for d in (0.1, 0.2, 0.3, 0.4, 0.5)], now=NOW)
        self.assertEqual(gone(p), [("A", 0.4), ("A", 0.5)])
        self.assertEqual([c["why"] for c in p["keep"]][0], "newest")

    def test_none_past_a_week_but_the_newest(self):
        p = cleanup.plan([copy("A", 8), copy("A", 9), copy("B", 1), copy("B", 7.5)], now=NOW)
        self.assertEqual(gone(p), [("A", 9), ("B", 7.5)])  # A's newest stays, however old

    def test_scratch_after_a_day(self):
        cs = [copy("Unnamed", d, scratch=True) for d in (0.5, 1.5, 2)] + [copy("Saved", d) for d in (0.5, 1.5, 2)]
        p = cleanup.plan(cs, now=NOW)
        self.assertEqual(gone(p), [("Unnamed", 1.5), ("Unnamed", 2)])

    def test_kept_open_crash_used_named(self):
        cs = [copy("Open", d) for d in (1, 2, 3, 4, 10)]
        cs += [copy("C", d) for d in (1, 2, 3, 4, 10)]
        p = cleanup.plan(cs, now=NOW, open_names=["Open"], crash=["/c/C/10.FCStd"], used_paths=["/c/C/4.FCStd"])
        self.assertEqual(gone(p), [])
        why = {c["path"]: c["why"] for c in p["keep"]}
        self.assertEqual(why["/c/Open/10.FCStd"], "open")
        self.assertEqual(why["/c/C/10.FCStd"], "last crash")
        self.assertEqual(why["/c/C/4.FCStd"], "used")
        p = cleanup.plan([copy("N", d, named=(d == 20)) for d in (1, 2, 3, 20)], now=NOW)
        self.assertEqual(gone(p), [])

    def test_open_by_folder_name(self):
        p = cleanup.plan([copy("My_Doc", d) for d in (1, 2, 3, 4)], now=NOW, open_names=["My Doc"])
        self.assertEqual(gone(p), [])

    def test_settings_change_the_numbers(self):
        p = cleanup.plan([copy("A", d) for d in (0.1, 0.2, 3)], now=NOW, keep=1, max_age_days=2)
        self.assertEqual(gone(p), [("A", 0.2), ("A", 3)])


class Params:
    def __init__(self, **v):
        self.v = v

    def GetInt(self, k, d=0):
        return self.v.get(k, d)

    def GetString(self, k, d=""):
        return self.v.get(k, d)

    def SetString(self, k, v):
        self.v[k] = v


class OnDisk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.tmp.name})
        self.env.start()
        self.made = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def autosave(self, doc, days, file_name=""):
        d = os.path.join(self.tmp.name, "autosave", doc)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "about.json"), "w") as f:
            json.dump({"label": doc, "fileName": file_name}, f)
        p = os.path.join(d, f"{days}.FCStd")
        with open(p, "wb") as f:
            f.write(b"x" * 1000)
        os.utime(p, (NOW - days * DAY,) * 2)
        return p

    def checkpoint(self, doc, n, days, name=None):
        d = os.path.join(self.tmp.name, "checkpoints", doc)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{n}-cp.FCStd")
        with open(p, "wb") as f:
            f.write(b"y")
        idx = os.path.join(d, "index.json")
        es = json.load(open(idx)) if os.path.exists(idx) else []
        es.append({"id": f"cp{n}", "n": n, "name": name, "file": p, "t": NOW - days * DAY, "fileName": "/w/Box.FCStd"})
        with open(idx, "w") as f:
            json.dump(es, f)
        return p

    def tree(self):
        out = []
        for r, _, fs in os.walk(self.tmp.name):
            out += [os.path.join(r, f) for f in fs]
        return sorted(out)

    def test_dry_run_changes_nothing_then_removal(self):
        for d in (1, 2, 3, 4, 9):
            self.autosave("Box", d, "/w/Box.FCStd")
        for d in (0.5, 2):
            self.autosave("Unnamed", d)
        for n, d in ((1, 10), (2, 9), (3, 1)):
            self.checkpoint("Part", n, d, name="datum" if n == 1 else None)
        before = self.tree()
        dry = cleanup.prune(dry_run=True, now=NOW, params=Params(), open_names=[])
        self.assertEqual(self.tree(), before)
        self.assertEqual(sorted((r["document"], os.path.basename(r["path"])) for r in dry["rows"]),
                         [("Box", "4.FCStd"), ("Box", "9.FCStd"), ("Part", "2-cp.FCStd"), ("Unnamed", "2.FCStd")])
        self.assertEqual(dry["count"], 4)
        binned = []
        out = cleanup.prune(dry_run=False, now=NOW, params=Params(), open_names=[], bin_=lambda p: binned.append(p) or "trash")
        self.assertEqual(out["removed"], 4)
        self.assertEqual(out["trashed"], 4)
        self.assertEqual(sorted(binned), sorted(r["path"] for r in dry["rows"]))
        idx = json.load(open(os.path.join(self.tmp.name, "checkpoints", "Part", "index.json")))
        self.assertEqual([e["id"] for e in idx], ["cp1", "cp3"])  # the named one stays

    def test_used_and_last_crash_are_kept(self):
        ps = [self.autosave("Box", d, "/w/Box.FCStd") for d in (1, 2, 3, 4, 9)]
        cleanup.mark_used([ps[3]], now=NOW - DAY)
        cleanup.mark_crash([ps[4]], ["Box"], now=NOW - 20 * DAY, pid=123)
        dry = cleanup.prune(dry_run=True, now=NOW, params=Params(), open_names=[])
        self.assertEqual(dry["count"], 0)
        self.assertEqual(cleanup.crash_this_session(pid=123), {os.path.abspath(ps[4])})
        self.assertEqual(cleanup.crash_this_session(pid=124), set())
        cleanup.mark_used([ps[3]], now=NOW - 8 * DAY)  # used, but over a week ago
        self.assertEqual(cleanup.prune(dry_run=True, now=NOW, params=Params(), open_names=[])["count"], 1)

    def test_settings_from_the_parameter_group(self):
        self.assertEqual(cleanup.settings(Params(CopiesKeep=5)), {"CopiesKeep": 5, "CopiesMaxAgeDays": 7, "ScratchMaxAgeDays": 1})
        self.assertEqual(cleanup.settings(Params(CopiesKeep=0))["CopiesKeep"], 3)
        self.assertEqual(cleanup.PARAMS, "User parameter:BaseApp/Preferences/Mod/SafetyNet")

    def test_at_most_once_a_day(self):
        for d in (1, 2, 3, 4):
            self.autosave("Box", d, "/w/Box.FCStd")
        prm, binned = Params(), []
        bin_ = lambda p: binned.append(p) or "trash"  # noqa: E731
        self.assertEqual(cleanup.maybe_prune(now=NOW, params=prm, open_names=[], bin_=bin_)["removed"], 1)
        self.assertIsNone(cleanup.maybe_prune(now=NOW + 3600, params=prm, open_names=[], bin_=bin_))
        self.assertIsNotNone(cleanup.maybe_prune(now=NOW + 3600, params=prm, open_names=[], bin_=bin_, force=True))
        self.assertIsNotNone(cleanup.maybe_prune(now=NOW + 3600 + DAY + 1, params=prm, open_names=[], bin_=bin_))


class Trash(unittest.TestCase):
    def test_mac_trash_without_send2trash(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(sys.modules, {"send2trash": None}):
            os.makedirs(os.path.join(home, ".Trash"))
            for _ in range(3):
                p = os.path.join(home, "1.FCStd")
                with open(p, "w") as f:
                    f.write("x")
                self.assertEqual(cleanup.trash(p, platform="darwin", home=home), "trash")
                self.assertFalse(os.path.exists(p))
            names = os.listdir(os.path.join(home, ".Trash"))
            self.assertEqual(len(names), 3)  # no name clashed
            self.assertIn("1.FCStd", names)

    def test_send2trash_first(self):
        import types

        sent = []
        mod = types.SimpleNamespace(send2trash=sent.append)
        with mock.patch.dict(sys.modules, {"send2trash": mod}):
            self.assertEqual(cleanup.trash("/x/1.FCStd"), "trash")
        self.assertEqual(sent, ["/x/1.FCStd"])

    def test_removed_where_there_is_no_trash(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(sys.modules, {"send2trash": None}):
            p = os.path.join(home, "1.FCStd")
            with open(p, "w") as f:
                f.write("x")
            self.assertEqual(cleanup.trash(p, platform="linux", home=home), "removed")
            self.assertFalse(os.path.exists(p))


class Recovery(unittest.TestCase):
    def test_copies_opened_are_marked(self):
        """A copy opened is kept a week; after a crash it is the Last crash."""
        from safetynet import recovery

        with tempfile.TemporaryDirectory() as h, mock.patch.dict(os.environ, {"AGENTLINK_HOME": h}):
            recovery._remember(["/c/A/1.FCStd"], ["A"], crash=False)
            self.assertIn(os.path.abspath("/c/A/1.FCStd"), cleanup.used())
            self.assertEqual(cleanup.last_crash(), {})
            recovery._remember(["/c/A/1.FCStd"], ["A"], crash=True)
            self.assertEqual(cleanup.crash_this_session(), {os.path.abspath("/c/A/1.FCStd")})


if __name__ == "__main__":
    unittest.main()
