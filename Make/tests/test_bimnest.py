# SPDX-License-Identifier: LGPL-2.1-or-later
# Cut Export's layout by FreeCAD's BIM Nest: its placed faces read back to
# each part (copies alike), a part it left out None, and the rows when BIM
# is not here. BIM stood in for.
import unittest

from _stubs import run


class Nest(unittest.TestCase):
    def test_moves_read_back(self):
        out = run(r'''
from workshop_make import bimnest as B
origs = [(200.0, 20, 10, 0, 0), (200.0, 20, 10, 0, 0), (50.0, 5, 10, 0, 0)]
OUT["two"] = B.match_moves(origs, [(200.0, 20, 10, 30, 5), (50.0, 5, 10, 60, 0), (200.0, 20, 10, 3, 5)])
OUT["left"] = B.match_moves(origs, [(200.0, 20, 10, 30, 5)])
''')
        self.assertEqual(out["two"], [[30, 5], [3, 5], [60, 0]])
        self.assertEqual(out["left"], [[30, 5], None, None])

    def test_bims_nester_and_its_absence(self):
        out = run(r'''
import types
from workshop_make import bimnest as B
class BB:
    def __init__(s, x, y, w, h): s.XMin, s.YMin, s.XLength, s.YLength = x, y, w, h
class F:
    def __init__(s, x, y): s.Area, s.BoundBox = 200.0, BB(x, y, 20, 10)
OUT["none"] = B.nest([F(0, 0)], 100, 50, 3)[1]
seen = {}
class Nester:
    def __init__(self, container=None, shapes=None):
        self.shapes, self.margin, self.rotations, self.results = shapes, 0, [0, 90], []
    def run(self):
        seen.update(margin=self.margin, rotations=self.rotations)
        self.results.append([F(40, 20)])
an = types.ModuleType("ArchNesting"); an.Nester = Nester
sys.modules["ArchNesting"] = an
sys.modules["Part"].makePlane = lambda w, h: ("plane", w, h)
OUT["moves"], OUT["why"] = B.nest([F(0, 0)], 100, 50, 3)
OUT["seen"] = seen
''')
        self.assertIn("BIM Nest", out["none"])
        self.assertEqual(out["moves"], [[40, 20]])
        self.assertIsNone(out["why"])
        self.assertEqual(out["seen"], {"margin": 3, "rotations": [0]})


if __name__ == "__main__":
    unittest.main()
