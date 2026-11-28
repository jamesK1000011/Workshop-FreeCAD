# SPDX-License-Identifier: LGPL-2.1-or-later
# mass_properties names the material as a person reads it: a display name,
# "(assumed; set the material to change it)" with none set, the id kept
# for agents.
import unittest

from _stubs import run


class Words(unittest.TestCase):
    def test_display_names(self):
        out = run(r'''
import types
from workshop_make.handlers import mass as M
M._r = lambda x, n=2: round(x, n)
M._vl = lambda v: list(v)
M._principal = lambda I: None
o = types.SimpleNamespace(Label="Box")
def p(mid, set_):
    return {"mass": 12.0, "com": (0, 0, 0), "volume": 1000.0, "material": {"id": mid, "density": 1.24}, "materialSet": set_,
            "as": "solid", "I": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "encased": []}
OUT["assumed"] = M.report(o, p("pla", False))
OUT["set"] = M.report(o, p("petg", True))
OUT["card"] = M.report(o, p("Steel-Generic", True))
''')
        self.assertEqual((out["assumed"]["material"], out["assumed"]["materialAssumed"]), ("PLA", True))
        self.assertEqual(out["assumed"]["materialId"], "pla")
        self.assertEqual(out["set"]["material"], "PETG")
        self.assertEqual(out["card"]["material"], "Steel-Generic")
        self.assertNotIn("material_set", str(out))


if __name__ == "__main__":
    unittest.main()
