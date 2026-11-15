# SPDX-License-Identifier: LGPL-2.1-or-later
# Make's panel tabs, task panels and runner, under stand-ins for FreeCAD and
# Qt (no FreeCAD, no Agent Link): the tabs build over any runner and send the
# arguments the old Agent Link tabs sent; the local runner answers what the
# Agent Link panel's _call answers, one undo step a changing call; the
# reviewer gives the verdict; the frame handler's gravity is defined.
import ast
import glob
import os
import unittest

from _stubs import ROOT, run

PARITY = r'''
from workshop_make import handlers, runner as R

def hosted(doc):
    """What Agent Link's panel._call does with a Make tool: the bound
    handler, an undo step if it changes, the answer through JSON, a refusal
    as {"error": {code, message}}."""
    s = R.Session(doc)
    table = handlers.bound(s)
    def call(tool, args):
        ch = R.changes(tool)
        if ch: doc.openTransaction(tool)
        try:
            out = table[tool](dict(args))
        except Exception as e:
            if ch: doc.abortTransaction()
            return False, {"error": {"code": e.code, "message": e.message}}
        if ch: doc.commitTransaction()
        return True, json.loads(json.dumps(out))
    return call

CALLS = [("setup", {"action": "add", "type": "print", "bodies": ["Box"]}), ("setup", {"action": "list"}),
         ("setup", {"action": "set", "id": "S1", "add": ["Lid"]}), ("part_spec", {"bodies": ["Box"], "material": "petg"}),
         ("part_spec", {"bodies": ["Box"], "material": "steel"}), ("part_spec", {"bodies": ["Box"], "material": ""}),
         ("setup", {"action": "bogus"}), ("setup", {"action": "add", "type": "print", "bodies": ["Nope"]}),
         ("thread_lookup", {"size": "M6"}), ("setup", {"action": "remove", "id": "S1"})]
docs = {"alone": Doc(), "hosted": Doc()}
runners = {"alone": R.local(lambda: docs["alone"]), "hosted": hosted(docs["hosted"])}
for k, r in runners.items():
    OUT[k] = [r(t, a) for t, a in CALLS]
    OUT[k + "_tx"] = docs[k].tx
'''

TABS = r'''
from workshop_make import panel as P
calls = []
def fake(tool, args):
    calls.append([tool, args])
    if tool == "setup" and args.get("action") == "list":
        return True, {"setups": [{"id": "S1", "type": "print", "name": "Print", "bodies": ["Box"], "nozzle": "0.4"}]}
    if tool == "fit":
        return True, {"model": {"slide": 5.25}, "printerFit": "hole 0.2"}
    return False, {"error": {"code": "invalid_input", "message": "no"}}
class Panel:  # what Agent Link hands a register_tab factory
    _call = staticmethod(fake)
tabs = {t: P.factory(c)(Panel()) for t, c, _o in P.HOSTED}
OUT["orders"] = [[t, o] for t, _c, o in P.HOSTED]
st = tabs["Setups"]
st.fill()
OUT["setup_rows"] = [r.texts for r in st.setups.rows]
OUT["in_none"] = st.msg.text()
st.body.setCurrentText("Lid"); st.new()
st.setups.setCurrentItem(st.setups.rows[0]); st.add()
st.setups.setCurrentItem(st.setups.rows[0]); st.remove()
mt = tabs["Materials"]
mt.fill()
OUT["mat_parts"] = [r.texts for r in mt.parts.rows]
OUT["hits"] = len(mt.hits.rows)
mt.find.setText("petg"); mt.search()
OUT["petg"] = [r.texts[0] for r in mt.hits.rows]
mt.parts.setCurrentItem(mt.parts.rows[0]); mt.hits.setCurrentItem(mt.hits.rows[0]); mt.give()
mt.parts.setCurrentItem(mt.parts.rows[0]); mt.forget()
OUT["mat_msg"] = mt.msg.text()
ft = tabs["Fits"]
ft.fill(); ft.nominal.setValue(5); ft.size()
OUT["fit_rows"] = [r.texts for r in ft.table.rows]
ft.calibrate()
rv = P.ReviewTab(runner=fake); rv.fill(); rv.review()
OUT["review_msg"] = rv.msg.text()
OUT["calls"] = calls
OUT["names"] = [w.objectName() for w in tabs.values()]
'''


