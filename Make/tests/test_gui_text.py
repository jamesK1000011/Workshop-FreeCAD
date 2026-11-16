# SPDX-License-Identifier: LGPL-2.1-or-later
# What a person reads in Make's GUI, under stand-ins for FreeCAD and Qt: the
# checks' answers as a verdict then figures with units (never a raw dict),
# refusals without the agent's tool syntax, task panels that start on
# sensible values and show choices capitalised while the tools get their
# values, and a second task refused while one is open.
import unittest

from _stubs import run


class Results(unittest.TestCase):
    def test_verdict_first_then_figures(self):
        out = run(r'''
from workshop_make import results as R
OUT["dfm"] = R.dfm({"body": "QA5", "findings": [{"severity": "error", "rule": "thin-wall", "says": "Wall 0.6 mm, under 0.8 mm.", "id": "F1"},
                                               {"severity": "warning", "rule": "overhang", "says": "Overhang 60°.", "waived": True}],
                    "wall": {"least": 0.6}, "setup": "Print (S1)"})
OUT["clean"] = R.dfm({"body": "QA5", "findings": [], "wall": {"least": 1.2}})
OUT["review"] = R.review({"body": "QA5", "verdict": "pass", "process": "printed", "findings": [],
                          "figures": {"mass": 12.34, "volume": 9876.5, "material": "pla", "wall": 1.2}})
OUT["mass"] = R.mass({"bodies": [{"body": "QA5", "mass": 12.3456, "com": [1.0, 2.5, 3.0], "volume": 10000.0, "material": "pla",
                                  "density": 1.24, "as": "solid", "inertia": {"aboutCom": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "principal": [1.0, 1.0, 1.0]}}]})
''')
        verdict, text, line = out["dfm"]
        self.assertEqual(verdict, "QA5 is not printable as it stands.")
        self.assertTrue(text.startswith(verdict))
        self.assertIn("Least wall: 0.6 mm", text)
        self.assertIn("Problem: Wall 0.6 mm", text)
        self.assertNotIn("Overhang", text)
        self.assertIn("Waived: 1", text)
        self.assertTrue(line.startswith("QA5 is not printable as it stands. DFM check: 1 problem"), line)
        self.assertEqual(out["clean"][0], "QA5 is printable.")
        self.assertEqual(out["review"][0], "QA5 passes.")
        self.assertIn("Mass: 12.3 g (PLA)", out["review"][1])
        verdict, text, line = out["mass"]
        # one decimal, as Part Review shows it
        self.assertEqual(verdict, "QA5 weighs 12.3 g.")
        self.assertIn("Material: PLA, 1.24 g/cm³", text)
        self.assertIn("Centre of mass: 1, 2.5, 3 mm", text)
        self.assertIn("g·mm²", text)
        for s in (text, line):
            self.assertNotIn("{", s)

    def test_materials_by_name_never_the_tool(self):
        out = run(r'''
from workshop_make import results as R
OUT["names"] = [R.material_name(x) for x in ("pla", "petg", "tpu-95a", "steel-1018", "abs (assumed: material_set records it)", "")]
OUT["mass"] = R.mass({"bodies": [{"body": "QA5", "mass": 30.53, "material": "pla (assumed: material_set records it)", "density": 1.24}]})[1]
OUT["review"] = R.review({"body": "QA5", "verdict": "pass", "figures": {"mass": 30.53, "material": "pla"}})[1]
''')
        self.assertEqual(out["names"][:4], ["PLA", "PETG", "TPU 95A", "steel-1018"])
        self.assertTrue(out["names"][4].startswith("ABS (assumed"), out["names"][4])
        self.assertEqual(out["names"][5], "not set")
        self.assertNotIn("material_set", out["mass"])
        self.assertIn("QA5: 30.5 g", out["mass"])
        self.assertIn("Mass: 30.5 g (PLA)", out["review"])

    def test_refusals_in_person_words(self):
        out = run(r'''
from workshop_make import results as R
OUT["setup"] = R.person_error({"error": {"message": 'QA5 is in no print setup: a part is encased between layers — setup add { type: "print", bodies: ["QA5"] } once the person says it is printed.'}})
OUT["tool"] = R.person_error({"error": {"message": "waive.id 'F9': not a finding of the last check on QA5 — dfm_check it first."}})
OUT["plain"] = R.person_error({"error": {"message": "body 'X': not in the document"}})
OUT["line"] = R.sentence("hw_pauses", "Pauses", {"body": "QA5", "pauses": [{"layer": 12, "z": 2.5, "note": "Insert 6x2 magnet"}], "count": 1})
''')
        self.assertEqual(out["setup"], "QA5 isn't in a print setup yet: Make ▸ New Setup… first.")
        self.assertNotIn("dfm_check", out["tool"])
        self.assertEqual(out["plain"], "Body 'X': not in the document.")
        self.assertEqual(out["line"], "Workshop: QA5 needs 1 pause: after layer 12 (Z 2.5 mm): Insert 6x2 magnet.")


