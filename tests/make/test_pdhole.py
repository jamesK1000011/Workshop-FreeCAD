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
    """Sizes itself as FreeCAD 1.1.3's does (FeatureHole.cpp): with a
    thread profile the fit sets the clearance (none with Profile None); a
    screw standard's cut sets the cut's sizes; restore() is Hole::Restore
    (a reopen): a sized hole's Diameter set again from size and fit, a
    screw standard's cut again from its table, a plain cut only when at or
    under the hole's diameter."""
    CLEAR = {("M3x0.5", "Fine"): 3.2, ("M3x0.5", "Medium"): 3.4, ("M3x0.5", "Coarse"): 3.6,
             ("M4x0.7", "Medium"): 4.5}
    STD = {("ISO 4762", "M3x0.5"): (5.5, 3.0), ("ISO 10642", "M3x0.5"): (6.72, 0.0), ("ISO 10642", "M4x0.7"): (9.0, 0.0)}
    def __init__(self):
        object.__setattr__(self, "v", {"ThreadType": "None", "ThreadSize": "M6x1.0", "ThreadFit": "Medium", "HoleCutType": "None",
                                        "Diameter": 6.6, "HoleCutDiameter": 0.0, "HoleCutDepth": 0.0, "HoleCutCountersinkAngle": 90.0,
                                        "HoleCutCustomValues": False, "Label2": ""})
    def getEnumerationsOfProperty(self, p):
        return {"ThreadSize": ["M2x0.4", "M3x0.5", "M4x0.7", "M6x1.0"], "ThreadFit": ["Medium", "Fine", "Coarse"],
                "HoleCutType": ["None", "Counterbore", "Countersink", "Counterdrill", "ISO 4762", "ISO 10642"]}.get(p, [])
    def __getattr__(self, k):
        return self.v[k]
    def _diameter(self):
        if self.v["ThreadType"] != "None":
            self.v["Diameter"] = self.CLEAR.get((self.v["ThreadSize"], self.v["ThreadFit"]), 9.9)
    def _cut(self):
        std = self.STD.get((self.v["HoleCutType"], self.v["ThreadSize"]))
        if std and self.v["ThreadType"] != "None":
            self.v["HoleCutDiameter"], self.v["HoleCutDepth"] = std
        elif self.v["HoleCutType"] in ("Counterbore", "Countersink") and self.v["HoleCutDiameter"] <= self.v["Diameter"]:
            self.v["HoleCutDiameter"] = self.v["Diameter"] * (1.6 if self.v["HoleCutType"] == "Counterbore" else 1.7)
    def __setattr__(self, k, x):
        self.v[k] = x
        if k in ("ThreadType", "ThreadSize", "ThreadFit", "Threaded"):
            self._diameter()
        if k == "HoleCutType":
            self._cut()
    def restore(self):
        self._diameter()
        self._cut()
    def recompute(self):
        # Hole::execute changes no property: what restore() left is what is cut.
        return dict(self.v)
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
# FreeCAD lists the cuts in the order it read their files: the standard's own name wins over the one with a washer.
OUT["cut_exact"] = [H.pick_cut(["None", "ISO 4762 + 7089", "ISO 4762"], "counterbore"), H.pick_cut(["None", "ISO 4762 + 7089"], "counterbore")]
import math
h = H.hexagon(5.5)
OUT["af"] = round(max(p[0] for p in h) - min(p[0] for p in h), 4)
OUT["corners"] = len(h)
''')
        self.assertEqual(out["size"], ["M3", "M3x0.5", None])
        self.assertEqual(out["fit"], ["Fine", "Medium", "Coarse"])
        self.assertEqual(out["fit_other"], ["Wide", "b"])
        self.assertEqual(out["cut"], [["ISO 4762", True], ["Countersink", False], ["None", False]])
        self.assertEqual(out["cut_exact"], [["ISO 4762", True], ["ISO 4762 + 7089", True]])
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
OUT["cb_custom"] = h.HoleCutType
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
        self.assertAlmostEqual(out["cal"]["clearanceBeforeAllowance"], 3.4)
        self.assertEqual(out["cal"]["depth"], 6.0)
        # The counterbore is FreeCAD's ISO 4762 one, the allowance added.
        self.assertEqual((out["cb"]["cut"], out["cb"]["cutSizedBy"]), ("ISO 4762", "FreeCAD"))
        self.assertAlmostEqual(out["cb"]["cutDiameter"], 5.7)
        self.assertEqual(out["cb"]["cutDepth"], 3.0)
        self.assertEqual(out["cb_custom"], "Counterbore")  # kept as FreeCAD's plain counterbore
        # FreeCAD has no table for inserts and magnets: a plain hole at size.
        self.assertEqual(out["ins_type"], ["None", "Dimension"])
        self.assertIn("insertSource", out["ins"])
        self.assertAlmostEqual(out["mag"]["hole"], 6.2)
        self.assertAlmostEqual(out["mag"]["depth"], 2.2)
        self.assertIn("6x2", out["refused"][0])
        self.assertIn("lists no M5", out["refused"][1])


class AllowanceKept(unittest.TestCase):
    # Live (FreeCAD 1.1.3): hw_hole answered M4 clearance 4.7 (4.5 + 0.2),
    # but after a later recompute and reopen the Hole read 4.5, FreeCAD's
    # M4 medium fit, and a countersink 9.0 against 9.2 answered.
    def test_answer_and_feature_agree_after_reopen(self):
        out = run(FAKE_HOLE + r'''
