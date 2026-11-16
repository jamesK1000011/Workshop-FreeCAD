# SPDX-License-Identifier: LGPL-2.1-or-later
# Cut Export's layout by FreeCAD's BIM Nest, against a stand-in that keeps
# ArchNesting's real shapes (FreeCAD 1.1.3): Nester(container, shapes),
# run() returning the sheets and appending them to results, each sheet a
# list of [hashCode, face], ROTATIONS a module constant, no margin setting.
import unittest

from _stubs import run

FAKE = r'''
import types
from workshop_make import bimnest as B
class BB:
    def __init__(s, x, y, w, h): s.XMin, s.YMin, s.XLength, s.YLength = x, y, w, h
N = [0]
class Face:
    def __init__(s, x, y, w, h):
        N[0] += 1
        s.h, s.Area, s.BoundBox = N[0], w * h, BB(x, y, w, h)
        s.Faces = [s]
    def hashCode(s): return s.h
    def copy(s): return Face(s.BoundBox.XMin, s.BoundBox.YMin, s.BoundBox.XLength, s.BoundBox.YLength)
    def makeOffset2D(s, d, join=0):
        b = s.BoundBox
        return Face(b.XMin - d, b.YMin - d, b.XLength + 2 * d, b.YLength + 2 * d)
    def moved(s, x, y):
        f = Face(x, y, s.BoundBox.XLength, s.BoundBox.YLength); return f
seen = {}
class Nester:
    def __init__(self, container=None, shapes=None):
        self.container, self.shapes, self.results = container, shapes, []
    def run(self):
        seen.update(rotations=list(an.ROTATIONS), container=self.container, n=len(self.shapes))
        x, sheet, sheets = 1.5, [], []
        for sh in self.shapes:
            w = sh.BoundBox.XLength
            if x + w > 300:
                sheets.append([[sh.hashCode(), sh.moved(1.5, 1.5)]])
                continue
            sheet.append([sh.hashCode(), sh.moved(x, 1.5)])
            x += w
        sheets.insert(0, sheet)
        self.results.append(sheets)
        return sheets
an = types.ModuleType("ArchNesting"); an.Nester, an.ROTATIONS = Nester, [0, 90, 180, 270]
sys.modules["Part"].makePlane = lambda w, h, at=None: ("plane", w, h, at)
sys.modules["FreeCAD"].Vector = lambda *a: list(a)
'''


class Nest(unittest.TestCase):
    def test_without_bim(self):
        out = run(FAKE + r'''
OUT["why"] = B.nest([Face(0, 0, 100, 60)], 300, 200, 3)[1]
''')
        self.assertIn("not in this FreeCAD", out["why"])

    def test_bims_sheets_read_back(self):
        out = run(FAKE + r'''
sys.modules["ArchNesting"] = an
faces = [Face(0, 0, 100, 60), Face(0, 0, 100, 60), Face(0, 0, 100, 60)]
OUT["moves"], OUT["why"] = B.nest(faces, 300, 200, 3)
OUT["seen"] = seen
OUT["rot_after"] = an.ROTATIONS
''')
        # Grown by half the gap, laid side by side from the sheet's margin;
        # the third does not fit the first sheet: left over.
        self.assertIsNone(out["why"])
        self.assertEqual(out["moves"][:2], [[3.0, 3.0], [106.0, 3.0]])
        self.assertIsNone(out["moves"][2])
        self.assertEqual(out["seen"]["rotations"], [0])
        self.assertEqual(out["seen"]["container"], ["plane", 297, 197, [1.5, 1.5, 0]])
        self.assertEqual(out["rot_after"], [0, 90, 180, 270])

    def test_a_turned_piece_is_refused(self):
        out = run(FAKE + r'''
sys.modules["ArchNesting"] = an
def turned(self):
    sh = self.shapes[0]; b = sh.BoundBox
    s = [[[sh.hashCode(), Face(0, 0, b.YLength, b.XLength)]]]
    self.results.append(s); return s
Nester.run = turned
OUT["why"] = B.nest([Face(0, 0, 100, 60)], 300, 200, 3)[1]
''')
        self.assertIn("turned", out["why"])


if __name__ == "__main__":
    unittest.main()