class Commands(unittest.TestCase):
    def test_command_and_panel_say_the_same(self):
        out = run(r'''
from workshop_make import commands as C, taskpanels as T
OUT["pairs"] = [[c.GetResources()["MenuText"], T.PANELS[c.panel][0]] for c in C.COMMANDS.values() if isinstance(c, C.Form)]
''')
        for menu, title in out["pairs"]:
            self.assertEqual(menu.rstrip("…"), title)

    def test_guidance_is_a_message_and_boxes_are_titled(self):
        out = run(r'''
made = []
class Box:
    Information, Warning = 1, 2
    def __init__(self, parent): self.calls = []; made.append(self)
    def __getattr__(self, n): return lambda *a: self.calls.append([n, list(a)])
sys.modules["PySide.QtGui"].QMessageBox = Box
from workshop_make import commands as C
said.clear()
warned = []
FreeCAD.Console.PrintWarning = warned.append
C.report("Pauses", False, {"error": {"code": "invalid_state", "message": "QA5 is in no print setup: setup add { … }"}}, "hw_pauses", show=True)
OUT["said"], OUT["warned"] = list(said), list(warned)
sys.platform = "darwin"
C.report("Mass properties", True, {"bodies": [{"body": "QA5", "mass": 30.53, "material": "pla", "density": 1.24}]}, "mass_properties", show=True)
OUT["calls"] = made[-1].calls
''')
        self.assertEqual(out["warned"], [])
        self.assertIn("isn't in a print setup yet", out["said"][0])
        calls = dict((c[0], c[1]) for c in out["calls"])
        self.assertEqual(calls["setWindowTitle"], ["Workshop Make · Mass Properties"])
        self.assertEqual(calls["setText"], ["Workshop Make · Mass Properties"])
        self.assertTrue(calls["setInformativeText"][0].startswith("QA5 weighs 30.5 g."))

    def test_slice_refuses_a_part_in_no_print_setup(self):
        out = run(r'''
from workshop_make import commands as C
C.R.run = lambda tool, args: (True, {"setups": [{"id": "S1", "type": "print", "bodies": ["Box"]}, {"id": "S2", "type": "cut", "bodies": ["Lid"]}]})
OUT["box"] = C.no_print_setup("Box")
OUT["lid"] = C.no_print_setup("Lid")
OUT["none"] = C.no_print_setup(None)
from workshop_make import results
OUT["said"] = results.person_error(OUT["lid"])
''')
        self.assertIsNone(out["box"])
        self.assertIsNone(out["none"])
        self.assertEqual(out["said"], "Lid isn't in a print setup yet: Make ▸ New Setup… first.")


