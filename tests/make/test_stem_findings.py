# SPDX-License-Identifier: LGPL-2.1-or-later
# Found on a bike stem on the Mac (live test drive, 16 Nov 2026), with the
# Body inside an App::Part moved off the origin: hw_hole failed "Touched"
# with a recompute pending; its screw searched [75, 11.5, 4] for an edge at
# [67, 11.5, 12] (the Part's offset); mass_properties and the drawing's
# title block showed the material's UUID; drawing_make wrote an absolute
# file as one flattened name ending ".pdf.pdf" and called out none of two counterbored
# PartDesign Holes. On FreeCAD with Agent Link beside it.
import os
import tempfile
import unittest

from _fc import AGENT, caller, server


@unittest.skipUnless(AGENT, "FreeCAD and Agent Link are not both importable here")
class StemFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import FreeCAD

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        for n, a in (("doc_new", {"name": "Stem"}), ("pd_body_new", {"name": "Stem"}), ("sketch_new", {"plane": "XY", "name": "Base"}),
                     ("sketch_add", {"sketch": "Base", "items": [{"kind": "rectangle", "corner": [0, 0], "size": [80, 23]}]}),
                     ("pd_pad", {"sketch": "Base", "length": 20})):
            err, out = cls.call(n, a)
            assert not err, (n, out)
        doc = cls.session.doc
        body = doc.getObjectsByLabel("Stem")[0]
        part = doc.addObject("App::Part", "Assembly")
        part.addObject(body)
        part.Placement = FreeCAD.Placement(FreeCAD.Vector(8, 0, -8), FreeCAD.Rotation())
        doc.recompute()
        cls.body = body
        # The top face is at z = 20 in the Body, z = 12 in the document.
        cls.top = 12.0

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def test_1_hole_with_a_recompute_pending(self):
        doc = self.session.doc
        pad = doc.getObjectsByLabel("Pad")[0]
        pad.touch()
        frozen = hasattr(doc, "RecomputesFrozen")
        if frozen:
            doc.RecomputesFrozen = True
        try:
            h = self.ok("hw_hole", {"body": "Stem", "kind": "counterbore", "size": "M6", "at": [75, 11.5, self.top], "dir": "-z"})
        finally:
            if frozen:
                self.assertTrue(doc.RecomputesFrozen)  # left as the person had it
                doc.RecomputesFrozen = False
        self.assertEqual(h["route"], "PartDesign Hole")
        self.assertTrue(h["sound"], h)
        self.assertAlmostEqual(h["through"], 20, delta=0.05)  # read in the Body's frame
        self.ok("hw_hole", {"body": "Stem", "kind": "counterbore", "size": "M6", "at": [28, 11.5, self.top], "dir": "-z"})

    def test_1b_face_named_with_its_feature(self):
        # "Pocket 5.Face4": the face of a feature by its label (taken whole
        # as the face's name, the Hole stayed "Touched").
        top = self.ok("shape_query", {"body": "Stem", "kind": "face", "type": "plane", "normal": [0, 0, 1], "sort": "-area"})["items"][0]["ref"]
        tip = self.body.Tip.Label
        h = self.ok("hw_hole", {"body": "Stem", "kind": "clearance", "size": "M3", "at": [50, 4, self.top], "dir": "-z", "face": f"{tip}.{top}"})
        self.assertTrue(h["sound"], h)
        err, out = self.call("hw_hole", {"body": "Stem", "kind": "clearance", "size": "M3", "at": [50, 18, self.top], "dir": "-z", "face": "Nothing.Face1"})
        self.assertTrue(err)
        self.assertIn("Nothing", out["error"]["message"])

    def test_2_screw_search_in_the_bodys_frame(self):
        import FreeCAD

        from workshop_fasteners import api

        p, d = api.to_shape(self.body, FreeCAD.Vector(75, 11.5, self.top - 6.0), api._vec("-z"))
        self.assertAlmostEqual(p.x, 67, places=6)
        self.assertAlmostEqual(p.z, 20 - 6.0, places=6)
        idx, edge = api._circle_at(self.body.Shape, p, d)
        self.assertIsNotNone(idx, "the counterbore's floor is on the hole's axis")
        self.assertAlmostEqual(edge.Curve.Center.x, 67, places=3)
        self.assertLess(edge.Curve.Radius, 5)  # the bore's edge, not the counterbore's wall

    def test_3_material_by_name(self):
        lst = self.ok("material_list", {"words": "aluminium"}).get("materials") or self.ok("material_list", {"words": "aluminum"}).get("materials") or []
        lib = [m for m in lst if len(str(m.get("id", ""))) == 36]
        if not lib:
            self.skipTest("this FreeCAD has no material library")
        mid = lib[0]["id"]
        self.ok("material_set", {"bodies": ["Stem"], "id": mid})
        m = self.ok("mass_properties", {"body": "Stem"})
        row = m["bodies"][0]
        self.assertEqual(row["materialId"], mid)
        self.assertNotIn(mid, row["material"])
        self.assertIn(lib[0]["name"].split(" (")[0], row["material"])

    def test_4_drawing_to_an_absolute_file_with_hole_callouts(self):
        folder = os.path.join(tempfile.mkdtemp(), "stem-test")
        d = self.ok("drawing_make", {"bodies": ["Stem"], "file": os.path.join(folder, "Stem-drawing.pdf"), "holes": True, "page": False})
        for k, p in d["files"].items():
            self.assertEqual(p, os.path.join(folder, f"Stem-drawing.{k}"))
            self.assertTrue(os.path.isfile(p), p)
        pd = [h for h in d["holes"] if h.get("from") == "PartDesign Hole" and h.get("cut") == "counterbore"]
        self.assertEqual(len(pd), 1, d["holes"])
        self.assertEqual(pd[0]["count"], 2)
        self.assertIn("⌴⌀", pd[0]["label"])  # ISO 129: counterbore ⌀, depth ↧
        self.assertIn("THRU", pd[0]["label"])
        # The bores are not called out again from their faces.
        self.assertFalse([h for h in d["holes"] if h.get("from") == "its faces" and abs(h["diameter"] - pd[0]["diameter"]) < 0.05], d["holes"])
        if "materialId" in d["titleBlock"]:
            self.assertNotIn(d["titleBlock"]["materialId"].upper(), d["titleBlock"]["material"])


if __name__ == "__main__":
    unittest.main()
