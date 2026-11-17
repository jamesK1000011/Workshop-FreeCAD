# SPDX-License-Identifier: LGPL-2.1-or-later
# fastener_set leaves no fastener it changed "not recomputed yet" (window
# review round 3: an old open fault): one more recompute when one is left
# touched that was not before the call (api.settle), none otherwise.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from workshop_fasteners import api  # noqa: E402


class O:
    def __init__(self, name, state):
        self.Name, self.State = name, list(state)


class Doc:
    def __init__(self, objs):
        self.objs, self.runs = objs, 0

    def recompute(self):
        self.runs += 1
        for o in self.objs:
            o.State = [s for s in o.State if s != "Touched"]


class Settle(unittest.TestCase):
    def test_left_touched_by_the_call(self):
        a, b = O("Screw", ["Touched"]), O("Nut", [])
        d = Doc([a, b])
        self.assertTrue(api.settle(d, [a, b], was=set()))
        self.assertEqual((d.runs, a.State), (1, []))

    def test_touched_before_or_nothing_left(self):
        a, b = O("Screw", ["Touched"]), O("Nut", [])
        d = Doc([a, b])
        self.assertFalse(api.settle(d, [a, b], was={"Screw"}))   # not this call's to recompute
        self.assertFalse(api.settle(d, [b]))
        self.assertEqual(d.runs, 0)


if __name__ == "__main__":
    unittest.main()
