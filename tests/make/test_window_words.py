# SPDX-License-Identifier: LGPL-2.1-or-later
# The window's words (Agent Link's echo asks a family's WORDS) for calls
# that gave only their tool's name or no figure in window review round 6:
# setup, part_spec, hw_hole, mass_properties, mass_target, mass_ballast,
# mass_calibrate, fastener_add.
import ast
import os
import unittest

from _stubs import run

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Words(unittest.TestCase):
    def test_each_with_its_figure(self):
        out = run(r'''
from workshop_make import words
W = words.words
OUT["mass"] = W("mass_properties", {}, {"bodies": [{"body": "Bracket", "mass": 17.8, "material": "pla"}]})
OUT["two"] = W("mass_properties", {}, {"bodies": [{"body": "A", "mass": 1.5}, {"body": "B", "mass": 2.5}]})
OUT["target"] = W("mass_target", {}, {"body": "B", "now": {"mass": 12.0}, "mass": {"target": 20, "off": -8}, "met": False, "ballast": {"mass": 8}})
OUT["met"] = W("mass_target", {}, {"body": "B", "now": {"mass": 20.0}, "met": True})
OUT["ballast"] = W("mass_ballast", {}, {"body": "B", "pockets": [{}, {}], "fill": {"what": "steel shot"}, "after": {"mass": 20.1}, "fillMass": 8.1, "cut": True})
OUT["cal"] = W("mass_calibrate", {}, {"scale": 1.04, "expected": 17.8, "weighed": 18.5, "for": "print setup P (s1)"})
OUT["hole"] = W("hw_hole", {}, {"size": "M3", "kind": "counterbore", "body": "Bracket", "depth": "through", "route": "PartDesign Hole"})
OUT["setup"] = W("setup", {}, {"added": {"name": "Print", "bodies": ["Bracket"]}})
OUT["spec"] = W("part_spec", {}, {"spec": {"load": "5 kg"}, "materials": {}})
OUT["other"] = W("dfm_check", {}, {"verdict": "printable"})
OUT["refused"] = W("mass_properties", {}, {"error": {"message": "no"}})
''')
        self.assertEqual(out["mass"], "Weighed Bracket: 17.8 g in PLA")
        self.assertEqual(out["two"], "Weighed 2 bodies: 4 g in all")
        self.assertEqual(out["target"], "B is 12 g, 8 g under the target 20 g; 8 g of ballast would do")
        self.assertEqual(out["met"], "B is 20 g: the target is met")
        self.assertEqual(out["ballast"], "Cut 2 ballast pockets in B: 8.1 g of steel shot, 20.1 g in all")
        self.assertEqual(out["cal"], "Calibrated print setup P (s1): weighed 18.5 g against 17.8 g (x1.04)")
        self.assertEqual(out["hole"], "M3 counterbored hole in Bracket, through")
        self.assertEqual(out["setup"], "Setup Print made with Bracket")
        self.assertEqual(out["spec"], "Part spec: load 5 kg")
        self.assertIsNone(out["other"])
        self.assertIsNone(out["refused"])

    def test_the_families_declare_them(self):
        for f in ("workshop_make/fam_make.py", "workshop_make/fam_mass.py", "workshop_make/fam_fits.py"):
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                self.assertIn("from .words import words as WORDS", fh.read(), f)
        tree = ast.parse(open(os.path.join(ROOT, "workshop_fasteners", "fam_fasteners.py"), encoding="utf-8").read())
        self.assertIn("WORDS", [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])


if __name__ == "__main__":
    unittest.main()
