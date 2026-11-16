# SPDX-License-Identifier: LGPL-2.1-or-later
# Hole for Hardware on FreeCAD's own PartDesign Hole: the names it picks in
# FreeCAD's lists, the Hole it sets up (a stand-in Hole that sizes itself
# from a small table, as FreeCAD's does), the route api.hole takes, and the
# face or sketch the task panel starts on. FreeCAD stood in for.
import unittest

from _stubs import run

FAKE_HOLE = r'''
from workshop_make import pdhole

class Hole:
    """Sizes itself as FreeCAD's does: the fit sets the clearance, a screw
    standard's cut sets the cut's sizes."""
    CLEAR = {("M3x0.5", "Fine"): 3.2, ("M3x0.5", "Medium"): 3.4, ("M3x0.5", "Coarse"): 3.6}
    def __init__(self):
        object.__setattr__(self, "v", {"ThreadSize": "M6x1.0", "ThreadFit": "Medium", "HoleCutType": "None", "Diameter": 6.6,
                                        "HoleCutDiameter": 0.0, "HoleCutDepth": 0.0})
    def getEnumerationsOfProperty(self, p):
        return {"ThreadSize": ["M2x0.4", "M3x0.5", "M6x1.0"], "ThreadFit": ["Medium", "Fine", "Coarse"],
                "HoleCutType": ["None", "Counterbore", "Countersink", "Counterdrill", "ISO 4762", "ISO 10642"]}.get(p, [])
    def __getattr__(self, k):
        return self.v[k]
    def __setattr__(self, k, x):
        self.v[k] = x
        if k in ("ThreadSize", "ThreadFit"):
            self.v["Diameter"] = self.CLEAR.get((self.v["ThreadSize"], self.v["ThreadFit"]), 9.9)
        if k == "HoleCutType" and x == "ISO 4762":
            self.v["HoleCutDiameter"], self.v["HoleCutDepth"] = 5.5, 3.0
'''


class Picks(unittest.TestCase):
    def test_names_in_freecads_lists(self):
        out = run(r'''
from workshop_make import pdhole as H
OUT["size"] = [H.pick_size(["M3", "M4"], "M3"), H.pick_size(["M3x0.5", "M3x0.35"], "M3"), H.pick_size(["M4x0.7"], "M3")]
OUT["fit"] = [H.pick_fit(["Medium", "Fine", "Coarse"], f) for f in ("close", "normal", "loose")]
OUT["fit_other"] = [H.pick_fit(["Standard", "Close", "Wide"], "loose"), H.pick_fit(["a", "b", "c"], "close")]
OUT["cut"] = [H.pick_cut(["None", "Counterbore", "ISO 4762"], "counterbore"), H.pick_cut(["None", "Counterbore", "Countersink"], "countersink"),
              H.pick_cut(["None"], "counterbore")]
import math
h = H.hexagon(5.5)
OUT["af"] = round(max(p[0] for p in h) - min(p[0] for p in h), 4)
OUT["corners"] = len(h)
''')
        self.assertEqual(out["size"], ["M3", "M3x0.5", None])
        self.assertEqual(out["fit"], ["Fine", "Medium", "Coarse"])
        self.assertEqual(out["fit_other"], ["Wide", "b"])
        self.assertEqual(out["cut"], [["ISO 4762", True], ["Countersink", False], ["None", False]])
        self.assertEqual(out["corners"], 6)
        self.assertAlmostEqual(out["af"], 5.5, places=3)


class Configure(unittest.TestCase):
    def test_freecads_sizes_and_only_the_allowance_on_top(self):
        out = run(FAKE_HOLE + r'''
h = Hole()
OUT["clear"] = pdhole._configure(h, "clearance", "M3", "through", "close", 0.0)
OUT["clear_type"] = [h.ThreadType, h.ThreadSize, h.Threaded, h.HoleCutType, h.DepthType]
h = Hole()
OUT["cal"] = pdhole._configure(h, "clearance", "M3", 6, "normal", 0.2)
h = Hole()
OUT["cb"] = pdhole._configure(h, "counterbore", "M3", "through", "normal", 0.2)
OUT["cb_custom"] = h.HoleCutCustomValues
h = Hole()
OUT["ins"] = pdhole._configure(h, "insert", "M3", "through", "normal", 0.1)
OUT["ins_type"] = [h.ThreadType, h.DepthType]
h = Hole()
OUT["mag"] = pdhole._configure(h, "magnet", "6x2", "through", "normal", 0.2)
for bad in (("magnet", "6"), ("clearance", "M5")):
    try:
        pdhole._configure(Hole(), bad[0], bad[1], "through", "normal", 0.0)
        OUT.setdefault("refused", []).append(None)
    except pdhole.Failed as e:
        OUT.setdefault("refused", []).append(str(e))
''')
        self.assertEqual(out["clear"]["clearance"], 3.2)
        self.assertEqual(out["clear"]["freecadSize"], "M3x0.5")
        self.assertEqual(out["clear_type"], ["ISOMetricProfile", "M3x0.5", False, "None", "ThroughAll"])
        self.assertAlmostEqual(out["cal"]["clearance"], 3.6)
        self.assertEqual(out["cal"]["depth"], 6.0)
        # The counterbore is FreeCAD's ISO 4762 one, the allowance added.
        self.assertEqual((out["cb"]["cut"], out["cb"]["cutSizedBy"]), ("ISO 4762", "FreeCAD"))
        self.assertAlmostEqual(out["cb"]["cutDiameter"], 5.7)
        self.assertEqual(out["cb"]["cutDepth"], 3.0)
        self.assertTrue(out["cb_custom"])
        # FreeCAD has no table for inserts and magnets: a plain hole at size.
        self.assertEqual(out["ins_type"], ["None", "Dimension"])
        self.assertIn("insert", out["ins"]["note"])
        self.assertAlmostEqual(out["mag"]["hole"], 6.2)
        self.assertAlmostEqual(out["mag"]["depth"], 2.2)
        self.assertIn("6x2", out["refused"][0])
        self.assertIn("lists no M5", out["refused"][1])


