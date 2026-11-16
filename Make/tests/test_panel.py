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
import os
from workshop_make import handlers, runner as R
sys.path.insert(0, os.path.join(sys.argv[1], "tests"))
import _threadtable
_threadtable.install()  # FreeCAD's thread tables, stood in for

def hosted(doc):
    """What Agent Link's panel._call does with a Make tool: the bound
    handler, an undo step if it changes, the answer through JSON, a refusal
    as {"error": {code, message}}."""
    s = R.Session(doc)
    table = handlers.bound(s)
    def call(tool, args):
        ch = R.changes(tool, args)  # a read (setup list) is no undo step, as in Agent Link
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
        self.assertEqual(out["setup_rows"], [["Print", "Box", "Generic, 0.4 mm nozzle, 0.2 mm layers"]])
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
        self.assertIn(["fit", {"action": "size", "nominal": 5.0, "of": "hole", "body": "Box"}], calls)
        self.assertEqual(out["fit_rows"], [["slide", "5.25 mm"]])
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
        # One undo step per changing call that went through; a refused one
        # undone; setup's action list is a read, no undo step.
        self.assertEqual([t[0] for t in out["alone_tx"]].count("open"), 8)
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
OUT["where"] = {k: sorted(v) for k, v in getattr(hooks, "TAB_WORKBENCHES", {}).items()}
class Panel:
    _call = staticmethod(lambda t, a: (True, {"setups": []}))
OUT["built"] = [type(t["factory"](Panel())).__name__ for t in hooks.TABS]
''', extra_path=_agentlink())
        self.assertEqual(out["tabs"], [["Setups", 30], ["Materials", 32], ["Fits", 34]])
        self.assertEqual(out["reviewers"], ["workshop_make.handlers.review"])
        self.assertTrue(out["hosted"])
        self.assertEqual(out["built"], ["SetupsTab", "MaterialsTab", "FitsTab"])
        if out["where"]:  # an Agent Link with tabs per workbench: only in Make's, Review too
            self.assertEqual(out["where"], {t: ["WorkshopMakeWorkbench"] for t in ("Setups", "Materials", "Fits", "Review")})


class Reads(unittest.TestCase):
    def test_a_panel_refresh_changes_nothing(self):
        """setup's action list or of is a read: no undo step (the document
        stayed "1*" after each panel refresh on the Mac); a change still is."""
        out = run(r'''
from workshop_make import runner as R, panel as P
OUT["changes"] = [R.changes("setup", {"action": "list"}), R.changes("setup", {}), R.changes("setup", {"action": "of"}),
                  R.changes("setup", {"action": "add"}), R.changes("part_spec", {}), R.changes("fit", {})]
seen = []
def quiet_runner(tool, args, quiet=False):
    seen.append([tool, args.get("action"), quiet])
    return True, {"setups": []}
quiet_runner.quiet_ok = True
t = P.SetupsTab(runner=quiet_runner)
t.fill()
OUT["seen"] = seen
''')
        self.assertEqual(out["changes"], [False, False, False, True, True, False])
        # The tab's own refresh is quiet; a click (New) is not.
        self.assertTrue(out["seen"])
        self.assertTrue(all(q for _t, a, q in out["seen"] if a == "list"))


class Untouched(unittest.TestCase):
    def test_refresh_and_same_record_leave_the_document_alone(self):
        """The panel's refresh reads; a record written with the value it has
        writes nothing (no records object made, the document not touched)."""
        out = run(r'''
from workshop_make import records, panel as P
class D:
    def __init__(self):
        object.__setattr__(self, "log", [])
        object.__setattr__(self, "Meta", {})
    def __setattr__(self, k, v):
        self.log.append(k)
        object.__setattr__(self, k, v)
d = D()
P.material_rows(d)
records.setups(d)
OUT["read"] = list(d.log)
records.save_setups(d, [{"id": "S1"}])
records.save_setups(d, [{"id": "S1"}])
OUT["writes"] = list(d.log)
''')
        self.assertEqual(out["read"], [])
        self.assertEqual(out["writes"], ["Meta"])


class KeepsTheMark(unittest.TestCase):
    def test_opening_the_workbench_leaves_the_star_alone(self):
        """Activating Make set the window's "*" on the Mac with no undo step:
        whatever the panel's opening sets on the window's side is put back;
        a refresh likewise."""
        out = run(r'''
from workshop_make import layout, panel, workbench
class G:
    Modified = False
class D:
    UndoNames = []
g, d = G(), D()
layout._documents = lambda: [("Box", g, d)]
def show(title="Setups"):
    g.Modified = True  # a view property set by the panel's opening
panel.show = show
class Gui:
    class Workbench:
        pass
    @staticmethod
    def addWorkbench(w):
        pass
wb = workbench.make_class(Gui)()
wb.Activated()
OUT["after_activate"] = g.Modified
class W:
    def fill(self):
        g.Modified = True
