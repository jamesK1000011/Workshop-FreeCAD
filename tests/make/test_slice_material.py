# SPDX-License-Identifier: LGPL-2.1-or-later
# slice and a part in no printing filament: the refusal names the exact
# material_set call (with the body's name), and slice's material slices in a
# filament this time only, recording nothing. Stand-ins for the slicer, the
# document's records and the material family; no FreeCAD needed.
import unittest

from _stubs import run

SETUP = r'''
import os, tempfile
from workshop_make.handlers import make as M
from workshop_make.handlers import slicing as SW
from workshop_make import records as store
recorded = {"Bracket": "steel-1018"}
writes = []
store.materials = lambda doc: dict(recorded)
store.setup_of = lambda doc, label, kind: {"id": "S1", "name": "Print", "type": "print", "bodies": [label], "layerHeight": 0.2}
store.write = lambda *a, **k: writes.append(a)
class Fam:
    def card(self, doc, mid):
        return {"density": 7.87, "name": "Steel 1018"} if mid == "steel-1018" else None
M.matfam = Fam()
M.encased = lambda s, label: []
class Body:
    Label = "Bracket"
    Shape = None
class S:
    doc = object()
    server = None
    out_dir = tempfile.mkdtemp()
    def body(self, label):
        return Body()
used = {}
class Slicer:
    def slice_stl(self, stl, gcode, settings):
        used.update(settings)
        open(gcode, "w").write(";LAYER_CHANGE\n")
        return "/bin/prusa-slicer"
    def read_gcode(self, gcode):
        return {"layers": 1}
    def insert_pauses(self, *a):
        return []
M.orcalib.module = lambda name: Slicer()
def call(a):
    try:
        return {"ok": M.slice(S(), a)}
    except Exception as e:  # noqa: BLE001
        return {"err": [getattr(e, "code", type(e).__name__), str(e)]}
'''


class SliceMaterial(unittest.TestCase):
    def test_refusal_names_the_exact_call(self):
        out = run(SETUP + r'''
OUT["r"] = call({"body": "Bracket"})
OUT["used"] = used
''')
        code, msg = out["r"]["err"]
        self.assertEqual(code, "invalid_state")
        self.assertIn('material_set { bodies: ["Bracket"], id: "petg" }', msg)
        self.assertIn('slice { body: "Bracket", material: "petg" }', msg)
        self.assertIn("Steel 1018", msg)
        self.assertEqual(out["used"], {})
        # The person reads it without the tool syntax.
        said = run("from workshop_make import results as R\nOUT['s'] = R.person_error({'error': {'message': %r}})" % msg)["s"]
        self.assertEqual(said, "Bracket is in Steel 1018, not a printing filament.")

    def test_material_for_this_slice_only(self):
        out = run(SETUP + r'''
OUT["r"] = call({"body": "Bracket", "material": "PETG"})
OUT["used"] = {k: used.get(k) for k in ("filament", "density")}
OUT["recorded"], OUT["writes"] = recorded, writes
OUT["bad"] = call({"body": "Bracket", "material": "steel-1018"})
OUT["cf"] = call({"body": "Bracket", "material": "pa6-cf"})
OUT["cf_used"] = used.get("filament")
''')
        r = out["r"]["ok"]
        self.assertEqual(out["used"]["filament"], "petg")
        self.assertGreater(out["used"]["density"], 1.0)
        self.assertLess(out["used"]["density"], 2.0)
        self.assertIn("this slice only", r["material"])
        self.assertEqual(out["recorded"], {"Bracket": "steel-1018"})
        self.assertEqual(out["writes"], [])
        code, msg = out["bad"]["err"]
        self.assertEqual(code, "invalid_input")
        self.assertIn("pla", msg)
        self.assertEqual(out["cf_used"], "pa6")

    def test_body_in_a_filament_needs_no_material(self):
        out = run(SETUP + r'''
recorded["Bracket"] = "abs"
OUT["r"] = call({"body": "Bracket"})
OUT["f"] = used.get("filament")
''')
        self.assertNotIn("material", out["r"]["ok"])
        self.assertEqual(out["f"], "abs")

    def test_slice_with_material_this_slice_only(self):
        out = run(SETUP + r'''
class Cli:
    NAMES = ("prusaslicer", "orcaslicer", "bambustudio")
    PAUSE = {"prusaslicer": "M601"}
    LAST = {}
    def slice_with(self, name, stl, gcode, settings, profiles, options=None):
        used.update(settings)
        open(gcode, "w").write(";LAYER_CHANGE\\n")
        return "/bin/prusa-slicer", "written"
    def read_gcode(self, gcode):
        return {"layers": 1}
SW.slicers = Cli()
SW.pauses_for = lambda s, o, setup: []
try:
    OUT["r"] = SW.slice_with(S(), {"body": "Bracket", "material": "tpu-95a"})
except Exception as e:
    OUT["r"] = repr(e)
OUT["f"] = used.get("filament")
OUT["recorded"], OUT["writes"] = recorded, writes
try:
    SW.slice_with(S(), {"body": "Bracket", "material": "oak"})
except Exception as e:
    OUT["bad"] = getattr(e, "code", repr(e))
''')
        self.assertIn("this slice only", out["r"]["material"])
        self.assertEqual(out["f"], "tpu")
        self.assertEqual(out["recorded"], {"Bracket": "steel-1018"})
        self.assertEqual(out["writes"], [])
        self.assertEqual(out["bad"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
