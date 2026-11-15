# SPDX-License-Identifier: LGPL-2.1-or-later
# Documents' Manual tab, task panels and runner, under stand-ins for FreeCAD
# and Qt (no FreeCAD, no Agent Link): the tab builds over any runner; "Make
# manual" uses a manual_maker service when one is given and falls back to
# drawing_exploded when none is; the local runner answers what the Agent
# Link panel's _call answers; the task panels' values become the tools'
# arguments.
import ast
import glob
import os
import unittest

from _stubs import ROOT, run

TAB = r'''
from workshop_documents import panel as P
calls = []
def fake(tool, args):
    calls.append([tool, args])
    if tool == "drawing_exploded":
        return True, {"steps": args["steps"], "bom": [1, 2], "manual": "/tmp/Box_assembly.md"}
    return False, {"error": {"code": "invalid_input", "message": "no"}}
class Panel:  # what Agent Link hands a register_tab factory
    _call = staticmethod(fake)
class Maker:  # an add-on's manual_maker service
    def __init__(self): self.seen = []
    def make(self, runner, rows, title):
        self.seen.append([rows, title])
        ok, _ = runner("manual_plan", {"steps": len(rows)})
        return True, {"steps": 2, "file": {"path": "/tmp/m.html"}, "credit": "Manual by a maker", "lint": []}
OUT["orders"] = [[t, o] for t, _c, o in P.HOSTED]
svc = {"now": None}
tab = P.factory(P.ManualTab, lambda: svc["now"])(Panel())
OUT["name"] = tab.objectName()
tab.fill()
OUT["parts"] = [it.text() for it in tab.parts.rows]
tab.make()
OUT["empty"] = tab.msg.text()
tab.add()
OUT["none_ticked"] = tab.msg.text()
tab.parts.rows[0].setCheckState(2); tab.title.setText("Base"); tab.add()
OUT["left"] = [it.text() for it in tab.parts.rows]
tab.parts.rows[0].setCheckState(2); tab.note.setText("screws in"); tab.add()
OUT["rows"] = [r.texts for r in tab.steps.rows]
tab.name.setText("Box")
tab.make()
OUT["fallback"] = [tab.msg.text(), tab.credit.text(), tab.file]
m = Maker(); svc["now"] = m
tab.make()
OUT["service"] = [tab.msg.text(), tab.credit.text(), tab.file]
OUT["seen"] = m.seen
OUT["calls"] = calls
alone = P.ManualTab(runner=fake)
OUT["alone_service"] = alone.service
'''


class Manual(unittest.TestCase):
    def test_hidden_parts_listed_and_empty_lines(self):
        out = run(r'''
from workshop_documents import panel as P
doc = Doc()
doc.Objects[0].Visibility = False
OUT["parts"] = P.parts(doc)
t = P.ManualTab(runner=lambda tool, a: (True, {}), doc_fn=lambda: Doc(()))
shown = []
t.no_parts.setVisible = shown.append
t.fill()
OUT["empty"] = [t.no_parts.text(), shown, t.no_steps.text()]
''')
        self.assertEqual(out["parts"], ["Box", "Lid"])
        self.assertEqual(out["empty"], ["No parts in the document yet.", [True], "No steps yet: tick the parts that go on first, then Add Step."])

    def test_tab_falls_back_then_uses_the_service(self):
        out = run(TAB)
        self.assertEqual(out["orders"], [["Manual", 40]])
        self.assertEqual(out["name"], "DocumentsManual")
        self.assertEqual(out["parts"], ["Box", "Lid"])
        self.assertEqual(out["empty"], "Add a step first.")
        self.assertEqual(out["none_ticked"], "Tick the parts this step adds.")
        self.assertEqual(out["left"], ["Lid"])
        self.assertEqual(out["rows"], [["1", "Base", "Box", ""], ["2", "Step 2", "Lid", "screws in"]])
        # No service: Documents' own drawing_exploded, the steps as it takes them.
        self.assertEqual(out["calls"][0], ["drawing_exploded", {"steps": [{"title": "Base", "add": ["Box"]}, {"title": "Step 2", "add": ["Lid"], "note": "screws in"}], "name": "Box"}])
        self.assertEqual(out["fallback"], ["2 steps, 2 items — /tmp/Box_assembly.md", "", "/tmp/Box_assembly.md"])
        # A service: it is given the rows, the title and the runner; its credit shown.
        self.assertEqual(out["seen"], [[[{"title": "Base", "bodies": ["Box"], "note": ""}, {"title": "Step 2", "bodies": ["Lid"], "note": "screws in"}], "Box"]])
        self.assertEqual(out["calls"][1], ["manual_plan", {"steps": 2}])
        self.assertEqual(len(out["calls"]), 2)
        self.assertEqual(out["service"], ["2 steps — /tmp/m.html", "Manual by a maker", "/tmp/m.html"])
        self.assertIsNone(out["alone_service"])

    def test_make_manual_without_qt(self):
        out = run(r'''
from workshop_documents import panel as P
rows = [{"title": "A", "bodies": ["Box"], "note": ""}, {"title": "B", "bodies": [], "note": ""}]
OUT["steps"] = P.exploded_steps(rows)
r = lambda t, a: (False, {"error": {"code": "not_found", "message": "Nope"}})
OUT["refused"] = P.make_manual(r, rows)[2]
class Bad:
    def make(self, runner, rows, title): return False, {"error": {"code": "failed", "message": "broke"}}
OUT["svc_refused"] = P.make_manual(r, rows, "T", Bad())[2]
''')
        self.assertEqual(out["steps"], [{"title": "A", "add": ["Box"]}])
        self.assertEqual(out["refused"], ["Nope", None, None])
        self.assertEqual(out["svc_refused"], ["broke", None, None])


