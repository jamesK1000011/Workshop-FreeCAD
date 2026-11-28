# SPDX-License-Identifier: LGPL-2.1-or-later
# app_recover list (test drive of 20 Nov, finding 15): more than 100
# documents came back in one answer. It lists the newest 10 by default
# (limit; 0 gives all), only the documents whose name or label holds
# document, with total, matched and more. Stand-in rows, no FreeCAD.
import os
import sys
import types
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from safetynet import handlers  # noqa: E402
from safetynet.refusal import Refused  # noqa: E402


def rows(n):
    # listing() answers newest first: row 0 is the newest.
    out = [{"document": f"Part{i:03d}", "label": f"Part {i}", "copies": [{"source": "autosave"}]} for i in range(n)]
    out[3] = {"document": "Bicycle", "label": "Bicycle", "copies": [{"source": "autosave"}]}
    out[40] = {"document": "Unnamed", "label": "Bicycle frame", "copies": [{"source": "checkpoint"}]}
    return out


class ListLimit(unittest.TestCase):
    def call(self, a):
        with mock.patch.object(handlers.recovery, "listing", lambda: rows(120)):
            sys.modules.setdefault("FreeCAD", types.ModuleType("FreeCAD"))
            return handlers.app_recover(None, {"action": "list", **a})

    def test_ten_newest_by_default_with_the_total(self):
        r = self.call({})
        self.assertEqual(len(r["documents"]), 10)
        self.assertEqual(r["documents"][0]["document"], "Part000")
        self.assertEqual(r["total"], 120)
        self.assertEqual(110, r["more"])
        self.assertNotIn("matched", r)

    def test_limit_and_zero_for_all(self):
        self.assertEqual(len(self.call({"limit": 3})["documents"]), 3)
        r = self.call({"limit": 0})
        self.assertEqual(len(r["documents"]), 120)
        self.assertNotIn("more", r)

    def test_document_filters_name_and_label_any_case(self):
        r = self.call({"document": "bicycle"})
        self.assertEqual([d["document"] for d in r["documents"]], ["Bicycle", "Unnamed"])
        self.assertEqual(r["matched"], 2)
        self.assertEqual(r["total"], 120)

    def test_bad_inputs_are_refused(self):
        for a in ({"limit": -1}, {"limit": "5"}, {"limit": True}, {"document": ""}, {"document": 4}):
            with self.assertRaises(Refused):
                self.call(a)

    def test_the_panel_and_menu_still_read_all(self):
        root = os.path.dirname(os.path.dirname(HERE))
        for f in ("panel.py", "commands.py"):
            with open(os.path.join(root, "safetynet", f), encoding="utf-8") as fh:
                self.assertIn('("app_recover", {"action": "list", "limit": 0})', fh.read())


if __name__ == "__main__":
    unittest.main()
