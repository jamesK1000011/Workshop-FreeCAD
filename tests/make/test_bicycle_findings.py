# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings of the bicycle test drive (FreeCAD 1.1.3, 20 Nov 2026), Make's
# part. FreeCAD and Agent Link stood in for.
#
# 12. setup kept machine "fiber laser"; cut_check then refused it ("one of
#     laser, waterjet, plasma, router"). Now one list from data serves both:
#     a common name is kept as its machine, and a name that is no machine is
#     refused at setup, with the allowed values.
# 13. Two sprockets were PartDesign bodies, hidden: cut_export did not find
#     "Chainring" by the body's label. Now a hidden Body is found by its
#     Label or Name, and its Shape (or its tip's) is used.
import unittest

from _stubs import run

BIKE = r'''
import types
class Shape:
    def __init__(self, solid=True, tag=""):
        self.Solids = [1] if solid else []
        self.tag = tag
    def isNull(self):
        return not self.Solids
class Feature:
    def __init__(self, label, name, shape):
        self.Label, self.Name, self.TypeId, self.Shape = label, name, "PartDesign::Pad", shape
        self.Visibility, self.InList = False, []
    def getParentGeoFeatureGroup(self):
        return None
class Body:
    def __init__(self, label, name, shape, tip, shown=False):
        self.Label, self.Name, self.TypeId, self.Shape, self.Tip = label, name, "PartDesign::Body", shape, tip
        self.Visibility, self.InList = shown, []
    def getParentGeoFeatureGroup(self):
        return None
pad = Feature("Pad", "Pad", Shape(tag="pad"))
chainring = Body("Chainring", "Body001", Shape(tag="chainring"), pad)
pad2 = Feature("Pad001", "Pad001", Shape(tag="cog"))
cog = Body("Cog", "Body002", Shape(False), pad2)       # its own Shape empty: the tip's is used
frame = Body("Frame", "Body", Shape(tag="frame"), None, shown=True)
doc = Doc(())
doc.Objects = [frame, chainring, pad, cog, pad2]
class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message
class HostSession:
    """A host's session: body() sees shown bodies only, as Agent Link's did."""
    def __init__(self, doc):
        self.doc, self.meta, self.steps = doc, {}, []
    def body(self, ref):
        for o in self.doc.Objects:
            if o.Visibility and (o.Label == ref or o.Name == ref):
                return o
        raise Refused("not_found", f"body {ref!r}: not here")
'''


class OneMachineList(unittest.TestCase):
    def test_names_are_made_into_the_machine(self):
        out = run(r'''
from workshop_make import cutmachines as cm
OUT["m"] = [cm.machine(x) for x in ("Fiber laser", "fibre-laser", "CO2 laser", "co2_laser", "laser", "Water jet", "CNC router", "lathe", "")]
OUT["keys"] = list(cm.keys())
OUT["refusal"] = cm.machine_refusal("lathe")
OUT["mat"] = [cm.material(x) for x in ("Aluminium", "plywood", "pom", "cheese")]
''')
        self.assertEqual(out["m"], ["laser", "laser", "laser", "laser", "laser", "waterjet", "router", None, None])
        self.assertEqual(out["keys"], ["laser", "waterjet", "plasma", "router"])
        for k in ("laser", "waterjet", "plasma", "router", "fiber laser", "co2 laser"):
            self.assertIn(k, out["refusal"])
        self.assertEqual(out["mat"], ["aluminium", "plywood", None, None])  # pom is not cut from sheet

    def test_setup_keeps_the_machine_cut_check_takes(self):
        out = run(r'''
from workshop_make import api, records
from workshop_make.refusal import Refused
doc = Doc(("Chainring", "Plate"))
st = api.setup_add(doc, "cut", ["Chainring"], {"machine": "fiber laser", "thickness": 3, "material": "Aluminium"})
OUT["kept"] = [st["machine"], st["material"]]
got = []
for settings in ({"machine": "lathe"}, {"machine": "laser", "material": "cheese"}):
    try:
        api.setup_add(doc, "cut", ["Plate"], settings)
        got.append(None)
    except Refused as e:
        got.append(str(e))
OUT["refused"] = got
OUT["setups"] = len(records.setups(doc))
s2 = api.setup_set(doc, st["id"], settings={"machine": "CO2 laser"})
OUT["set"] = s2["machine"]
try:
    api.setup_set(doc, st["id"], settings={"machine": "fiber"})
    OUT["set_bad"] = None
except Refused as e:
    OUT["set_bad"] = str(e)
# Print and mill setups are not judged by the cut lists.
OUT["print"] = api.setup_add(doc, "print", ["Plate"], {"printer": "generic"})["type"]
''')
        self.assertEqual(out["kept"], ["laser", "aluminium"])
        self.assertIn("settings.machine 'lathe'", out["refused"][0])
        self.assertIn("laser (or ", out["refused"][0])
        self.assertIn("waterjet", out["refused"][0])
        self.assertIn("settings.material 'cheese'", out["refused"][1])
        self.assertEqual(out["setups"], 1)  # nothing kept from a refused add
        self.assertEqual(out["set"], "laser")
        self.assertIn("not a machine", out["set_bad"])
        self.assertEqual(out["print"], "print")

    def test_cut_check_reads_the_same_list(self):
        out = run(r'''
from workshop_make.handlers import cut as C
from workshop_make import cutmachines as cm
OUT["same"] = [list(C.MACHINES) == list(cm.keys()), list(C.METALS + C.OTHERS) == list(sum(cm.cut_materials(), ()))]
assumed = {}
OUT["old"] = list(C.machine_of(None, {"machine": "Fiber Laser", "material": "Steel"}, {}, assumed))
OUT["arg"] = list(C.machine_of(None, {}, {"machine": "co2 laser"}, {}))
try:
    C.machine_of(None, {"machine": "lathe"}, {}, {})
except C.ToolError as e:
    OUT["bad"] = [e.code, e.message]
''')
        self.assertEqual(out["same"], [True, True])
        self.assertEqual(out["old"], ["laser", "steel", 0.2])  # a setup kept before this fix still reads
        self.assertEqual(out["arg"][0], "laser")
        self.assertEqual(out["bad"][0], "invalid_input")
        self.assertIn("not a machine", out["bad"][1])


