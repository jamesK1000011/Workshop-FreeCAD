# SPDX-License-Identifier: LGPL-2.1-or-later
# The Parts add-on with no agent: workshop_parts.api as a macro or a command
# calls it. Skipped where FreeCAD cannot be imported.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..")]
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD

    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Api(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("parts_api")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def test_no_agent_link_needed(self):
        # In a fresh Python: other tests here may have loaded Agent Link.
        import subprocess

        code = "import sys, FreeCAD, workshop_parts.api; print('agentlink' in sys.modules)"
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)})
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ["False"], r.stderr[-500:])

    def test_bin_made_and_measured(self):
        from workshop_parts import api

        m = api.make(None, "gridfinity_bin", {"x": 2, "y": 1, "units": 3}, measure=True)
        self.assertFalse(m["made"])
        self.assertAlmostEqual(m["parts"][0]["size"][0], 83.5, delta=0.6)
        out = api.make(self.doc, "gridfinity_bin", {"x": 1, "y": 1, "magnets": True})
        self.assertEqual(len(out["bodies"]), 1)
        self.assertTrue(all(out["sound"].values()))
        self.assertEqual(out["encased"]["count"], 4)

    def test_box_and_lid(self):
        from workshop_parts import api

        out = api.make(self.doc, "project_box", {"length": 80, "width": 50, "height": 30}, name="Case")
        self.assertEqual(out["bodies"], ["Case", "Case lid"])
        self.assertEqual(out["printerFit"].split(" ")[0], "none")

    def test_refusals_say_the_range(self):
        from workshop_parts.refusal import Refused
        from workshop_parts import api

        with self.assertRaises(Refused) as e:
            api.make(None, "gridfinity_bin", {"x": 99}, measure=True)
        self.assertIn("1 to 10", e.exception.message)
        with self.assertRaises(Refused):
            api.make(None, "spaceship", {}, measure=True)

    def test_records_fit_used(self):
        from workshop_parts import records
        from workshop_parts import api

        records.write(self.doc, "fit", {"hole": 0.35, "shaft": 0.05})
        cal, said = api.calibration(self.doc)
        self.assertEqual((cal["hole"], said), (0.35, "calibrated"))


if __name__ == "__main__":
    unittest.main()