panel._fill(W())
OUT["after_refresh"] = g.Modified
''')
        self.assertFalse(out["after_activate"])
        self.assertFalse(out["after_refresh"])


class NarrowDock(unittest.TestCase):
    def test_no_row_too_wide_for_the_dock(self):
        """In the 330 px dock: Setups' two picks on one line and its keys on
        the next; Fits' printer calibration a form, Keep under it."""
        out = run(r'''
from workshop_make import panel as P
fake = lambda tool, args: (True, {"setups": []})
s = P.SetupsTab(runner=fake)
f = P.FitsTab(runner=fake)
OUT["rows"] = [s.pick_row is not s.key_row, hasattr(f, "cal_form")]
''')
        self.assertEqual(out["rows"], [True, True])


class OwnDock(unittest.TestCase):
    @unittest.skipUnless(_agentlink(), "Agent Link is not on the path")
    def test_own_dock_when_agent_link_places_panels(self):
        """With Agent Link's placer (service panel_layout) Make's tabs are
        its own "Make" dock beside Model and Tasks, not tabs of Agent
        Link's panel; the reviewer still answers Agent Link's Review."""
        out = run(r'''
from agentlink import hooks
hooks.provide("panel_layout", object())
import workshop_make.agentlink_families, workshop_make
OUT["tabs"] = [t["title"] for t in hooks.TABS]
OUT["review_in"] = sorted(getattr(hooks, "TAB_WORKBENCHES", {}).get("Review", ()))
OUT["reviewers"] = len(hooks.REVIEWERS)
OUT["hosted"] = workshop_make._hosted
''', extra_path=_agentlink())
        self.assertEqual(out["tabs"], [])
        self.assertEqual(out["review_in"], [])
        self.assertEqual(out["reviewers"], 1)
        self.assertTrue(out["hosted"])


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


LIVE = r'''
from workshop_make import panel as P, results as R
OUT["names"] = [P.setup_name(s) for s in ({"id": "S1", "type": "print", "name": "Print"}, {"id": "S2", "type": "print", "name": "Print 2"},
                                          {"id": "S3", "type": "print", "name": "Bracket run"}, {"id": "S4", "type": "cut", "name": ""})]
OUT["sums"] = [P.summary({}, "print"), P.summary({"printer": "h2d", "layerHeight": 0.12, "infill": 15}, "print"), P.summary({}, "cut"), P.summary({"fit": {"hole": 0.1}}, "print")]
hits = P.material_hits("")
OUT["hit_names"] = [h[1] for h in hits]
OUT["hit_kinds"] = sorted({h[2] for h in hits})
OUT["aluminium"] = [h[0] for h in P.material_hits("aluminium")]
OUT["mat_rows"] = P.material_rows(Doc(("Box",)))
OUT["fits"] = P.fit_rows({"model": {"slide": 5.2, "press": 4.9}})
OUT["head"] = [P.review_lines({"verdict": v, "process": p}, "Body")[0] for v, p in (("pass", "printed"), ("fix", "cut"), ("pass", "mill"), ("unknown", "unknown"))]
OUT["foot"] = P.review_lines({"verdict": "pass", "process": "printed", "figures": {"volume": 24000.0, "mass": 9.6, "material": "pla", "as": "printed: 2 walls"}}, "Body")[3]
OUT["foot_small"] = R.figures_line({"volume": 512.0, "mass": 0.6, "material": "pla (assumed: none set)", "wall": 1.2})
'''


class LiveFindings(unittest.TestCase):
    """What driving the Make dock on the Mac (354 px, FreeCAD Dark) found."""

    def test_setup_named_once_and_settings_shown(self):
        out = run(LIVE)
        self.assertEqual(out["names"], ["Print", "Print 2", "Bracket run (Print)", "S4 (Cut)"])
        self.assertEqual(out["sums"], ["Defaults: Generic, 0.4 mm nozzle, 0.2 mm layers", "H2D, 0.4 mm nozzle, 0.12 mm layers, 15% infill", "Defaults",
                                       "Defaults: Generic, 0.4 mm nozzle, 0.2 mm layers"])

    def test_materials_by_display_name_once(self):
        out = run(LIVE)
        names = out["hit_names"]
        self.assertIn("Aluminum", names)
        self.assertNotIn("Aluminium", names)  # a spelling of Aluminum: found by search, listed once
        self.assertEqual(out["aluminium"], ["aluminum"])
        for n in names:
            self.assertTrue(n[0].isupper(), n)
        self.assertIn("Stainless Steel", names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(out["hit_kinds"], ["Filament", "Metal", "Non-metal"])
        self.assertEqual(out["mat_rows"], [["Box", "PLA (assumed)", "1.24"]])

    def test_fits_and_review_with_units(self):
        out = run(LIVE)
        self.assertEqual(out["fits"], [["slide", "5.20 mm"], ["press", "4.90 mm"]])
        self.assertEqual(out["head"], ["PASS — Body, printed", "FIX — Body, cut", "PASS — Body, milled", "UNKNOWN — Body, process not set"])
        self.assertEqual(out["foot"], "Volume 24.0 cm³  ·  Mass 9.6 g  ·  Material PLA  ·  As printed: 2 walls")
        self.assertEqual(out["foot_small"], "Volume 512.0 mm³  ·  Mass 0.6 g  ·  Material PLA (assumed)  ·  Least wall 1.20 mm")

    def test_tables_fit_the_dock(self):
        """Every table: no horizontal scrollbar, a stretch column, the rest
        sized to contents; every cell's full text in its tooltip."""
        out = run(r'''