class HiddenBodies(unittest.TestCase):
    def test_a_hidden_body_is_found_by_its_label_or_name(self):
        out = run(BIKE + r'''
from workshop import finder
s = finder.looked(HostSession(doc))
OUT["shown"] = s.body("Frame").Label
OUT["hidden"] = [s.body("Chainring").Shape.tag, s.body("Body001").Label, s.body("chainring").Label]
c = s.body("Cog")
OUT["tip"] = [type(c).__name__, c.Shape.tag, c.Label, finder.real(c) is cog]
try:
    s.body("Seatpost")
except Exception as e:
    OUT["missing"] = [e.code, e.message]
# The session's own state stays its own.
s._last = 3
OUT["state"] = [s.__dict__.get("_last"), getattr(s, "_last"), s.doc is doc, finder.looked(s) is s]
''')
        self.assertEqual(out["shown"], "Frame")
        self.assertEqual(out["hidden"], ["chainring", "Chainring", "Chainring"])
        self.assertEqual(out["tip"], ["TipShaped", "cog", "Cog", True])
        self.assertEqual(out["missing"], ["not_found", "body 'Seatpost': not here"])  # the session's own refusal
        self.assertEqual(out["state"][1:], [3, True, True])

    def test_bound_handlers_and_the_add_on_runner_find_it(self):
        out = run(BIKE + r'''
from workshop_make import handlers, runner
seen = []
def tool(s, a):
    o = s.body(a["body"])
    seen.append([o.Label, o.Shape.tag])
    return {}
h = handlers.bound(HostSession(doc), {"t": tool})
h["t"]({"body": "Chainring"})
h["t"]({"body": "Body002"})
OUT["bound"] = seen
r = runner.Session(doc)
OUT["runner"] = [r.body("Chainring").Shape.tag, r.body("Cog").Shape.tag, [o.Label for o in r.bodies()]]
''')
        self.assertEqual(out["bound"], [["Chainring", "chainring"], ["Cog", "cog"]])
        self.assertEqual(out["runner"], ["chainring", "cog", ["Frame"]])  # bodies() still lists the shown ones

    def test_documents_handlers_find_it_too(self):
        out = run(BIKE + r'''
from workshop_documents import handlers, runner
seen = []
h = handlers.bound(HostSession(doc), {"t": lambda s, a: seen.append(s.body(a["body"]).Label)})
h["t"]({"body": "Chainring"})
OUT["bound"] = seen
OUT["runner"] = runner.Session(doc).body("Chainring").Label
''')
        self.assertEqual(out["bound"], ["Chainring"])
        self.assertEqual(out["runner"], "Chainring")


if __name__ == "__main__":
    unittest.main()
