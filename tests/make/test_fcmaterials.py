# SPDX-License-Identifier: LGPL-2.1-or-later
# The Materials tab on FreeCAD's own library: a metal's E and yield only
# from FreeCAD's card, Give to Part setting FreeCAD's ShapeMaterial so
# Inspect Material agrees, a material set with FreeCAD's own command read
# back, and the library's browsing left to FreeCAD's Material editor. A
# stand-in library (FreeCAD's Materials module) here.
import unittest

from _stubs import run

LIBRARY = r'''
import types
class Mat:
    def __init__(self, name, uuid, **props):
        self.Name, self.UUID, self.PhysicalProperties = name, uuid, props
    def hasPhysicalProperty(self, n): return n in self.PhysicalProperties
    def getPhysicalValue(self, n): return self.PhysicalProperties.get(n)
DEFAULT = Mat("Default", "default-uuid", Density="7800 kg/m^3")
LIB = {m.UUID: m for m in (
    DEFAULT,
    Mat("Steel-Generic", "u-steel", Density="7900 kg/m^3", YoungsModulus="210 GPa", YieldStrength="250 MPa"),
    Mat("Aluminum-6061-T6", "u-al", Density="2700 kg/m^3", YoungsModulus="69000 MPa", YieldStrength="240 MPa"),
    Mat("Copper-Generic", "u-cu", Density="8960 kg/m^3"),
    Mat("PLA-Generic", "u-pla", Density="1240 kg/m^3"),
    Mat("PETG (printed)", "u-petg", Density="1270 kg/m^3"),
)}
class Manager:
    Materials = LIB
    def defaultMaterial(self): return DEFAULT
Materials = types.ModuleType("Materials")
Materials.MaterialManager = Manager
sys.modules["Materials"] = Materials
class Part:
    def __init__(self, label): self.Label, self.Name, self.ShapeMaterial = label, label, DEFAULT
'''


class Library(unittest.TestCase):
    def test_reading_freecads_cards(self):
        out = run(LIBRARY + r'''
from workshop_make import fcmaterials as F
OUT["q"] = [F.quantity("210 GPa", F.PA_PER), F.quantity("250 MPa", F.PA_PER), F.quantity("7900 kg/m^3", F.DENSITY_PER),
            F.quantity("12 furlongs", F.PA_PER), F.quantity(None, F.PA_PER)]
names = list(F.cards())
OUT["match"] = [F.match(names, ["Steel-Generic"]), F.match(names, ["Aluminum-Generic", "Aluminum-6061-T6"]), F.match(names, ["Titanium"])]
OUT["steel"] = F.metal(["Steel-Generic"])
OUT["copper"] = F.metal(["Copper-Generic"])
OUT["none"] = F.metal(["Titanium"])
OUT["fil"] = [F.filament_card("pla"), F.filament_card("petg", "PETG (printed)"), F.filament_card("asa", "ASA (printed)")]
''')
        self.assertEqual(out["q"][:3], [210000.0, 250.0, 7.9])
        self.assertEqual(out["q"][3:], [None, None])
        self.assertEqual(out["match"], ["Steel-Generic", "Aluminum-6061-T6", None])
        self.assertEqual(out["steel"], {"card": "Steel-Generic", "density": 7.9, "E": 210000.0, "yield": 250.0})
        # A card without E or yield gives none; no card, no figures at all.
        self.assertEqual(out["copper"], {"card": "Copper-Generic", "density": 8.96})
        self.assertIsNone(out["none"])
        # The person's own card (named as the filament) wins; no card, None.
        self.assertEqual(out["fil"], ["PLA-Generic", "PETG (printed)", None])

    def test_no_materials_module(self):
        out = run(r'''
from workshop_make import fcmaterials as F
class P: Label = "Box"
OUT["cards"] = F.cards()
OUT["give"] = F.give(P(), "pla")
OUT["of"] = F.of(P())
''')
        self.assertEqual(out["cards"], {})
        self.assertIsNone(out["give"][0])
        self.assertEqual(out["give"][1], {"reason": "noShapeMaterial"})
        self.assertIsNone(out["of"])


# FreeCAD 1.1's own manager (src/Mod/Material/App/MaterialManagerPyImp.cpp):
# getMaterial(uuid), no defaultMaterial(); and its Default card as shipped
# (Resources/Materials/Standard/Default.FCMat: 1 kg/m^3).
LIBRARY_11 = LIBRARY + r'''
REAL = Mat("Default", "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb", Density="1 kg/m^3")
LIB[REAL.UUID] = REAL
class Manager11:
    Materials = LIB
    def getMaterial(self, uuid):
        if uuid not in LIB:
            raise LookupError("Material not found")
        return LIB[uuid]
Materials.MaterialManager = Manager11
'''


