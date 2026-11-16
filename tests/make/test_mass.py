# SPDX-License-Identifier: LGPL-2.1-or-later
# The mass tools on a real FreeCAD: skipped where FreeCAD cannot be imported.
import json
import unittest

from _fc import AGENT as HAVE, add_body, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Mass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        add_body(cls.session, "Block", Part.makeBox(40, 20, 10))
        add_body(cls.session, "Grip", Part.makeBox(60, 30, 20))
        add_body(cls.session, "Bar", Part.makeBox(60, 30, 20))
        cls.call("material_set", {"bodies": ["Block", "Grip", "Bar"], "id": "pla"})

    def test_1_solid(self):
        err, r = self.call("mass_properties", {"body": "Block"})
        self.assertFalse(err, r)
        b = r["bodies"][0]
        self.assertAlmostEqual(b["mass"], 9.92, places=2)
        self.assertEqual(b["com"], [20.0, 10.0, 5.0])
        ixx = 9.92 * (20 ** 2 + 10 ** 2) / 12
        self.assertAlmostEqual(b["inertia"]["aboutCom"][0][0], ixx, delta=0.5)
        self.assertEqual(b["as"], "solid")

    def test_2_printed_is_lighter(self):
        self.call("setup", {"action": "add", "type": "print", "bodies": ["Block"], "settings": {"walls": 2, "infill": 20}})
        err, r = self.call("mass_properties", {"body": "Block"})
        b = r["bodies"][0]
        print("\nprinted:", json.dumps(b))
        self.assertTrue(b["as"].startswith("printed"))
        self.assertLess(b["mass"], 9.92)
        self.assertGreater(b["mass"], 9.92 * 0.2)
        for got, want in zip(b["com"], [20, 10, 5]):
            self.assertAlmostEqual(got, want, delta=0.01)

    def test_3_target(self):
        err, t = self.call("mass_target", {"body": "Grip", "mass": 60, "com": [40, None, None]})
        self.assertFalse(err, t)
        self.assertFalse(t["met"])
        self.assertAlmostEqual(t["ballast"]["mass"], 60 - 36000 * 1.24 / 1000, places=1)
        err, t = self.call("mass_target", {"body": "Grip", "mass": 44.64})
        self.assertTrue(t["met"], t)

    def test_4_ballast_to_a_mass(self):
        err, b = self.call("mass_ballast", {"body": "Grip", "mass": 60, "fill": "steel-bb"})
        self.assertFalse(err, b)
        print("\nballast:", json.dumps(b))
        self.assertFalse(b["cut"])
        self.assertAlmostEqual(b["after"]["mass"], 60, delta=1.0)
        err, cut = self.call("mass_ballast", {"body": "Grip", "mass": 60, "fill": "steel-bb", "cut": True})
        self.assertFalse(err, cut)
        self.assertTrue(cut["cut"] and cut["sound"], cut)
        err, m = self.call("mass_properties", {"body": "Grip"})
        g = m["bodies"][0]
        self.assertAlmostEqual(g["mass"], 60, delta=1.0)
        self.assertEqual(g["encased"][0]["what"], "ballast")
        self.assertLess(g["volume"], 36000)

    def test_5_ballast_moves_the_centre(self):
        err, b = self.call("mass_ballast", {"body": "Bar", "com": [45, None, None], "fill": "tungsten", "maxPockets": 6})
        self.assertFalse(err, b)
        self.assertGreater(b["after"]["com"][0], b["before"]["com"][0] + 1.0)
        self.assertTrue(all(p["at"][0] > 30 for p in b["pockets"]), b["pockets"])
        err, no = self.call("mass_ballast", {"body": "Bar", "mass": 10})
        self.assertTrue(no)
        self.assertEqual(no["error"]["code"], "invalid_state")

    def test_2b_printed_mass_is_the_same_whatever_meshed_the_body_before(self):
        # Found live (16 Nov 2026): 17.10 g, then 17.15 g for one body. The
        # estimate tessellated the body's own shape, which keeps and reuses
        # the triangles of whatever meshed it before; it reads a copy now.
        import FreeCAD
        import Part

        rod = Part.makeBox(40, 20, 10).cut(Part.makeCylinder(4, 10, FreeCAD.Vector(12, 10, 0)))
        o = add_body(self.session, "Rod", rod)
        self.call("material_set", {"bodies": ["Rod"], "id": "pla"})
        self.call("setup", {"action": "add", "type": "print", "bodies": ["Rod"], "settings": {"walls": 2, "infill": 20}})
        first = self.call("mass_properties", {"body": "Rod"})[1]["bodies"][0]
        o.Shape.tessellate(0.001)   # a finer mesh left on the body's shape, as a wall check leaves one
        again = self.call("mass_properties", {"body": "Rod"})[1]["bodies"][0]
        self.assertEqual((first["mass"], first["inertia"]), (again["mass"], again["inertia"]))

    def test_6_no_pocket_through_a_hole(self):
        # Found live (16 Nov 2026): on a bracket with screw holes two of ten
        # pockets were laid through an M3 hole (its axis 2.8 mm from the
        # pocket's, between the nine points tried a level) and the answer
        # said closed pockets, sound. Every pocket and its wall is material.
        import FreeCAD
        import Part

        plate = Part.makeBox(80, 40, 10)
        holes = [(70, 30, 1.8), (50, 20, 1.6), (10, 20, 3.3)]
        for x, y, r in holes:
            plate = plate.cut(Part.makeCylinder(r, 10, FreeCAD.Vector(x, y, 0)))
        add_body(self.session, "Holed", plate)
        self.call("material_set", {"bodies": ["Holed"], "id": "pla"})
        err, b = self.call("mass_ballast", {"body": "Holed", "mass": 80, "diameter": 8})
        self.assertFalse(err, b)
        self.assertTrue(b["pockets"])
        wall = b["minWall"]
        for p in b["pockets"]:
            for x, y, r in holes:
                gap = ((p["at"][0] - x) ** 2 + (p["at"][1] - y) ** 2) ** 0.5 - p["diameter"] / 2 - r
                self.assertGreaterEqual(gap, wall - 1e-6, (p, (x, y, r)))
        self.assertGreater(b["leftOut"]["places"], 0)
        err, cut = self.call("mass_ballast", {"body": "Holed", "mass": 80, "diameter": 8, "cut": True})
        self.assertFalse(err, cut)
        removed = sum(3.141592653589793 * (p["diameter"] / 2) ** 2 * p["depth"] for p in cut["pockets"])
        err, m = self.call("mass_properties", {"body": "Holed"})
        self.assertAlmostEqual(plate.Volume - m["bodies"][0]["volume"], removed, delta=0.5)   # every pocket whole, none in a hole

    def test_9_calibrate_to_a_weighed_print(self):
        import Part

        add_body(self.session, "Coupon", Part.makeBox(20, 20, 20))
        self.call("material_set", {"bodies": ["Coupon"], "id": "pla"})
        self.call("setup", {"action": "add", "type": "print", "bodies": ["Coupon"], "settings": {"walls": 2, "infill": 15}})
        _e, before = self.call("mass_properties", {"body": "Coupon"})
        expected = before["bodies"][0]["mass"]
        err, cal = self.call("mass_calibrate", {"body": "Coupon", "grams": round(expected * 1.1, 2)})
        self.assertFalse(err, cal)
        self.assertAlmostEqual(cal["scale"], 1.1, delta=0.01)
        _e, after = self.call("mass_properties", {"body": "Coupon"})
        self.assertAlmostEqual(after["bodies"][0]["mass"], expected * 1.1, delta=0.02)
        self.assertIn("calibrated", after["bodies"][0]["as"])
        err, far = self.call("mass_calibrate", {"body": "Coupon", "grams": expected * 10})
        self.assertTrue(err)
        self.call("mass_calibrate", {"body": "Coupon", "reset": True})
        _e, back = self.call("mass_properties", {"body": "Coupon"})
        self.assertAlmostEqual(back["bodies"][0]["mass"], expected, delta=0.01)


if __name__ == "__main__":
    unittest.main()