got = {}
for kind in ("clearance", "counterbore", "countersink"):
    for add in (0.0, 0.2):
        h = Hole()
        ans = pdhole._configure(h, kind, "M4" if kind != "counterbore" else "M3", "through", "normal", add)
        h.restore()
        h.recompute()
        got[f"{kind} {add}"] = {"ans": ans, "d": h.Diameter, "cd": h.HoleCutDiameter, "type": h.ThreadType, "label2": h.Label2}
OUT["got"] = got
# Without the fix: the allowance on a sized hole, as before, is lost on reopen.
h = Hole()
h.ThreadType = "ISOMetricProfile"; h.ThreadSize = "M4x0.7"; h.ThreadFit = "Medium"
h.Diameter = h.Diameter + 0.2
h.restore()
OUT["old_way"] = h.Diameter
''')
        self.assertAlmostEqual(out["old_way"], 4.5)  # the stand-in resets as FreeCAD does
        for k, g in out["got"].items():
            self.assertAlmostEqual(g["d"], g["ans"]["clearance"], msg=k)
            if not k.startswith("clearance"):
                self.assertAlmostEqual(g["cd"], g["ans"]["cutDiameter"], msg=k)
        c = out["got"]["clearance 0.2"]
        self.assertAlmostEqual(c["d"], 4.7)
        self.assertEqual(c["type"], "None")
        self.assertIn("Diameter", c["ans"]["allowanceOn"]["props"])
        self.assertIn("M4 clearance, ISO 273 medium 4.5 mm + 0.2 mm", c["label2"])
        cs = out["got"]["countersink 0.2"]
        self.assertAlmostEqual(cs["cd"], 9.2)
        self.assertEqual(cs["ans"]["cutBeforeAllowance"], 9.0)
        self.assertIn("HoleCutDiameter", cs["ans"]["allowanceOn"]["props"])
        # No allowance: FreeCAD's own sized hole, as it was.
        self.assertEqual(out["got"]["clearance 0.0"]["type"], "ISOMetricProfile")
        self.assertAlmostEqual(out["got"]["countersink 0.0"]["cd"], 9.0)
        self.assertNotIn("allowanceOn", out["got"]["clearance 0.0"]["ans"])


class HeadSide(unittest.TestCase):
    def test_which_face_the_head_is_on(self):
        out = run(r'''
from workshop_make import pdhole as H
OUT["wall"] = H.head_side("countersink", [0, 20, 15], (1, 0, 0))
OUT["top"] = H.head_side("counterbore", [10, 5, 12.5], (0, 0, -1))
OUT["slant"] = H.head_side("clearance", [1, 2, 3], (1, 1, 0))
OUT["sketch"] = H.head_side("clearance", None, (0, 0, -1))
''')
        self.assertEqual((out["wall"]["face"], out["wall"]["facing"]), ("x=0", "-x"))
        self.assertEqual(out["wall"]["head"], "countersink")
        self.assertEqual((out["top"]["head"], out["top"]["face"], out["top"]["facing"]), ("counterbore", "z=12.5", "+z"))
        self.assertEqual(out["slant"]["facing"], [-0.7071, -0.7071, 0.0])
        self.assertTrue(out["sketch"]["onSketch"])


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
# live 105: a sketch named Sketch001 whose label is another word is found by its name
class D2(D):
    def getObject(self, n): return "the sketch" if n == "Sketch001" else None
OUT["by_name"] = api._named(D2(), "Sketch001")
OUT["by_none"] = api._named(D2(), "Nothing")
''')
        self.assertEqual(out["pd"]["route"], "PartDesign Hole")
        self.assertEqual(out["pd"]["features"], ["HoleSketch", "Hole"])
        self.assertEqual(out["pd"]["removed"], 10.0)
        self.assertEqual(out["seen"], {"kind": "clearance", "face": "Face6", "at": [1, 2, 3]})
        self.assertIn("PartDesign Body only", out["plain_sketch"])
        self.assertEqual(out["by_name"], "the sketch")
        self.assertIsNone(out["by_none"])


class Settle(unittest.TestCase):
    def test_what_the_change_left_touched_is_recomputed_too(self):
        # Found live (16 Nov 2026): after hw_hole in a Body with two screws
        # on its holes the health check said "2 objects not recomputed
        # yet". The document's recompute of a list runs the list and what
        # it stands on, not what stands on it.
        out = run(r'''
from workshop_make import pdhole
class O:
    def __init__(self, name, touched=False, on=None):
        self.Name, self.touched, self.on, self.runs = name, touched, on, 0
    State = property(lambda self: ["Touched"] if self.touched else [])
class D:
    def __init__(self, objs): self.Objects, self.calls = objs, []
    def recompute(self, objs=None):
        todo = self.Objects if objs is None else list(objs)
        self.calls.append([o.Name for o in todo])
        for o in todo:
            o.touched, o.runs = False, o.runs + 1
            for d in self.Objects:   # FreeCAD: a link to a renumbered edge is touched
                if d.on is o:
                    d.touched = True
body, hole = O("Body"), O("Hole", touched=True)
screw, stale, far = O("Screw", on=body), O("Stale", touched=True), O("Far")
d = D([body, hole, screw, stale, far])
pdhole.settle(d, [hole, body])
OUT["calls"] = d.calls
OUT["touched"] = [o.Name for o in d.Objects if o.touched]
OUT["runs"] = {o.Name: o.runs for o in d.Objects}
''')
        self.assertEqual(out["calls"], [["Hole", "Body"], ["Screw"]])
        # What was waiting before the call is not this call's: left as it was.
        self.assertEqual(out["touched"], ["Stale"])
        self.assertEqual(out["runs"], {"Body": 1, "Hole": 1, "Screw": 1, "Stale": 0, "Far": 0})


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