class Panels(unittest.TestCase):
    def test_defaults_and_shown_text(self):
        out = run(r'''
from workshop_make import taskpanels as T
p = T.FormPanel("setup_new", runner=lambda t, a: (True, {"setups": []}))
OUT["values"] = p.values()
OUT["args"] = T.args_of("setup_new", p.values())
OUT["cut"] = T.args_of("setup_new", dict(p.values(), type="cut"))
OUT["titles"] = {k: v[0] for k, v in T.PANELS.items()}
OUT["fit"] = T.FormPanel("fit_size", runner=lambda t, a: (True, {})).values()["kind"]
OUT["shown"] = [T.shown(v) for v in ("print", "corexy", "nut_trap", "-z", "M3")]
OUT["body_one"] = T.body_items(["QA5"])
OUT["body_sel"] = T.body_items(["A", "B"], "B")
OUT["body_many"] = T.body_items(["A", "B"])[0][0]
OUT["no_setups"] = T.FormPanel("setup_remove", runner=lambda t, a: (True, {"setups": []})).values()
''')
        v = out["values"]
        self.assertEqual((v["type"], v["printer"], v["nozzle"], v["layerHeight"], v["infill"]), ("print", "generic", "0.4", 0.2, 15.0))
        self.assertEqual(out["args"][1]["settings"], {"printer": "generic", "nozzle": 0.4, "layerHeight": 0.2, "infill": 15.0})
        self.assertNotIn("settings", out["cut"][1])
        for t in out["titles"].values():
            self.assertTrue(all(w[0].isupper() or w in ("for", "to", "of") for w in t.split()), t)
        self.assertEqual(out["fit"], "")
        self.assertEqual(out["shown"], ["Print", "CoreXY", "Nut trap", "Down (−Z)", "M3"])
        self.assertEqual(out["body_one"], [[["QA5", "QA5"]], 0])
        self.assertEqual(out["body_sel"], [[["A", "A"], ["B", "B"]], 1])
        self.assertEqual(out["body_many"], ["", "Choose a part"])
        self.assertEqual(out["no_setups"], {"id": ""})

    def test_hole_and_embed_fields_read_as_words(self):
        out = run(r'''
from workshop_make import taskpanels as T
p = T.FormPanel("hole", runner=lambda t, a: (True, {}))
OUT["through"] = p.values()["depth"]
OUT["args"] = T.args_of("hole", p.values())[1].get("depth")
labels = [l for _k, l, _kind, _d, _x in T.PANELS["hole"][3]] + [l for _k, l, _kind, _d, _x in T.PANELS["embed"][3]]
OUT["labels"] = labels
OUT["dirs"] = [t for _v, t in T.options(dict((k, x) for k, _l, _kind, _d, x in T.PANELS["hole"][3])["dir"])]
''')
        self.assertEqual((out["through"], out["args"]), ("through", "through"))
        self.assertIn("Depth", out["labels"])
        self.assertNotIn("Depth (mm or through)", out["labels"])
        self.assertEqual(out["dirs"], ["Down (−Z)", "Up (+Z)", "Toward −X", "Toward +X", "Toward −Y", "Toward +Y"])

    def test_depth_number_when_not_through(self):
        out = run(r'''
from workshop_make import taskpanels as T
made = []
orig = sys.modules["PySide.QtGui"].QCheckBox
class Check(orig):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); made.append(self)
sys.modules["PySide.QtGui"].QCheckBox = Check
p = T.FormPanel("hole", runner=lambda t, a: (True, {}))
made[0].setChecked(False)
OUT["depth"] = T.args_of("hole", p.values())[1].get("depth")
''')
        self.assertEqual(out["depth"], 0.1)

    def test_every_panel_says_what_it_does(self):
        out = run(r'''
from workshop_make import taskpanels as T
OUT["missing"] = [k for k in T.PANELS if not T.INTRO.get(k)]
''')
        self.assertEqual(out["missing"], [])

    def test_no_setups_leaves_ok_out(self):
        out = run(r'''
from workshop_make import taskpanels as T
for name in ("setup_add", "setup_remove"):
    p = T.FormPanel(name, runner=lambda t, a: (True, {"setups": []}))
    OUT[name] = [p.blocked, p.getStandardButtons(), p.accept(), p.msg.text()]
q = T.FormPanel("setup_remove", runner=lambda t, a: (True, {"setups": [{"id": "S1", "name": "Print"}]}))
OUT["some"] = [q.blocked, q.getStandardButtons()]
''')
        for name in ("setup_add", "setup_remove"):
            blocked, buttons, accepted, msg = out[name]
            self.assertEqual(blocked, "No setups yet: Make ▸ New Setup… first.")
            self.assertEqual(buttons, 2)  # Cancel alone
            self.assertFalse(accepted)
            self.assertEqual(msg, blocked)
        self.assertEqual(out["some"], ["", 3])

    def test_a_second_task_is_refused(self):
        out = run(r'''
told, shown = [], []
class Box:
    @staticmethod
    def information(parent, title, text): told.append([title, text])
    warning = information
sys.modules["PySide.QtGui"].QMessageBox = Box
Gui.Control = types.SimpleNamespace(activeDialog=lambda: object(), showDialog=shown.append, closeDialog=lambda: None)
from workshop_make import taskpanels as T
OUT["got"] = T.show("calibrate", runner=lambda t, a: (True, {}))
OUT["told"] = told
OUT["shown"] = len(shown)
''')
        self.assertIsNone(out["got"])
        self.assertEqual(out["told"], [["Workshop Make", "Finish or cancel the open task first."]])
        self.assertEqual(out["shown"], 0)


if __name__ == "__main__":
    unittest.main()
