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

    def test_health_reading(self):
        # Make's reading for Agent Link's shared health check: a setup that
        # names a body gone from the document, an encased part whose pocket
        # is solid again. Amber, never red, each with the call to run.
        out = run(r'''
import types
from workshop_make import services as S, records
F = sys.modules["FreeCAD"]
F.Vector = lambda *a: tuple(a)
class Shape:
    def __init__(self, solid_at): self.solid_at = solid_at
    def isInside(self, p, tol, face): return tuple(p) in self.solid_at
class O:
    def __init__(self, label, shape=None): self.Label, self.Shape = label, shape
d = Doc(("Box",))
box = O("Box", Shape({(1, 1, 1)}))
d.Objects = [box]
ses = types.SimpleNamespace(doc=d)
OUT["clean"] = S.health_reading(ses, "setup", [])
records.save_setups(d, [{"id": "S1", "type": "print", "name": "Print", "bodies": ["Box", "Lid"]}])
records.write(d, "embeds", {"Box": [{"id": "E1", "centre": [1, 1, 1]}, {"id": "E2", "centre": [5, 5, 5]}]})
OUT["found"] = S.health_reading(ses, "part_boolean", [box])
OUT["untouched"] = S.health_reading(ses, "part_boolean", [])
OUT["no_doc"] = S.health_reading(types.SimpleNamespace(doc=None), "x", [])
''')
        self.assertEqual(out["clean"], [])
        self.assertEqual(out["no_doc"], [])
        self.assertEqual(len(out["found"]), 2)
        self.assertIn("Lid", out["found"][0]["line"])
        self.assertIn("E1", out["found"][1]["line"])
        self.assertNotIn("E2", out["found"][1]["line"])
        self.assertTrue(all(x["red"] is False for x in out["found"]))
        self.assertEqual(len(out["untouched"]), 1)  # the setup's line only: embeds are read on what the call recomputed

    def test_readme_lists_them(self):
        with open(os.path.join(ROOT, "docs", "make.md"), encoding="utf-8") as f:  # Make's hook services table
            text = f.read()
        for n in ("`mass_properties`", "`material_set`", "`print_pauses`"):
            self.assertIn(f"| {n} |", text)


if __name__ == "__main__":
    unittest.main()