PARITY = r'''
from workshop_documents import handlers, runner as R

def hosted(doc):
    """What Agent Link's panel._call does with a Documents tool."""
    s = R.Session(doc)
    table = handlers.bound(s)
    def call(tool, args):
        if tool not in table:
            return False, {"error": {"code": "not_found", "message": f"{tool}: not a tool of Workshop Documents."}}
        ch = R.changes(tool)
        if ch: doc.openTransaction(tool)
        try:
            out = table[tool](dict(args))
        except Exception as e:
            if ch: doc.abortTransaction()
            return False, {"error": {"code": getattr(e, "code", "failed"), "message": getattr(e, "message", str(e))}}
        if ch: doc.commitTransaction()
        return True, json.loads(json.dumps(out))
    return call

CALLS = [("drawing_exploded", {}), ("drawing_exploded", {"steps": [{"title": "A", "add": ["Box"]}], "direction": "sideways"}),
         ("nope_tool", {})]
docs = {"alone": Doc(), "hosted": Doc()}
runners = {"alone": R.local(lambda: docs["alone"]), "hosted": hosted(docs["hosted"])}
for k, r in runners.items():
    OUT[k] = [r(t, a) for t, a in CALLS]
    OUT[k + "_tx"] = docs[k].tx
'''


class Runner(unittest.TestCase):
    def test_alone_answers_as_hosted(self):
        out = run(PARITY)
        self.assertEqual(out["alone"], out["hosted"])
        self.assertEqual(out["alone_tx"], out["hosted_tx"])
        self.assertEqual([r[1]["error"]["code"] for r in out["alone"]], ["invalid_input", "invalid_input", "not_found"])


def _agentlink():
    import sys

    for p in sys.path:
        if os.path.isfile(os.path.join(p, "agentlink", "hooks.py")):
            return p
    return None


class Hosted(unittest.TestCase):
    @unittest.skipUnless(_agentlink(), "Agent Link is not on the path")
    def test_manual_tab_registered_and_service_asked(self):
        out = run(r'''
from agentlink import hooks
import workshop_documents.agentlink_families, workshop_documents
OUT["tabs"] = [[t["title"], t["order"]] for t in hooks.TABS]
OUT["hosted"] = workshop_documents._hosted
class Panel:
    _call = staticmethod(lambda t, a: (True, {"steps": a["steps"], "bom": [], "manual": "/tmp/x.md"}))
tab = hooks.TABS[0]["factory"](Panel())
OUT["built"] = type(tab).__name__
OUT["none"] = tab.service()
class Maker:
    def make(self, runner, rows, title): return True, {"steps": 1, "file": "/tmp/y.html", "credit": "c"}
m = hooks.provide("manual_maker", Maker())
OUT["given"] = tab.service() is m
''', extra_path=_agentlink())
        self.assertEqual(out["tabs"], [["Manual", 40]])
        self.assertTrue(out["hosted"])
        self.assertEqual(out["built"], "ManualTab")
        self.assertIsNone(out["none"])
        self.assertTrue(out["given"])


