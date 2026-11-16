# SPDX-License-Identifier: LGPL-2.1-or-later
# Make's hook services: mass and materials are Make's, offered under
# stable names for Agent Link's measure_mass and material_set to defer to.
import os
import unittest

from _stubs import ROOT, run


class Services(unittest.TestCase):
    def test_offered_under_stable_names(self):
        out = run(r'''
from workshop_make import services as S, records
given = {}
class Hooks:
    def provide(self, n, f): given[n] = f
OUT["names"] = S.provide(Hooks())
OUT["given"] = sorted(given)
d = Doc(("Box", "Lid"))
d.getObjectsByLabel = lambda l: []
OUT["set"] = S.material_set(d, ["Box"], "petg")
OUT["forget"] = S.material_set(d, ["Box"], "")
try:
    S.material_set(d, ["Box"], "unobtainium")
except Exception as e:
    OUT["bad"] = type(e).__name__
import workshop_make.handlers.mass as M
M.mass_properties = lambda s, a: {"seen": [s, a]}
OUT["mass"] = S.mass_properties("session", {"body": "Box"})
''')
        self.assertEqual(out["names"], ["mass_properties", "material_set"])
        self.assertEqual(out["given"], ["mass_properties", "material_set"])
        self.assertEqual(out["set"]["materials"], {"Box": "petg"})
        self.assertEqual(out["forget"]["materials"], {})
        self.assertEqual(out["bad"], "Refused")
        self.assertEqual(out["mass"], {"seen": ["session", {"body": "Box"}]})

    def test_readme_lists_them(self):
        with open(os.path.join(ROOT, "docs", "make.md"), encoding="utf-8") as f:  # Make's hook services table
            text = f.read()
        for n in ("`mass_properties`", "`material_set`", "`print_pauses`"):
            self.assertIn(f"| {n} |", text)


if __name__ == "__main__":
    unittest.main()
