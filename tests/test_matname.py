# SPDX-License-Identifier: LGPL-2.1-or-later
# A material's name from whatever id a part carries (workshop/matname.py):
# the mass report and the drawing's title block showed FreeCAD's library
# card by its UUID ("68b152b2-…"). Pure: no FreeCAD here, so a library id
# nothing can look up is said as a card, never shown bare.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from workshop import matname  # noqa: E402

UUID = "68b152b2-b4c5-4d3e-8f00-1a2b3c4d5e6f"


class MaterialNames(unittest.TestCase):
    def test_ids(self):
        self.assertTrue(matname.is_uuid(UUID))
        self.assertFalse(matname.is_uuid("pla"))

    def test_shown(self):
        self.assertEqual(matname.shown("pla"), "PLA")
        self.assertEqual(matname.shown(""), "not set")
        u = matname.shown(UUID)
        self.assertNotEqual(u, UUID)
        self.assertIn("68b152b2", u)
        self.assertIn("card", u)

    def test_results_and_mass_words(self):
        from workshop_make import results

        self.assertNotIn(UUID, results.material_name(UUID))
        self.assertTrue(results.material_name("abs (assumed: material_set records it)").startswith("ABS (assumed"))


if __name__ == "__main__":
    unittest.main()
