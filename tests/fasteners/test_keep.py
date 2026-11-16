# SPDX-License-Identifier: LGPL-2.1-or-later
# The keeper (workshop_fasteners/keep.py), found on a live test drive (16 Nov
# 2026, FreeCAD 1.1.3): screws lost their hole when a later PartDesign
# feature renumbered the Body's edges, and their labels counted up at every
# recompute (M8x25-Screw218, 219, 222). The stand-in document here does
# what FreeCAD and Fasteners do there: a label set to one in use gets the
# next suffix past the highest (the object's own counted), and each
# recompute runs a Fasteners-like execute that relabels "M8x25-Screw" and
# moves the screw to whatever its BaseObject edge now is. On the reference
# clone of Fasteners Workbench (FASTENERS_SRC, else /tmp/fwb), as
# test_bridge.py.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _fwb import have_fasteners, run  # noqa: E402

SETUP = r'''
import re
from workshop_fasteners import api, keep

def unique(doc, o, want):
    """FreeCAD 1.x: a label in use gets the suffix one past the highest
    of that base (the object's own label counted)."""
    if not any(x.Label == want for x in doc.Objects if x is not o) and o.Label == want:
        return want
    if not any(x.Label == want for x in doc.Objects):
        return want
    nums = [int(m.group(1)) for x in doc.Objects for m in [re.fullmatch(re.escape(want) + r"(\d+)", x.Label)] if m]
    return f"{want}{max(nums + [0]) + 1:03d}"

def execute(o):
    """Fasteners' execute as far as it matters here: its label,
    unconditionally, and the screw moved onto its BaseObject's edge if that
    is round."""
    object.__setattr__(o, "Label", unique(doc, o, f"{o.Diameter}x{o.Length}-Screw"))
    b = o.BaseObject
    sh = b[0].getSubObject(b[1][0]) if b and b[0] is not None and b[1] else None
    if sh is not None and hasattr(sh.Curve, "Radius"):
        o.Placement.Base = sh.Curve.Center

FP.recompute = execute  # DocumentObject.recompute(): this one's execute

class FDoc(Doc):
    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)
    def recompute(self):
        Doc.recompute(self)
        for o in self.Objects:
            if isinstance(o, FP) and hasattr(o, "Diameter"):
                execute(o)
        for f in OBS:
            f.slotRecomputedDocument(self)

OBS = [keep.Observer()]
doc = FDoc()
# A plate: two M8 pass holes (⌀8.4) at x=10 and x=40, top and bottom edges,
# and a ⌀20 bore.
top1, bot1 = Edge(Vec(10, 0, 10), Vec(0, 0, 1), 4.2), Edge(Vec(10, 0, 0), Vec(0, 0, 1), 4.2)
top2, bot2 = Edge(Vec(40, 0, 10), Vec(0, 0, 1), 4.2), Edge(Vec(40, 0, 0), Vec(0, 0, 1), 4.2)
bore = Edge(Vec(70, 0, 10), Vec(0, 0, 1), 10.0)
plate = Plate("Body", [top1, bot1, top2, bot2, bore])
doc.Objects.append(plate)
'''