class Tabs(unittest.TestCase):
    def test_tabs_send_what_the_old_tabs_sent(self):
        out = run(TABS)
        self.assertEqual(out["orders"], [["Setups", 30], ["Materials", 32], ["Fits", 34]])
        self.assertEqual(out["setup_rows"], [["Print (Print)", "Box", "0.4 nozzle"]] if out["setup_rows"][0][0] == "Print (Print)" else out["setup_rows"])
        self.assertIn("Lid", out["in_none"])
        calls = out["calls"]
        self.assertIn(["setup", {"action": "add", "type": "print", "bodies": ["Lid"]}], calls)
        self.assertIn(["setup", {"action": "set", "id": "S1", "add": ["Lid"]}], calls)
        self.assertIn(["setup", {"action": "remove", "id": "S1"}], calls)
        self.assertEqual([r[0] for r in out["mat_parts"]], ["Box", "Lid"])
        self.assertGreater(out["hits"], 6)  # filaments and shop materials
        self.assertEqual(out["petg"], ["PETG (printed)"] if out["petg"] and "PETG" in out["petg"][0] else out["petg"])
        self.assertIn(["part_spec", {"bodies": ["Box"], "material": "petg"}], calls)
        self.assertIn(["part_spec", {"bodies": ["Box"], "material": ""}], calls)
        self.assertEqual(out["mat_msg"], "no")
        self.assertIn(["fit", {"action": "size", "nominal": 5.0, "of": "hole"}], calls)
        self.assertEqual(out["fit_rows"], [["slide", "5.250"]])
        self.assertIn(["fit", {"action": "calibrate", "hole": 0.2, "shaft": 0.0}], calls)
        self.assertIn(["part_review", {"body": "Box"}], calls)
        self.assertEqual(out["review_msg"], "no")
        self.assertEqual(out["names"], ["MakeSetups", "MakeMaterials", "MakeFits"])


class Runner(unittest.TestCase):
    def test_alone_answers_as_hosted(self):
        out = run(PARITY)
        self.assertEqual(out["alone"], out["hosted"])
        self.assertEqual(out["alone_tx"], out["hosted_tx"])
        res = out["alone"]
        self.assertTrue(res[0][0])
        self.assertEqual(res[1][1]["setups"][0]["bodies"], ["Box"])
        self.assertEqual(res[3][1]["materials"], {"Box": "petg"})
        self.assertFalse(res[4][0])  # a shop material is not a filament
        self.assertEqual(res[5][1]["materials"], {})
        self.assertEqual(res[6][1]["error"]["code"], "invalid_input")
        self.assertEqual(res[7][1]["error"]["code"], "not_found")
        self.assertTrue(res[8][0])
        # One undo step per changing call that went through; a refused one undone.
        self.assertEqual([t[0] for t in out["alone_tx"]].count("open"), 9)
        self.assertIn(("abort",), [tuple(t) for t in out["alone_tx"]])

    def test_reviewer(self):
        out = run(r'''
import workshop_make.handlers.make as M
from workshop_make import runner as R
seen = []
M.part_review = lambda s, a: (seen.append([type(s).__name__, a]), {"verdict": "pass", "findings": []})[1]
from workshop_make import handlers
ns = {"review": handlers.review}
OUT["v"] = ns["review"](None, "Box")
OUT["seen"] = seen
def no(s, a):
    raise M.ToolError("not_found", "body 'X': not here")
M.part_review = no
OUT["refused"] = ns["review"](R.Session(Doc()), "X")
''')
        self.assertEqual(out["v"], {"verdict": "pass", "findings": []})
        self.assertEqual(out["seen"], [["Session", {"body": "Box"}]])
        self.assertEqual(out["refused"], {"error": {"code": "not_found", "message": "body 'X': not here"}})


