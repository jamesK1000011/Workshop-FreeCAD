# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Electronics loads with no other Mod folder present: InitGui.py run the way
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

Gui.Workbench = Workbench
Gui.addCommand = lambda name, c: commands.__setitem__(name, c)
Gui.addWorkbench = benches.append
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "PySide", "PySide.QtGui", "PySide.QtCore"):
    sys.modules[n] = Stub(n)

path = sys.argv[1]
sys.path.insert(0, path)
exec(compile(open(path + "/InitGui.py", encoding="utf-8").read(), path + "/InitGui.py", "exec"), {"__name__": "__main__"})
out = {"said": said, "benches": []}
for b in benches:
    b.Initialize()
    out["benches"].append({"class": type(b).__name__, "MenuText": b.MenuText, "classname": b.GetClassName(), "toolbars": b.toolbars, "menus": b.menus})
out["commands"] = {k: c.GetResources().get("MenuText") for k, c in commands.items()}
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
    def test_its_own_workbench(self):
        out = load()
        [b] = out["benches"]
        self.assertEqual((b["class"], b["MenuText"], b["classname"]), ("WorkshopElectronicsWorkbench", "Workshop Electronics", "Gui::PythonWorkbench"))
        names = sorted(out["commands"])
        self.assertEqual(len(names), 1)
        self.assertEqual(sorted(b["toolbars"]["Electronics"]), names)
        self.assertEqual(sorted(b["menus"]["&Electronics"]), names)
    def test_nothing_else_loaded(self):
        out = load()
        self.assertEqual(out["said"], [])
        self.assertEqual([m for m in out["modules"] if m.split(".")[0] != "workshop_electronics"], [])

    def test_echo_names_its_bench_and_buttons(self):
        out = load("workshop_electronics.fam_electronics")
        self.assertEqual(set(out["WORKBENCHES"].values()), {"WorkshopElectronicsWorkbench"})
        self.assertLessEqual(set(out["COMMANDS"].values()), set(out["commands"]))

if __name__ == "__main__":
    unittest.main()