@unittest.skipUnless(have_fasteners(), "the Fasteners Workbench reference clone is not here")
class Keep(unittest.TestCase):
    def test_labels_stay_put_across_recomputes(self):
        out = run(SETUP + r'''
a = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge1"])[0]
b = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge3"])[0]
c = api.add(doc, "ISO4762", "M8", 30, edges=["Body.Edge2"])[0]
OUT["first"] = [a.Label, b.Label, c.Label]
for _ in range(5):
    doc.recompute()
OUT["after"] = [a.Label, b.Label, c.Label]
names = [a.Name, b.Name, c.Name]
api.change(doc, [b.Label], length=30)
OUT["changed"] = [a.Label, b.Label, c.Label]
OUT["names"] = [a.Name, b.Name, c.Name] == names
api.change(doc, [a.Label], label="Clamp bolt")
doc.recompute()
OUT["named"] = a.Label
OUT["count"] = len(api.fasteners_in(doc))
''')
        self.assertEqual(out["first"], ["M8x25-Screw", "M8x25-Screw 2", "M8x30-Screw"])
        self.assertEqual(out["after"], out["first"])  # five recomputes: no counting up
        # A new length: in place, its label follows the size, numbered per size.
        self.assertEqual(out["changed"], ["M8x25-Screw", "M8x30-Screw 2", "M8x30-Screw"])
        self.assertTrue(out["names"])
        self.assertEqual(out["named"], "Clamp bolt")
        self.assertEqual(out["count"], 3)

    def test_without_the_keeper_labels_count_up(self):
        # The stand-in reproduces what was seen live, so the test above means something.
        out = run(SETUP + r'''
OBS.clear()
a = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge1"])[0]
b = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge3"])[0]
seen = []
for _ in range(3):
    doc.recompute(); seen.append(b.Label)
OUT["seen"] = seen
''')
        self.assertEqual(len(set(out["seen"])), 3, out["seen"])

    def test_renumbered_edges_reattach(self):
        out = run(SETUP + r'''
s = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge3"])[0]
OUT["was"] = api.describe(s)["attachedTo"]
# A later feature: two new edges in front, the rest renumbered.
plate.Shape.Edges[:0] = [Edge(Vec(0, 50, 0), Vec(1, 0, 0), 2.0), Edge(Vec(5, 5, 5), Vec(0, 0, 1), 4.2 + 0.5)]
doc.recompute()
d = api.describe(s)
OUT["now"], OUT["re"], OUT["at"] = d["attachedTo"], d.get("reattached"), d["at"]
OUT["listed"] = api.listing(doc).get("warnings")
''')
        self.assertEqual(out["was"], "Body.Edge3")
        self.assertEqual(out["now"], "Body.Edge5")  # the same circle, its new number
        self.assertIn("renumbered", out["re"])
        self.assertEqual(out["at"], [40, 0, 10])
        self.assertIsNone(out["listed"])

    def test_lost_hole_is_said_loudly(self):
        out = run(SETUP + r'''
s = api.add(doc, "ISO4762", "M8", 25, edges=["Body.Edge3"])[0]
# The hole removed: Edge3 is now the bore's edge, no ⌀8.4 edge near (40, 0, 10).
plate.Shape.Edges[:] = [top1, bot1, bore]
doc.recompute()
L = api.listing(doc)
OUT["warn"] = L.get("warnings")
OUT["lost"] = L["fasteners"][0].get("lost")
''')
        self.assertTrue(out["warn"] and "lost its hole" in out["warn"][0], out)
        self.assertIn("M8x25-Screw", out["warn"][0])
        self.assertTrue(any("lost its hole" in e for e in out["errs"]))  # the Report view
        self.assertEqual(out["lost"], out["warn"][0])

    def test_hole_is_not_another_one_far_off(self):
        out = run(SETUP + r'''
from workshop_fasteners import keep as k
g = k.geometry(plate, "Edge3")
OUT["same"] = k.refind(plate, g)
g2 = dict(g, c=[25.0, 0.0, 10.0])  # between the two holes, beyond reach of either
OUT["none"] = k.refind(plate, g2)
g3 = dict(g, c=[40.5, 0.0, 10.0])  # nudged half a millimetre
OUT["near"] = k.refind(plate, g3)
''')
        self.assertEqual(out["same"], "Edge3")
        self.assertIsNone(out["none"])
        self.assertEqual(out["near"], "Edge3")

    def test_hw_hole_again_changes_the_screw_in_place(self):
        out = run(SETUP + r'''
args = {"kind": "clearance", "size": "M8", "at": [40, 0, 10], "dir": "-z"}
r1 = api.hole_screw(doc, args, {"body": "Body", "through": 10}, True)
r2 = api.hole_screw(doc, args, {"body": "Body", "through": 10}, {"length": 16})
OUT["r"] = [r1["screw"]["object"], r2["screw"]["object"], r2["screw"]["label"]]
OUT["count"] = len(api.fasteners_in(doc))
''')
        self.assertEqual(out["r"][0], out["r"][1])
        self.assertEqual(out["r"][2], "M8x16-Screw")
        self.assertEqual(out["count"], 1)

    def test_older_screws_are_adopted(self):
        # StemV2, made before the keeper: screws with no kept hole whose
        # labels Fasteners had counted up, and one someone named.
        out = run(SETUP + r"""
from workshop_fasteners import fs
F = fs.load()
keeper = OBS.pop()  # the file as it was saved: made with no keeper about
def old(edge, length, label):
    o = doc.addObject("Part::FeaturePython", "Screw")
    F.FastenersCmd.FSScrewObject(o, "ISO4762", (plate, [edge]))
    o.Diameter = "M8"
    doc.recompute()
    o.Length = str(length)
    object.__setattr__(o, "Label", label)
    return o
a, b, c, d = old("Edge1", 25, "M8x25-Screw221"), old("Edge3", 25, "M8x25-Screw225"), old("Edge2", 35, "M8x35-Screw002"), old("Edge4", 25, "Clamp bolt")
OBS.append(keeper)
keeper.slotFinishRestoreDocument(doc)  # as the file opens
OUT["opened"] = [x.Label for x in (a, b, c, d)]
for _ in range(3):
    doc.recompute()
OUT["after"] = [x.Label for x in (a, b, c, d)]
L = api.listing(doc)
OUT["states"] = [(f["label"], f.get("hole"), f.get("adopted")) for f in L["fasteners"]]
plate.Shape.Edges[:0] = [Edge(Vec(0, 50, 0), Vec(1, 0, 0), 2.0)]
doc.recompute()
OUT["moved"] = [(f["label"], f.get("hole"), f["attachedTo"]) for f in api.listing(doc)["fasteners"]]
""")
        self.assertEqual(out["opened"], ["M8x25-Screw", "M8x25-Screw 2", "M8x35-Screw", "Clamp bolt"])
        self.assertEqual(out["after"], out["opened"])  # no more counting up
        self.assertEqual([s[1:] for s in out["states"]], [["kept", True]] * 4)
        self.assertEqual([m[1] for m in out["moved"]], ["reattached"] * 4)
        self.assertEqual([m[2] for m in out["moved"]], ["Body.Edge2", "Body.Edge4", "Body.Edge3", "Body.Edge5"])

    def test_near_a_holes_centre(self):
        out = run(SETUP + r"""
from workshop_fasteners import fs
OUT["on_rim"] = api.element(doc, {"body": "Body", "near": [44.2, 0, 10]})[1]
OUT["centre_top"] = api.element(doc, {"body": "Body", "near": [40, 0, 10]})[1]
OUT["centre_bottom"] = api.element(doc, {"body": "Body", "near": [40, 0, 0.5]})[1]
try:
    api.element(doc, {"body": "Body", "near": [40, 0, 5]})  # inside the hole, 5 mm from either rim's centre
except fs.Missing as e:
    OUT["refused"] = e.message
s = api.add(doc, "ISO4762", "M8", 20, edges=[{"body": "Body", "near": [10, 0, 10]}])[0]
OUT["added"] = api.describe(s)["attachedTo"]
""")
        self.assertEqual(out["on_rim"], "Edge3")
        self.assertEqual(out["centre_top"], "Edge3")
        self.assertEqual(out["centre_bottom"], "Edge4")
        self.assertIn("centre", out["refused"])
        self.assertEqual(out["added"], "Body.Edge1")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(have_fasteners(), "the Fasteners Workbench reference clone is not here")