class DefaultMaterial(unittest.TestCase):
    """Found live (16 Nov 2026, FreeCAD 1.1.3): part_review weighed a body
    with no material at FreeCAD's Default card's 1 kg/m^3 (a 30 cm3 bin:
    0.02 g, so "mass 3.4" was its magnets alone, material "Default"),
    because the default was asked of a method FreeCAD 1.1 does not have."""

    def test_the_default_card_is_no_material(self):
        out = run(LIBRARY_11 + r'''
from workshop_make import fcmaterials as F
p = Part("Bin"); p.ShapeMaterial = REAL
OUT["of"] = F.of(p)
p.ShapeMaterial = LIB["u-steel"]
OUT["steel"] = F.of(p)
OUT["cleared"] = F.clear(p)
OUT["after"] = [p.ShapeMaterial.Name, p.ShapeMaterial.UUID]
OUT["uuid"] = F._default_uuid()
''')
        self.assertIsNone(out["of"])
        self.assertEqual(out["steel"]["card"], "Steel-Generic")
        self.assertTrue(out["cleared"])
        self.assertEqual(out["after"], ["Default", "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"])
        self.assertEqual(out["uuid"], "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb")


class Tab(unittest.TestCase):
    def test_metals_figures_are_freecads(self):
        out = run(LIBRARY + r'''
from workshop_make import panel as P
OUT["hits"] = {h[0]: [h[3], h[4], h[5], h[6]] for h in P.material_hits("")}
OUT["what"] = [h[7] for h in P.material_hits("steel") if h[0] == "steel"]
''')
        h = out["hits"]
        self.assertEqual(h["steel"], [7.9, 210000.0, 250.0, False])
        self.assertEqual(h["aluminum"], [2.7, 69000.0, 240.0, False])
        # FreeCAD has no card here: blank, never a number of Make's own.
        self.assertEqual(h["titanium"], [None, None, None, False])
        self.assertEqual(h["acrylic"], [None, None, None, False])
        self.assertIn("Steel-Generic", out["what"][0])
        self.assertTrue(h["pla"][3])

    def test_give_sets_freecads_material_and_forget_clears_it(self):
        out = run(LIBRARY + r'''
from workshop_make import api, panel as P
box, lid = Part("Box"), Part("Lid")
class D(Doc):
    def getObjectsByLabel(self, l): return [o for o in (box, lid) if o.Label == l]
d = D()
OUT["give"] = api.freecad_material(d, ["Box"], "pla")
OUT["box"] = box.ShapeMaterial.Name
OUT["asa"] = api.freecad_material(d, ["Lid"], "asa")
OUT["lid"] = lid.ShapeMaterial.Name
OUT["petg"] = api.freecad_material(d, ["Lid"], "petg")
OUT["lid_petg"] = lid.ShapeMaterial.Name
lid.ShapeMaterial = DEFAULT
OUT["forget"] = api.freecad_material(d, ["Box"], None)
OUT["box_after"] = box.ShapeMaterial.Name
# A material set with FreeCAD's own command is what the tab shows.
lid.ShapeMaterial = Materials.MaterialManager.Materials["u-steel"]
d.Objects = [box, lid]
from workshop_make import runner
runner.bodies_in = lambda doc: [box, lid]
OUT["rows"] = P.material_rows(d)
''')
        self.assertEqual(out["give"], {"Box": {"card": "PLA-Generic"}})
        self.assertEqual(out["box"], "PLA-Generic")
        self.assertEqual("noCard", out["asa"]["Lid"]["why"]["reason"])
        self.assertEqual(out["lid"], "Default")
        self.assertEqual((out["petg"], out["lid_petg"]), ({"Lid": {"card": "PETG (printed)"}}, "PETG (printed)"))
        self.assertEqual(out["forget"], {"Box": {"card": "FreeCAD's default"}})
        self.assertEqual(out["box_after"], "Default")
        self.assertEqual(out["rows"], [["Box", "PLA (assumed)", "1.24"], ["Lid", "Steel-Generic (FreeCAD)", "7.9"]])

    def test_buttons_open_freecads_own_commands(self):
        out = run(LIBRARY + r'''
import types
from workshop_make import panel as P
ran, picked = [], []
sys.modules["FreeCADGui"].runCommand = ran.append
sys.modules["FreeCADGui"].Selection = types.SimpleNamespace(getSelection=lambda: [], clearSelection=lambda: picked.append("clear"),
                                                            addSelection=lambda o: picked.append(o.Label), removeSelection=lambda *a: None)
box = Part("Box")
class D(Doc):
    def getObjectsByLabel(self, l): return [box] if l == "Box" else []
d = D()
t = P.MaterialsTab(runner=lambda tool, args: (True, {}), doc_fn=lambda: d)
t.library()
t.parts.cur = P.item(["Box", "PLA (assumed)", "1.24"])
t.set_freecad()
OUT["ran"], OUT["picked"] = ran, picked
t.parts.cur = P.item(["Box", "PLA (assumed)", "1.24"])
t.hits.cur = P.item(["Steel", "Metal"])
t.hits.cur.setData(1, P.QtCore.Qt.UserRole, False)
t.give()
OUT["shop"] = t.msg.text()
''')
        self.assertEqual(out["ran"], ["Material_Edit", "Std_SetMaterial"])
        self.assertEqual(out["picked"], ["clear", "Box"])
        self.assertIn("FreeCAD Material…", out["shop"])


if __name__ == "__main__":
    unittest.main()
