# SPDX-License-Identifier: LGPL-2.1-or-later
# Thread sizes (anywhere) and the thread tools (on a real FreeCAD).
import unittest

from _fc import AGENT, BEFORE_1_1, WHY_1_0, add_body, caller, server

import _threadtable
from workshop_make import threads as tt


class Table(unittest.TestCase):
    """Make's arithmetic on FreeCAD's rows (a stand-in for them here)."""

    def setUp(self):
        _threadtable.install()

    def tearDown(self):
        tt.use(None)

    def test_sizes(self):
        m6 = tt.lookup("M6")
        self.assertEqual((m6["major"], m6["pitch"], m6["tapDrill"]), (6.0, 1.0, 5.0))
        self.assertAlmostEqual(m6["minorInt"], 4.917, places=3)
        self.assertEqual(tt.lookup("M10x1.25")["series"], "metric-fine")
        self.assertEqual(tt.lookup("M8x1.25")["series"], "metric")
        u = tt.lookup("1/4-20")
        self.assertAlmostEqual(u["major"], 6.35, places=3)
        self.assertAlmostEqual(u["pitch"], 1.27, places=3)
        self.assertEqual(tt.lookup("1/4")["size"], "1/4-20")
        self.assertEqual(tt.lookup("#10-32")["series"], "unf")
        self.assertIsNone(tt.lookup("M7.3"))
        self.assertEqual(len(tt.table("metric")), 17)
        self.assertEqual((m6["freecad"], m6["source"]), ("M6x1.0", "FreeCAD"))
        self.assertEqual(m6["insert"]["hole"], 8.0)
        self.assertEqual(tt.lookup("M6x1.0"), m6)
        self.assertEqual((u["tpi"], u["tapDrillName"], u["freecad"]), (20, "#7", "1/4"))
        self.assertAlmostEqual(u["tapDrill"], 5.105, places=3)

    def test_unified_without_our_pitch(self):
        # A Unified size FreeCAD has and Make has no pitch for: listed by
        # FreeCAD's name, its pitch unknown rather than made up.
        tt.use(lambda: _threadtable.rows() + [{"series": "unc", "designation": "9/16", "major": 14.288, "tapDrill": 12.1}])
        r = tt.lookup("9/16")
        self.assertEqual((r["size"], r["pitch"], r["minorInt"]), ("9/16", None, None))
        self.assertTrue(tt.nearest(14.29, False))

    def test_no_freecad_no_table(self):
        tt.use(lambda: [])
        self.assertEqual(tt.table(), [])
        self.assertIsNone(tt.lookup("M6"))

    def test_extras_only_what_freecad_lacks(self):
        import json
        import os

        with open(os.path.join(os.path.dirname(tt.__file__), "data", "threads.json"), encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        for k, v in entries.items():
            self.assertIn(v["series"], ("unc", "unf"), k)
            self.assertFalse({"nominal", "pitch", "tapDrill", "majorInch", "tapDrillInch"} & set(v), k)

    def test_nearest_and_tie(self):
        n = tt.nearest(5.0, True)
        self.assertEqual((n[0]["size"], n[0]["as"]), ("M6", "tapDrill"))
        n = tt.nearest(9.95, False, 4)
        t = tt.tie(n)
        self.assertTrue(t)
        self.assertEqual({x["size"] for x in t}, {"M10", "M10x1.25", "M10x1"})
        self.assertIsNone(tt.tie(tt.nearest(4.2, True)))


@unittest.skipUnless(AGENT, "FreeCAD and Agent Link are not both importable here")
@unittest.skipIf(BEFORE_1_1, WHY_1_0 + " (its PartDesign Hole has no ThreadDiameter: no thread table to read)")
class Thread(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import FreeCAD
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        plate = Part.makeBox(20, 20, 10).cut(Part.makeCylinder(2.5, 10, FreeCAD.Vector(10, 10, 0)))
        add_body(cls.session, "Plate", plate)
        add_body(cls.session, "Wide", Part.makeBox(20, 20, 10).cut(Part.makeCylinder(3.5, 10, FreeCAD.Vector(10, 10, 0))))
        add_body(cls.session, "Rod", Part.makeCylinder(5, 30))

    def _pd_plate(self, label):
        """A PartDesign Body: a 20 x 20 x 10 box with a 5 mm hole through it."""
        import FreeCAD

        doc = self.session.doc
        body = doc.addObject("PartDesign::Body", "Body")
        body.Label = label
        box = body.newObject("PartDesign::AdditiveBox", "Box")
        box.Length, box.Width, box.Height = 20, 20, 10
        bore = body.newObject("PartDesign::SubtractiveCylinder", "Bore")
        bore.Radius, bore.Height = 2.5, 10
        bore.Placement = FreeCAD.Placement(FreeCAD.Vector(10, 10, 0), FreeCAD.Rotation())
        doc.recompute()
        return body

    def test_1_lookup(self):
        err, r = self.call("thread_lookup", {"size": "M3"})
        self.assertFalse(err, r)
        self.assertEqual(r["thread"]["tapDrill"], 2.5)
        err, r = self.call("thread_lookup", {"near": 6.3})
        self.assertIn("1/4-20", [x["size"] for x in r["threads"]])

    def test_2_identify(self):
        err, r = self.call("thread_identify", {"body": "Plate", "faces": {"near": [12.5, 10, 5]}})
        self.assertFalse(err, r)
        self.assertEqual(r["kind"], "hole")
        self.assertAlmostEqual(r["diameter"], 5.0, places=3)
        # M6's tap drill. Where another size of this table has the same
        # drill and its own pitch, the answer asks for the pitch instead.
        if r.get("needs") == "pitch":
            self.assertIn("M6", [x["size"] for x in r["nearest"]], r)
        else:
            self.assertEqual(r["best"]["size"], "M6", r)
        err, r = self.call("thread_identify", {"body": "Rod", "faces": {"near": [5, 0, 15]}})
        self.assertEqual(r["kind"], "shaft")
        self.assertEqual(r["needs"], "pitch")
        err, r = self.call("thread_identify", {"body": "Rod", "faces": {"near": [5, 0, 15]}, "pitch": 1.25})
        self.assertEqual(r["best"]["size"], "M10x1.25")

    def test_3_refusals(self):
        err, r = self.call("thread_cut", {"body": "Rod", "faces": {"near": [5, 0, 15]}, "size": "M10", "mode": "modelled"})
        self.assertTrue(err)
        self.assertEqual(r["error"]["code"], "unavailable")
        err, r = self.call("thread_cut", {"body": "Wide", "faces": {"near": [13.5, 10, 5]}, "size": "M6"})
        self.assertTrue(err)
        self.assertEqual(r["error"]["code"], "invalid_state")
        err, r = self.call("thread_identify", {"body": "Rod"})
        self.assertTrue(err)
        self.assertEqual(r["error"]["code"], "invalid_input")

    def test_35_scan_goes_to_a_reader(self):
        from workshop_make import fam_thread as thread

        saved = list(thread.SCAN_READERS)
        thread.SCAN_READERS.clear()
        try:
            err, r = self.call("thread_identify", {"scan": {"axis": {"origin": [0, 0, 0], "direction": [0, 0, 1], "radius": 3}}})
            self.assertTrue(err)
            self.assertEqual(r["error"]["code"], "unavailable")
            thread.SCAN_READERS.append(lambda s, a: {"verdict": "match", "best": {"designation": "M6×1", "family": "metric"}, "asked": a})
            err, r = self.call("thread_identify", {"scan": {"axis": {"radius": 3}}})
            self.assertFalse(err, r)
            self.assertEqual(r["from"], "scan")
            self.assertEqual("M6x1", r["threadSize"])
        finally:
            thread.SCAN_READERS[:] = saved

    def test_4_cut_modelled(self):
        before = self.session.body("Plate").Shape.Volume
        err, r = self.call("thread_cut", {"body": "Plate", "faces": {"near": [12.5, 10, 5]}, "size": "M6", "mode": "modelled"})
        print("\nthread:", r)
        self.assertFalse(err, r)
        self.assertGreater(r["removed"], 1.0)
        self.assertLess(self.session.body("Plate").Shape.Volume, before)
        self.assertEqual(len([o for o in self.session.doc.Objects if o.Name.startswith("AgentLinkThread")]), 0)
        self.assertEqual([o.Label for o in self.session.bodies()], ["Plate", "Wide", "Rod"])
        err, u = self.call("history_undo")
        self.assertAlmostEqual(self.session.body("Plate").Shape.Volume, before, places=3)

    def test_5_in_a_partdesign_body_it_is_a_hole_that_stays(self):
        # A shape written into a Body is gone at its next recompute (the
        # Body takes its tip's shape again): the thread was answered as cut
        # and was not there. In a Body it is FreeCAD's own Hole, kept.
        body = self._pd_plate("PdPlate")
        before = body.Shape.Volume
        self.assertAlmostEqual(before, 20 * 20 * 10 - 3.14159265 * 2.5 ** 2 * 10, delta=0.5)
        err, r = self.call("thread_cut", {"body": "PdPlate", "faces": {"near": [12.5, 10, 5]}, "size": "M6", "mode": "modelled"})
        self.assertFalse(err, r)
        self.assertEqual(r["route"], "PartDesign Hole")
        self.assertGreater(r["removed"], 1.0)
        self.session.doc.recompute()
        body.recompute(True)
        self.assertLess(body.Shape.Volume, before - 1.0)
        self.assertEqual(body.Tip.TypeId, "PartDesign::Hole")
        self.assertTrue(body.Tip.Threaded and body.Tip.ModelThread)
        self.assertEqual(body.Tip.Name, r["thread"]["feature"])
        self.assertEqual(len([o for o in self.session.doc.Objects if o.Name.startswith("AgentLinkThread")]), 0)
        err, u = self.call("history_undo")
        self.assertAlmostEqual(body.Shape.Volume, before, places=3)

    def test_6_cosmetic_in_a_moved_body(self):
        # The face is picked on the Body's shape (its Placement in it); the
        # Hole's sketch is in the Body's own frame.
        import FreeCAD

        body = self._pd_plate("PdMoved")
        body.Placement = FreeCAD.Placement(FreeCAD.Vector(100, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 90))
        self.session.doc.recompute()
        # (10, 10) of the Body is (100 - 10, 10) of the document after the quarter turn
        err, r = self.call("thread_cut", {"body": "PdMoved", "faces": {"near": [90, 12.5, 5]}, "size": "M6"})
        self.assertFalse(err, r)
        self.assertEqual((r["route"], r["thread"]["mode"]), ("PartDesign Hole", "cosmetic"))
        self.assertAlmostEqual(r["thread"]["holeDiameter"], 5.0, places=2)
        self.assertTrue(r["sound"], r)
        self.assertAlmostEqual(body.Tip.Shape.Volume, 20 * 20 * 10 - 3.14159265 * 2.5 ** 2 * 10, delta=0.5)

    def test_7_a_parametric_part_is_refused_not_lost(self):
        # A Part::Cut takes its own shape again at the recompute: refused,
        # with the plain copy to work on.
        doc = self.session.doc
        box = doc.addObject("Part::Box", "PBox")
        box.Length, box.Width, box.Height = 20, 20, 10
        cyl = doc.addObject("Part::Cylinder", "PCyl")
        cyl.Radius, cyl.Height = 2.5, 10
        import FreeCAD

        cyl.Placement = FreeCAD.Placement(FreeCAD.Vector(10, 10, 0), FreeCAD.Rotation())
        cut = doc.addObject("Part::Cut", "Drilled")
        cut.Base, cut.Tool = box, cyl
        cut.Label = "Drilled"
        doc.recompute()
        before = cut.Shape.Volume
        err, r = self.call("thread_cut", {"body": "Drilled", "faces": {"near": [12.5, 10, 5]}, "size": "M6", "mode": "modelled"})
        self.assertTrue(err, r)
        self.assertEqual(r["error"]["code"], "invalid_state")
        self.assertIn("part_transform", r["error"]["message"])
        self.assertAlmostEqual(cut.Shape.Volume, before, places=6)
        self.assertEqual(len([o for o in doc.Objects if o.Name.startswith("AgentLinkThread")]), 0)
        err, r = self.call("hw_hole", {"body": "Drilled", "kind": "clearance", "size": "M3", "at": [4, 4, 10]})
        self.assertTrue(err, r)
        self.assertEqual(r["error"]["code"], "invalid_state")
        self.assertIn("pd_clone", r["error"]["message"])


if __name__ == "__main__":
    unittest.main()