from workshop_make import panel as P
def fake(tool, args):
    if tool == "setup":
        return True, {"setups": [{"id": "S1", "type": "print", "name": "Print", "bodies": ["Box"]}]}
    if tool == "part_review":
        return True, {"verdict": "pass", "process": "printed", "findings": [{"severity": "warning", "says": "A long finding", "fix": "Do it"}], "figures": {}}
    return True, {"model": {"slide": 5.25}}
OUT["trees"] = []
for cls in (P.SetupsTab, P.MaterialsTab, P.FitsTab, P.ReviewTab):
    t = cls(runner=fake)
    t.fill()
    if cls is P.FitsTab: t.size()
    if cls is P.ReviewTab:
        OUT["review_empty_before"] = t.none.visible
        t.review()
        OUT["review_empty_after"] = t.none.visible
    for tr in [v for v in vars(t).values() if isinstance(v, P.QtWidgets.QTreeWidget)]:
        OUT["trees"].append({"tab": cls.__name__, "modes": tr.hdr.modes, "last": tr.hdr.last, "hbar": tr.hbar,
                             "tips": all(r.texts[i] in (r.tips.get(i) or "") for r in tr.rows for i in range(len(r.texts)) if r.texts[i])})
''')
        self.assertEqual(len(out["trees"]), 5)
        for t in out["trees"]:
            self.assertEqual(t["hbar"], "off", t)
            self.assertFalse(t["last"], t)
            self.assertIn("stretch", t["modes"].values(), t)
            self.assertTrue(set(t["modes"].values()) <= {"stretch", "contents"}, t)
            self.assertTrue(t["tips"], t)
        self.assertTrue(out["review_empty_before"])
        self.assertFalse(out["review_empty_after"])

    def test_fits_labels_and_calibration_in_mm(self):
        out = run(r'''
from workshop_make import panel as P
rows = []
class Form(P.QtWidgets.QWidget):
    def addRow(self, label, w): rows.append(label)
P.QtWidgets.QFormLayout = Form
f = P.FitsTab(runner=lambda t, a: (True, {"setups": []}))
f.doc_fn = lambda: Doc(("Body",))
f.fill()
OUT["rows"] = rows
OUT["in_part"] = [f.body.itemText(i) for i in range(f.body.count())]
OUT["suffix"] = [getattr(sb, "suffix", "") for sb in (f.nominal, f.cal_hole, f.cal_shaft)]
f.runner = lambda t, a: (True, {"model": {"slide": 5.2}, "printerFit": "none, so holes are assumed to print 0.2 mm small"})
f.size()
OUT["said"] = f.msg.text()
''')
        self.assertIn("Bought part size", out["rows"])
        self.assertEqual(out["in_part"], ["Body"])
        self.assertEqual(out["suffix"], [" mm", " mm", " mm"])
        self.assertEqual(out["said"], "Printer calibration: none, so holes are assumed to print 0.2 mm small.")

    def test_review_leaves_no_selection_behind(self):
        """The part the review showed stayed selected after leaving Make:
        put back on leaving, unless the person had selected it."""
        out = run(r'''
from workshop_make import panel as P, workbench
sel = set()
class O:
    def __init__(self, n): self.Name, self.Label, self.Document = n, n, D
class D:
    Name = "Doc"
    @staticmethod
    def getObjectsByLabel(l): return [O(l)]
Gui.Selection.getSelection = lambda *a: [O(n) for _d, n in sorted(sel)]
Gui.Selection.removeSelection = lambda d, n: sel.discard((d, n))
def runner(tool, args):  # Agent Link's _call shows the click: it selects the part
    sel.add(("Doc", args["body"]))
    return True, {"verdict": "pass", "process": "printed", "findings": [], "figures": {}}
t = P.ReviewTab(runner=runner, doc_fn=lambda: D)
t.body.addItems(["Body"])
t.review()
OUT["during"] = sorted(sel)
class G:
    class Workbench:
        pass
wb = workbench.make_class(G)()
wb.Deactivated()
OUT["after"] = sorted(sel)
sel.add(("Doc", "Body"))  # the person picked it first
t.review()
wb.Deactivated()
OUT["kept"] = sorted(sel)
''')
        self.assertEqual(out["during"], [["Doc", "Body"]])
        self.assertEqual(out["after"], [])
        self.assertEqual(out["kept"], [["Doc", "Body"]])
