# SPDX-License-Identifier: LGPL-2.1-or-later
# Print-aware strength on Agent Link's FEM tools: buildDir recorded on the
# study, the tension across the layers judged against half the yield. A PLA
# cantilever (needs FreeCAD, Agent Link, ccx and gmsh for the solve).
import shutil
import unittest

from _fc import AGENT, add_body, caller, server


@unittest.skipUnless(AGENT, "FreeCAD and Agent Link are not both importable here")
class Printed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import Part

        cls.session, srv = server()
        cls.call = staticmethod(caller(srv))
        add_body(cls.session, "Beam", Part.makeBox(100, 10, 10))
        cls.call("material_set", {"id": "pla"})

    def test_1_setup_records_the_build_direction(self):
        err, r = self.call("fea_setup", {"body": "Beam", "mesh": 2.5, "buildDir": "+z"})
        self.assertFalse(err, r)
        self.assertEqual(r["study"]["buildDir"], [0, 0, 1])
        self.assertIn("across the layers", r["printed"])
        err, e = self.call("fea_setup", {"body": "Beam", "buildDir": "up"})
        self.assertTrue(err)
        self.assertIn("buildDir", e["error"]["message"])

    def test_2_across_layers(self):
        self.call("fea_setup", {"body": "Beam", "mesh": 2.5, "buildDir": "+z"})
        self.call("fea_hold", {"faces": {"normal": [-1, 0, 0], "x": 0}})
        self.call("fea_load", {"faces": {"near": [100, 5, 5]}, "force": [0, 0, -10]})
        if not (shutil.which("ccx") and shutil.which("gmsh")):
            self.skipTest("ccx and gmsh are not on PATH")
        err, r = self.call("fea_solve")
        self.assertFalse(err, r)
        self.assertIn("acrossLayers", r)
        self.assertEqual(r["acrossLayers"]["factor"], 0.5)
        self.assertIn("face", r["acrossLayers"])
        # Bending a cantilever along x puts no tension across z-layers to
        # speak of: far safer across than the von Mises safety would say.
        self.assertTrue(r["acrossLayers"]["safety"] is None or r["acrossLayers"]["safety"] > 0)


if __name__ == "__main__":
    unittest.main()
