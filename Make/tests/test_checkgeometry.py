# SPDX-License-Identifier: LGPL-2.1-or-later
# Soundness is FreeCAD's own Check Geometry (Shape.check, as
# Part_CheckGeometry runs it, its BOP-check preference honoured); Make adds
# only what a printed part needs beyond it. A stand-in shape here.
import unittest

from _stubs import run

SHAPE = r'''
from workshop_make import geo
class Shell:
    def __init__(self, closed): self.c = closed
    def isClosed(self): return self.c
class Shape:
    def __init__(self, bad=None, closed=True, solids=1):
        self.bad, self.Shells, self.Solids, self.Faces, self.Edges, self.calls = bad, [Shell(closed)], [1] * solids, [], [], []
    def check(self, bop=False):
        self.calls.append(bop)
        if self.bad:
            raise ValueError("\n".join(self.bad))
    def isValid(self): return not self.bad
bop = {"v": False}
class Params:
    def GetBool(self, k, d=False): return bop["v"] if k == "RunBOPCheck" else d
sys.modules["FreeCAD"].ParamGet = lambda path: Params()
'''


class CheckGeometry(unittest.TestCase):
    def test_freecads_check_then_makes_extras(self):
        out = run(SHAPE + r'''
good = Shape()
OUT["good"] = geo.soundness(good)
bad = Shape(bad=["Face 3: BRepCheck_NotClosed", "Edge 7: BRepCheck_InvalidCurveOnSurface"])
OUT["bad"] = geo.soundness(bad)
bop["v"] = True
s = Shape(closed=False, solids=2)
OUT["open"] = geo.soundness(s)
OUT["bop"] = s.calls
class Old:
    Shells, Solids, Faces, Edges = [], [], [], []
    def isValid(self): return False
OUT["old"] = geo.freecad_check(Old())
''')
        g, b, o = out["good"], out["bad"], out["open"]
        self.assertTrue(g["ok"])
        self.assertEqual(g["checkedBy"], "FreeCAD's Check Geometry")
        self.assertFalse(b["ok"])
        self.assertEqual(b["checkGeometry"], ["Face 3: BRepCheck_NotClosed", "Edge 7: BRepCheck_InvalidCurveOnSurface"])
        self.assertIn("FreeCAD's Check Geometry", b["problems"][0])
        # Passing Check Geometry is not all a print needs: closed, one solid.
        self.assertTrue(o["valid"])
        self.assertEqual(len(o["problems"]), 2)
        self.assertEqual(out["bop"], [True])
        self.assertIsNone(out["old"])


if __name__ == "__main__":
    unittest.main()
