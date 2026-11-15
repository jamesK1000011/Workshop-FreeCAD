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
        self.assertTrue(line.startswith("DFM Check · QA5 is not printable"))
        self.assertEqual(out["clean"][0], "QA5 is printable.")
        self.assertEqual(out["review"][0], "QA5 passes.")
        self.assertIn("Mass: 12.3 g (pla)", out["review"][1])
        verdict, text, line = out["mass"]
        self.assertEqual(verdict, "QA5 weighs 12.35 g.")
        self.assertIn("Centre of mass: 1, 2.5, 3 mm", text)
        self.assertIn("g·mm²", text)
        for s in (text, line):
            self.assertNotIn("{", s)

    def test_refusals_in_person_words(self):
        out = run(r'''
from workshop_make import results as R
OUT["setup"] = R.person_error({"error": {"message": 'QA5 is in no print setup: a part is encased between layers — setup add { type: "print", bodies: ["QA5"] } once the person says it is printed.'}})
OUT["tool"] = R.person_error({"error": {"message": "waive.id 'F9': not a finding of the last check on QA5 — dfm_check it first."}})
OUT["plain"] = R.person_error({"error": {"message": "body 'X': not in the document"}})
OUT["line"] = R.line("Workshop Make · Pauses", {"body": "QA5", "pauses": [{"z": 1}], "count": 1, "setup": {"id": "S1"}})
''')
        self.assertEqual(out["setup"], "QA5 isn't in a print setup yet: Make ▸ New Setup… first.")
        self.assertNotIn("dfm_check", out["tool"])
        self.assertEqual(out["plain"], "Body 'X': not in the document.")
        self.assertEqual(out["line"], "Workshop Make · Pauses · body QA5; pauses 1 item; count 1.")


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
        self.assertEqual(out["shown"], ["Print", "CoreXY", "Nut trap", "-z", "M3"])
        self.assertEqual(out["body_one"], [[["QA5", "QA5"]], 0])
        self.assertEqual(out["body_sel"], [[["A", "A"], ["B", "B"]], 1])
        self.assertEqual(out["body_many"], ["", "Choose a part"])
        self.assertEqual(out["no_setups"], {"id": ""})

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
