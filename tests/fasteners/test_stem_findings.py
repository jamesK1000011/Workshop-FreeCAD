# SPDX-License-Identifier: LGPL-2.1-or-later
# Found putting screws in a bike stem on the Mac (live test drive, 16 Nov
# 2026): fastener_add { edges: [{ body, near }] } crashed on its own error
# path (o.Label on None); an M6 asked for on a counterbore's 15.2 mm wall
# came out M14; hw_hole's screw searched off the hole's axis. On the
# reference clone of Fasteners Workbench (FASTENERS_SRC, else /tmp/fwb) with
# stand-ins for FreeCAD, as test_bridge.py.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _fwb import have_fasteners, run  # noqa: E402

PLATE = r'''
from workshop_fasteners import api, fs
doc = Doc()
# A stem's counterbored M6 hole down from z=20: the counterbore's wall edge
# (15.2 mm) at the top, its floor's two circles at z=12.4 (the wall's,
# 15.2 mm, and the bore's, 6.6 mm), the bore's bottom edge at z=0; a hole
# beside it, 3.4 mm.
doc.Objects.append(Plate("Stem", [Edge(Vec(67, 11.5, 20), Vec(0, 0, 1), 7.6), Edge(Vec(67, 11.5, 12.4), Vec(0, 0, 1), 7.6),
                                  Edge(Vec(67, 11.5, 12.4), Vec(0, 0, -1), 3.3), Edge(Vec(67, 11.5, 0), Vec(0, 0, 1), 3.3),
                                  Edge(Vec(20, 11.5, 20), Vec(0, 0, 1), 1.7)]))
'''


@unittest.skipUnless(have_fasteners(), "the Fasteners Workbench reference clone is not here")
class StemFindings(unittest.TestCase):
    def test_edges_by_body_and_near(self):
        out = run(PLATE + r'''
OUT["picked"] = api.element(doc, {"body": "Stem", "near": [20, 13.2, 20]})
for bad in ({"near": [67, 11.5, 19.6]}, {"body": "Stem", "near": [0, 0, 50]}, {"body": "Stem"}, {"body": None, "near": [1, 2, 3]}):
    try:
        api.element(doc, bad)
    except fs.Missing as e:
        OUT.setdefault("refused", []).append([e.code, e.message])
''')
        self.assertEqual(out["picked"][1], "Edge5")
        codes = [c for c, _ in out["refused"]]
        self.assertEqual(codes, ["invalid_input", "not_found", "invalid_input", "invalid_input"])
        self.assertIn("body", out["refused"][0][1])
        self.assertIn("Edge", out["refused"][1][1])  # the nearest round edges named

    def test_explicit_size_wins_and_moves_off_a_counterbore_wall(self):
        out = run(PLATE + r'''
s = api.add(doc, "ISO4762", "M6", 20, edges=[{"body": "Stem", "near": [67 + 7.6, 11.5, 19.6]}])
OUT["made"] = [api.describe(o) for o in s]
plate = doc.Objects[0]
OUT["fits"] = [api.bore_edge(plate, "Edge5", 3.0), api.bore_edge(plate, "Edge1", 6.0), api.bore_edge(plate, "Edge1", 4.0)]
''')
        m = out["made"][0]
        self.assertEqual(m["size"], "M6")
        self.assertEqual(m["attachedTo"], "Stem.Edge3")  # the bore's edge at the floor, not the wall's
        self.assertEqual(m["edgeDiameter"], 6.6)
        self.assertIn("counterbore", m["attachNote"])
        # An edge that fits stays; a wall with no bore for that size stays too.
        self.assertEqual(out["fits"], [None, "Edge3", None])

    def test_hole_screw_searches_along_the_axis(self):
        out = run(PLATE + r'''
# The counterbore's depth read a little short: still on the hole's axis.
OUT["cb"] = api.hole_screw(doc, {"kind": "counterbore", "size": "M6", "at": [67, 11.5, 20], "dir": "-z"}, {"body": "Stem", "through": 20, "sizes": {"cutDepth": 7.0}}, True)
OUT["off"] = api.hole_screw(doc, {"kind": "clearance", "size": "M6", "at": [75, 11.5, 4], "dir": "-z"}, {"body": "Stem", "through": 20}, True)
''')
        self.assertEqual(out["cb"]["screw"]["attachedTo"], "Stem.Edge3")
        self.assertEqual("noEdge", out["off"]["screwNote"]["reason"])


if __name__ == "__main__":
    unittest.main()