class Route(unittest.TestCase):
    def test_body_gets_a_hole_and_a_plain_solid_is_told(self):
        out = run(r'''
from workshop_make import api, pdhole, geo
class Shape:
    Volume, Solids = 1000.0, [1]
    def isNull(self): return False
class Body:
    Label = "Bracket"
    def __init__(self): self.Shape = Shape()
    def isDerivedFrom(self, t): return t == "PartDesign::Body"
class Plain:
    Label = "Plate"
    def isDerivedFrom(self, t): return False
    def getParentGeoFeatureGroup(self): return None
class D:
    Meta = {}
    def getObjectsByLabel(self, l): return []
    def recompute(self): pass
body, seen = Body(), {}
def make(doc, pd, kind, size, at, d, depth, fit, cal, face=None, sketch=None):
    seen.update(kind=kind, face=face, at=at)
    pd.Shape.Volume = 990.0
    return ["HoleSketch", "Hole"], {"clearance": 3.6}
pdhole.make = make
geo.soundness = lambda s: {"ok": True, "problems": []}
api.calibration = lambda doc, label: ({"hole": 0.2}, "hole 0.2")
OUT["pd"] = api.hole(D(), body, "clearance", "M3", at=[1, 2, 3], face="Face6")
OUT["seen"] = seen
try:
    api.hole(D(), Plain(), "clearance", "M3", sketch=Plain())
except api.Refused as e:
    OUT["plain_sketch"] = str(e)
''')
        self.assertEqual(out["pd"]["route"], "PartDesign Hole")
        self.assertEqual(out["pd"]["features"], ["HoleSketch", "Hole"])
        self.assertEqual(out["pd"]["removed"], 10.0)
        self.assertIn("double-click", out["pd"]["note"])
        self.assertEqual(out["seen"], {"kind": "clearance", "face": "Face6", "at": [1, 2, 3]})
        self.assertIn("PartDesign Body only", out["plain_sketch"])


class Panel(unittest.TestCase):
    def test_starts_on_the_face_or_sketch_picked(self):
        out = run(r'''
import types
from workshop_make import taskpanels as T
class O:
    def __init__(self, t, label, parent=None): self.t, self.Label, self.Name, self.p, self.Tip = t, label, label, parent, None
    def isDerivedFrom(self, t): return t == self.t
    def getParentGeoFeatureGroup(self): return self.p
body = O("PartDesign::Body", "Body")
tip = O("PartDesign::Pad", "Pad", body)
body.Tip = tip
older = O("PartDesign::Pad", "Pad001", body)
sk = O("Sketcher::SketchObject", "Holes", body)
plain = O("Part::Feature", "Plate")
def sel(o, subs):
    return [types.SimpleNamespace(Object=o, SubElementNames=subs)]
got = []
for o, subs in ((tip, ["Face6"]), (body, ["Pad.Face3"]), (older, ["Face2"]), (sk, []), (plain, ["Face1"]), (body, ["Pad001.Face2"])):
    sys.modules["FreeCADGui"].Selection = types.SimpleNamespace(getSelectionEx=lambda o=o, subs=subs: sel(o, subs))
    got.append(T.picked_entry())
sys.modules["FreeCADGui"].Selection = types.SimpleNamespace(getSelectionEx=lambda: [])
got.append(T.picked_entry())
OUT["got"] = got
OUT["intro"] = T.INTRO["hole"]
''')
        self.assertEqual(out["got"], [{"face": "Face6"}, {"face": "Face3"}, {}, {"sketch": "Holes"}, {}, {}, {}])
        self.assertIn("FreeCAD's own Hole", out["intro"])


if __name__ == "__main__":
    unittest.main()