class Reopen(unittest.TestCase):
    # Live (FreeCAD 1.1.3): after a reopen the labels came out once as
    # "M8x25-Screw 001/002/003" and after the next as "M8x25-Screw 2/3/4".
    # Here a reopen is the labels as saved, then Fasteners' execute on each
    # screw in turn, with a uniquifier that also counts up a label set to
    # the one the object already holds (and with a space, as seen).
    def test_labels_the_same_after_each_reopen(self):
        out = run(SETUP + r'''
def quirky(doc, o, want):
    if not any(x.Label == want for x in doc.Objects):
        return want
    nums = [int(m.group(1)) for x in doc.Objects for m in [re.fullmatch(re.escape(want) + r" (\d+)", x.Label)] if m]
    return f"{want} {max(nums + [0]) + 1:03d}"
screws = [api.add(doc, "ISO4762", "M8", 25, edges=[e])[0] for e in ("Body.Edge1", "Body.Edge2", "Body.Edge3", "Body.Edge4")]
first = [s.Label for s in screws]
seen, sets = [], []
real_set = FP.__setattr__
def spy(self, k, v):
    if k == "Label":
        sets.append(v)
    real_set(self, k, v)
FP.__setattr__ = spy
keeper = OBS[0]
for _ in range(3):  # three reopens
    for s in screws:  # Fasteners on the restored screws, before the keeper
        object.__setattr__(s, "Label", quirky(doc, s, f"{s.Diameter}x{s.Length}-Screw"))
    keeper.slotFinishRestoreDocument(doc)
    seen.append([s.Label for s in screws])
    doc.recompute()
    seen.append([s.Label for s in screws])
OUT["first"], OUT["seen"] = first, seen
OUT["kept_sets"] = [v for v in sets if not v.endswith("(relabelling)")]
''')
        self.assertEqual(out["first"], ["M8x25-Screw", "M8x25-Screw 2", "M8x25-Screw 3", "M8x25-Screw 4"])
        for s in out["seen"]:
            self.assertEqual(s, out["first"])
        # The keeper only ever set final labels (and temporary ones out of the way).
        self.assertTrue(set(out["kept_sets"]) <= set(out["first"]), out["kept_sets"])

    def test_bom_counts_every_screw_after_a_change(self):
        # Live: fastener_set {objects: four screws, length: 20}: fastener_list
        # listed four M8x20 but its bom said qty 3 (Fasteners' own count
        # leaves a hidden screw out).
        out = run(SETUP + r'''
screws = [api.add(doc, "ISO4762", "M8", 35, edges=[e])[0] for e in ("Body.Edge1", "Body.Edge2", "Body.Edge3", "Body.Edge4")]
more = [api.add(doc, "ISO4762", "M8", 35, edges=["Body.Edge5"])[0] for _ in range(2)]
screws[0].Visibility = False
api.change(doc, [s.Name for s in screws], length=20)
doc.recompute()
L = api.listing(doc)
OUT["bom"] = L["bom"]
OUT["labels"] = [f["label"] for f in L["fasteners"]]
OUT["hidden"] = [f.get("hidden") for f in L["fasteners"]]
''')
        self.assertEqual(out["bom"], [{"item": "ISO4762 Screw M8x20", "qty": 4}, {"item": "ISO4762 Screw M8x35", "qty": 2}])
        self.assertEqual(out["labels"][:4], ["M8x20-Screw", "M8x20-Screw 2", "M8x20-Screw 3", "M8x20-Screw 4"])
        self.assertEqual(out["hidden"][0], True)