class TaskPanels(unittest.TestCase):
    def test_values_become_arguments(self):
        out = run(r'''
from workshop_documents import taskpanels as T
OUT["drawing"] = T.args_of("drawing", {"bodies": "", "views": "front, iso", "projection": "", "paper": "A3", "scale": 0.0, "name": "Box"})
OUT["exploded"] = T.args_of("exploded", {"steps": "Base: Box; Lid on: Lid, Screw", "explode": 0.0, "direction": "up", "name": ""})
OUT["library"] = T.args_of("library", {"bodies": "Box", "license": "MIT", "name": "", "description": "", "author": ""})
OUT["patent"] = T.args_of("patent", {"title": "A box", "field": "", "bodies": "", "name": ""})
OUT["panels"] = sorted(T.PANELS)
''')
        self.assertEqual(out["drawing"], ["drawing_make", {"views": ["front", "iso"], "paper": "A3", "name": "Box"}])
        self.assertEqual(out["exploded"], ["drawing_exploded", {"steps": [{"title": "Base", "add": ["Box"]}, {"title": "Lid on", "add": ["Lid", "Screw"]}], "direction": "up"}])
        self.assertEqual(out["library"], ["library_pack", {"bodies": ["Box"], "license": "MIT"}])
        self.assertEqual(out["patent"], ["patent_draft", {"title": "A box"}])
        self.assertEqual(out["panels"], ["drawing", "exploded", "library", "patent"])

    def test_form_panel_builds(self):
        out = run(r'''
from workshop_documents import taskpanels as T
for name in T.PANELS:
    OUT[name] = sorted(T.FormPanel(name, runner=lambda t, a: (True, {})).values())
''')
        self.assertEqual(out["exploded"], ["direction", "explode", "name", "steps"])
        self.assertEqual(out["library"], ["author", "bodies", "description", "license", "name"])

    def test_every_command_has_its_panel_or_tool(self):
        import json

        with open(os.path.join(ROOT, "workshop_documents", "data", "tools.json"), encoding="utf-8") as f:
            tools = set(json.load(f)["entries"])
        out = run(r'''
from workshop_documents import commands as C, taskpanels as T
OUT["forms"] = {n: c.panel for n, c in C.COMMANDS.items() if isinstance(c, C.Form)}
OUT["runs"] = {n: c.tool for n, c in C.COMMANDS.items() if isinstance(c, C.Run)}
OUT["panel_tools"] = {k: v[1] for k, v in T.PANELS.items()}
''')
        for panel in out["forms"].values():
            self.assertIn(out["panel_tools"][panel], tools)
        for tool in out["runs"].values():
            self.assertIn(tool, tools)
        covered = set(out["panel_tools"][p] for p in out["forms"].values()) | set(out["runs"].values())
        self.assertEqual(covered, tools, "a button for every Documents tool")


class Theme(unittest.TestCase):
    def test_accent_from_the_parameters_else_highlight(self):
        out = run(r'''
from workshop_documents import theme
OUT["hex"] = theme.hex_of(0x3A7BD5FF)
OUT["none"] = theme.hex_of(0)
OUT["roles"] = theme.roles(get=lambda n: {"ThemeAccentColor1": 0x112233FF}.get(n, 0))
OUT["fill"] = theme.fill("a @accent2 b @accent c @bad", {"accent": "#1", "accent2": "#2", "bad": "#3"})
''')
        self.assertEqual(out["hex"], "#3a7bd5")
        self.assertIsNone(out["none"])
        self.assertEqual(out["roles"]["accent"], "#112233")
        self.assertEqual(out["fill"], "a #2 b #1 c #3")


class Plain(unittest.TestCase):
    def test_no_agentlink_import_outside_the_family_layer(self):
        pkg = os.path.join(ROOT, "workshop_documents")
        for path in glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True):
            name = os.path.basename(path)
            if name in ("agentlink_families.py", "tooldata.py") or name.startswith("fam_"):
                continue
            for n in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                self.assertFalse(any(m.split(".")[0] == "agentlink" for m in mods), f"{name} imports {mods}")


if __name__ == "__main__":
    unittest.main()