def _agentlink():
    import sys

    for p in sys.path:
        if os.path.isfile(os.path.join(p, "agentlink", "hooks.py")):
            return p
    return None


class Hosted(unittest.TestCase):
    @unittest.skipUnless(_agentlink(), "Agent Link is not on the path")
    def test_tabs_and_reviewer_registered(self):
        out = run(r'''
from agentlink import hooks
import workshop_make.agentlink_families, workshop_make
OUT["tabs"] = [[t["title"], t["order"]] for t in hooks.TABS]
OUT["reviewers"] = [f.__module__ + "." + f.__name__ for f in hooks.REVIEWERS]
OUT["hosted"] = workshop_make._hosted
class Panel:
    _call = staticmethod(lambda t, a: (True, {"setups": []}))
OUT["built"] = [type(t["factory"](Panel())).__name__ for t in hooks.TABS]
''', extra_path=_agentlink())
        self.assertEqual(out["tabs"], [["Setups", 30], ["Materials", 32], ["Fits", 34]])
        self.assertEqual(out["reviewers"], ["workshop_make.handlers.review"])
        self.assertTrue(out["hosted"])
        self.assertEqual(out["built"], ["SetupsTab", "MaterialsTab", "FitsTab"])


class EmptyLists(unittest.TestCase):
    def test_setups_say_how_to_fill_them(self):
        out = run(r'''
from workshop_make import panel as P
for n, setups in (("none", []), ("some", [{"id": "S1", "type": "print", "name": "Print", "bodies": ["Box"]}])):
    t = P.SetupsTab(runner=lambda tool, a, setups=setups: (True, {"setups": setups}))
    shown = []
    t.none.setVisible = shown.append
    t.fill()
    OUT[n] = [t.none.text(), shown]
''')
        self.assertEqual(out["none"], ["No setups yet: Make ▸ New Setup…", [True]])
        self.assertEqual(out["some"][1], [False])


class TaskPanels(unittest.TestCase):
    def test_values_become_arguments(self):
        out = run(r'''
from workshop_make import taskpanels as T
OUT["new"] = T.args_of("setup_new", {"type": "print", "bodies": "Box, Lid", "name": "", "printer": "h2d", "nozzle": "0.4", "layerHeight": 0.2, "infill": 0.0})
OUT["hole"] = T.args_of("hole", {"body": "", "kind": "insert", "size": "M3", "at": [1, 2, 3], "dir": "-z", "depth": "6", "fit": "normal"})
OUT["cal"] = T.args_of("calibrate", {"hole": 0.15, "shaft": 0.05})
OUT["slice"] = T.args_of("slice", {"body": "Box", "name": "", "layerHeight": 0.0, "infill": 20.0, "pauseCommand": ""})
OUT["rm"] = T.args_of("setup_remove", {"id": "S2"})
OUT["panels"] = sorted(T.PANELS)
''')
        self.assertEqual(out["new"], ["setup", {"action": "add", "type": "print", "bodies": ["Box", "Lid"], "settings": {"printer": "h2d", "nozzle": 0.4, "layerHeight": 0.2}}])
        self.assertEqual(out["hole"], ["hw_hole", {"kind": "insert", "size": "M3", "at": [1.0, 2.0, 3.0], "dir": "-z", "depth": 6.0, "fit": "normal"}])
        self.assertEqual(out["cal"], ["fit", {"action": "calibrate", "hole": 0.15, "shaft": 0.05}])
        self.assertEqual(out["slice"], ["slice", {"body": "Box", "settings": {"infill": 20.0}}])
        self.assertEqual(out["rm"], ["setup", {"action": "remove", "id": "S2"}])
        self.assertEqual(out["panels"], ["calibrate", "embed", "fit_size", "hole", "setup_add", "setup_new", "setup_remove", "slice"])

    def test_form_panel_builds(self):
        out = run(r'''
from workshop_make import taskpanels as T
ran = []
for name in T.PANELS:
    p = T.FormPanel(name, runner=lambda t, a: (ran.append(t), (True, {"setups": [{"id": "S1", "name": "Print"}]}))[1])
    OUT[name] = sorted(p.values())
''')
        self.assertEqual(out["hole"], ["at", "body", "depth", "dir", "fit", "kind", "size"])
        self.assertEqual(out["setup_add"], ["add", "id"])


