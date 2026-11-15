# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents loads with no other Mod folder present: InitGui.py run the way
# FreeCAD runs it, in a fresh Python whose path holds only this add-on and
# stand-ins for FreeCAD's own modules — no other Workshop add-on, no Agent
# Link.
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HARNESS = r'''
import json, sys, types

class Stub(types.ModuleType):
    """A FreeCAD module stand-in: any name is a callable stand-in."""
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        v = Stub(f"{self.__name__}.{k}")
        setattr(self, k, v)
        return v
    def __call__(self, *a, **k):
        return Stub(self.__name__ + "()")

said, commands, benches = [], {}, []
FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=said.append, PrintWarning=said.append, PrintError=said.append, PrintLog=lambda m: None)
FreeCAD.ActiveDocument = None
Gui = Stub("FreeCADGui")

class Workbench:
    def __init__(self):
        self.toolbars, self.menus = {}, {}
    def appendToolbar(self, name, cmds):
        self.toolbars[name] = list(cmds)
    def appendMenu(self, name, cmds):
        self.menus[name if isinstance(name, str) else "/".join(name)] = list(cmds)
    def Activated(self):
        pass
    def Deactivated(self):
        pass

Gui.Workbench = Workbench
Gui.addCommand = lambda name, c: commands.__setitem__(name, c)
Gui.addWorkbench = benches.append
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "TechDrawGui", "PySide", "PySide.QtGui", "PySide.QtCore"):
    sys.modules[n] = Stub(n)

path = sys.argv[1]
sys.path.insert(0, path)
# As FreeCAD runs it: its globals hold only FreeCAD, FreeCADGui and the
# builtins, and InitGui's own names land in a separate locals dict.
exec(compile(open(path + "/InitGui.py", encoding="utf-8").read(), path + "/InitGui.py", "exec"),
     {"__builtins__": __builtins__, "FreeCAD": FreeCAD, "FreeCADGui": Gui}, {})
out = {"said": said, "benches": []}
for b in benches:
    b.Initialize()
    b.Activated()
    out["benches"].append({"class": type(b).__name__, "MenuText": b.MenuText, "Icon": b.Icon, "ToolTip": b.ToolTip, "classname": b.GetClassName(), "toolbars": b.toolbars, "menus": b.menus})
out["commands"] = {k: c.GetResources().get("MenuText") for k, c in commands.items()}
out["pixmaps"] = {k: c.GetResources().get("Pixmap") for k, c in commands.items()}
out["modules"] = sorted(m for m in sys.modules if m.split(".")[0].startswith(("workshop_", "agentlink", "addonkit")))
fam = sys.argv[2] if len(sys.argv) > 2 else ""
if fam:
    import importlib
    m = importlib.import_module(fam)
    out["WORKBENCHES"] = getattr(m, "WORKBENCHES", None)
    out["COMMANDS"] = getattr(m, "COMMANDS", None)
    if hasattr(m, "command_for"):
        out["command_for"] = [m.command_for(*c) for c in json.loads(sys.argv[3])]
print(json.dumps(out))
'''


def load(fam="", calls=()):
    r = subprocess.run([sys.executable, "-I", "-c", HARNESS, ROOT] + ([fam, json.dumps(list(calls))] if fam else []), capture_output=True, text=True,
                       env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": ""}, cwd=ROOT)
    if r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class LoadsAlone(unittest.TestCase):
    def test_initgui_runs_as_freecad_runs_it(self):
        # exec(code, FreeCAD's globals, {}): the bench's class and method
        # bodies must not need InitGui's own names (real FreeCAD's
        # "name '_ICONS' is not defined").
        [b] = load()["benches"]
        self.assertEqual(b["classname"], "Gui::PythonWorkbench")
        self.assertEqual(b["Icon"], os.path.join(ROOT, "workshop_documents", "icons", "Workshop_Documents_Workbench.svg"))
        self.assertTrue(os.path.isfile(b["Icon"]))
        self.assertEqual(b["ToolTip"], "Drawings and documents from the bodies: dimensioned sheets, assembly manuals, patent figures, library packs (Workshop for FreeCAD)")

    def test_its_own_workbench(self):
        out = load()
        [b] = out["benches"]
        self.assertEqual((b["class"], b["MenuText"], b["classname"]), ("WorkshopDocumentsWorkbench", "Workshop Documents", "Gui::PythonWorkbench"))
        self.assertEqual(list(b["toolbars"]), ["Drawings", "Share", "Patent"])
        self.assertEqual(b["toolbars"]["Drawings"], ["Workshop_Documents_Drawing", "Workshop_Documents_Exploded"])
        self.assertIn("Workshop_Documents_Panel", b["menus"]["&Documents"])
        self.assertEqual(set(out["commands"]), set(b["menus"]["&Documents"]))
    def test_nothing_else_loaded(self):
        out = load()
        self.assertEqual(out["said"], [])
        self.assertEqual([m for m in out["modules"] if m.split(".")[0] != "workshop_documents"], [])

class Echo(unittest.TestCase):
    def test_buttons_declared_are_techdraw_buttons(self):
        import ast

        decl = {}
        for f in ("fam_drawing.py", "fam_share.py"):
            for n in ast.parse(open(os.path.join(ROOT, "workshop_documents", f), encoding="utf-8").read()).body:
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("WORKBENCHES", "COMMANDS", "PAGES"):
                    decl.setdefault(n.targets[0].id, {}).update(dict.fromkeys(ast.literal_eval(n.value)) if n.targets[0].id == "PAGES" else ast.literal_eval(n.value))
        self.assertEqual(decl["WORKBENCHES"], {"drawing_": "TechDrawWorkbench"})
        self.assertEqual(list(decl["PAGES"]), ["drawing_"])
        with open(os.path.join(ROOT, "workshop_documents", "data", "tools.json"), encoding="utf-8") as f:
            tools = json.load(f)["entries"]
        for tool, cmd in decl["COMMANDS"].items():
            self.assertIn(tool, tools)
            self.assertTrue(tool.startswith("drawing_") and cmd.startswith("TechDraw_"), (tool, cmd))


if __name__ == "__main__":
    unittest.main()