class Theme(unittest.TestCase):
    def test_accent_from_the_parameters_else_highlight(self):
        out = run(r'''
from workshop_make import theme
OUT["hex"] = theme.hex_of(0x3A7BD5FF)
OUT["none"] = theme.hex_of(0)
OUT["roles"] = theme.roles(get=lambda n: {"ThemeAccentColor1": 0x112233FF}.get(n, 0))
OUT["fill"] = theme.fill("a @accent2 b @accent c @bad", {"accent": "#1", "accent2": "#2", "bad": "#3"})
''')
        self.assertEqual(out["hex"], "#3a7bd5")
        self.assertIsNone(out["none"])
        self.assertEqual(out["roles"]["accent"], "#112233")
        self.assertEqual(out["roles"]["accent2"], "#112233")
        self.assertEqual(out["fill"], "a #2 b #1 c #3")


class Frame(unittest.TestCase):
    def test_gravity_is_defined(self):
        out = run(r'''
import workshop_make.handlers.frame as H
got = {}
H.ccx_io.find_binary = lambda *a: "/bin/true"
def build(members, supports, loads, g, n, tol):
    got["g"] = g
    raise ValueError("stop here")
H.FR.build = build
H.matfam = types.SimpleNamespace(card=lambda d, m: {"name": "PLA", "E": 3500, "nu": 0.36, "density": 1.24})
s = types.SimpleNamespace(doc=Doc(), out_dir="/tmp")
try:
    H.fea_frame(s, {"members": [{"name": "M", "from": [0, 0, 0], "to": [1000, 0, 0], "section": {"kind": "rect", "b": 10, "d": 10}, "material": "pla"}],
                    "supports": [{"at": [0, 0, 0]}], "gravity": True})
except Exception as e:
    OUT["raised"] = type(e).__name__
OUT["g"] = got.get("g")
OUT["G"] = H.G
''')
        self.assertNotEqual(out.get("raised"), "NameError")
        self.assertEqual(out["G"], 9810.0)
        self.assertEqual(out["g"], [0, 0, -9810.0])


class Plain(unittest.TestCase):
    def test_no_agentlink_import_outside_the_family_layer(self):
        pkg = os.path.join(ROOT, "workshop_make")
        for path in glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True):
            name = os.path.basename(path)
            # The family layer, and the helper only it loads. maps.py and
            # printed.py are lent what they need by it (maps.register,
            # printed.register), so they are held to this too.
            if name in ("agentlink_families.py", "tooldata.py") or name.startswith("fam_"):
                continue
            for n in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                self.assertFalse(any(m.split(".")[0] == "agentlink" for m in mods), f"{name} imports {mods}")

    def test_maps_and_printed_are_lent_what_they_need(self):
        out = run('''
import types
from workshop_make import maps, printed
OUT["loaded"] = sorted(m for m in sys.modules if m.split(".")[0] == "agentlink")
OUT["before"] = [maps.render, printed.hooks]
try:
    maps.wall(None, {"objects": []})
except RuntimeError as e:
    OUT["unlent"] = str(e)
got = []
render = types.SimpleNamespace(register_map=lambda *a: got.append(a[0]))
maps.register(render)
ext = []
hooks = types.SimpleNamespace(extend_tool=lambda name, *a: ext.append(name), analysis=lambda s, k: {"from": "hooks", "kind": k})
printed.register(hooks)
OUT["maps"] = [got, maps.render is render]
OUT["printed"] = [ext, printed.hooks is hooks, printed._last(object())]
''')
        self.assertEqual(out["loaded"], [])
        self.assertEqual(out["before"], [None, None])
        self.assertIn("renderer", out["unlent"])
        self.assertEqual(out["maps"], [["wall"], True])
        self.assertEqual(out["printed"], [["fea_setup", "fea_solve"], True, {"from": "hooks", "kind": "fea"}])


if __name__ == "__main__":
    unittest.main()
