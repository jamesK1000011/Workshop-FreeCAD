# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make loads with no other Mod folder present: InitGui.py run the way
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
        self.assertEqual((b["class"], b["MenuText"], b["classname"]), ("WorkshopMakeWorkbench", "Workshop Make", "Gui::PythonWorkbench"))
        self.assertEqual(list(b["toolbars"]), ["Setup", "Check", "Fits", "Hardware", "Output", "Printer"])
        self.assertEqual(b["toolbars"]["Check"], ["Workshop_Make_DfmCheck", "Workshop_Make_PartReview", "Workshop_Make_MassProperties"])
        self.assertEqual(b["toolbars"]["Printer"], ["Workshop_Make_PrinterStatus", "Workshop_Make_PrinterSend"])
        self.assertIn("Workshop_Make_Panel", b["menus"]["&Make"])
        self.assertEqual(set(out["commands"]), set(b["menus"]["&Make"]))
    def test_nothing_else_loaded(self):
        out = load()
        self.assertEqual(out["said"], [])
        self.assertEqual([m for m in out["modules"] if m.split(".")[0] != "workshop_make"], [])
    def test_echo_names_its_bench(self):
        import ast
        import glob

        benches = set()
        for f in glob.glob(os.path.join(ROOT, "workshop_make", "fam_*.py")):
            for n in ast.parse(open(f, encoding="utf-8").read()).body:
                if isinstance(n, ast.Assign) and any(getattr(x, "id", None) == "WORKBENCHES" for x in n.targets):
                    benches |= set(ast.literal_eval(n.value).values())
        self.assertEqual(benches, {"WorkshopMakeWorkbench"})

# Changing tools with no button of their own (the agent's; the panel's tabs
# use some of them: part_spec in Materials).
NO_BUTTON = {"part_spec", "hw_embed_list", "hw_unembed", "mass_ballast", "mass_target", "mass_calibrate", "thread_cut",
             "slice_with", "slice_open", "slicer_presets", "printer_add", "printer_pause", "printer_stop", "fea_frame",
             "cut_check", "mill_check", "slice_read", "thread_identify", "printer_list"}


def declared(name):
    import ast
    import glob

    out = {}
    for f in glob.glob(os.path.join(ROOT, "workshop_make", "fam_*.py")):
        for n in ast.parse(open(f, encoding="utf-8").read()).body:
            if isinstance(n, ast.Assign) and any(getattr(x, "id", None) == name for x in n.targets):
                out.update(ast.literal_eval(n.value))
    return out


class Echo(unittest.TestCase):
    def test_every_button_is_declared_and_only_those(self):
        with open(os.path.join(ROOT, "workshop_make", "data", "tools.json"), encoding="utf-8") as f:
            tools = json.load(f)["entries"]
        cmds, benches = declared("COMMANDS"), declared("WORKBENCHES")
        self.assertEqual(set(benches), set(cmds), "a bench switch only where the tool has a button")
        registered = set(load()["commands"])
        self.assertEqual({v for v in cmds.values() if v not in registered}, set())
        self.assertEqual({k for k in cmds if k not in tools}, set())
        changing = {k for k, v in tools.items() if v.get("changes")}
        self.assertEqual({k for k in changing if k not in cmds and k not in NO_BUTTON}, set())
        self.assertEqual({k for k in NO_BUTTON & set(cmds)}, set())

    def test_args_pick_the_button(self):
        from _stubs import run

        out = run(r'''
al = types.ModuleType("agentlink"); pr = types.ModuleType("agentlink.protocol")
class ToolError(Exception):
    def __init__(self, code, message): super().__init__(message); self.code, self.message = code, message
pr.ToolError = ToolError; al.protocol = pr
sys.modules.update({"agentlink": al, "agentlink.protocol": pr})
from workshop_make import fam_fits, fam_make
OUT["fits"] = [fam_fits.command_for(*c) for c in (("fit", {"action": "calibrate"}), ("fit", {"action": "size"}), ("hw_hole", {}))]
OUT["make"] = [fam_make.command_for(*c) for c in (("setup", {"action": "add"}), ("setup", {"action": "set"}), ("setup", {"action": "remove"}), ("part_review", {}))]
''')
        self.assertEqual(out["fits"], ["Workshop_Make_Calibrate", "Workshop_Make_FitSize", "Workshop_Make_Hole"])
        self.assertEqual(out["make"], ["Workshop_Make_NewSetup", "Workshop_Make_AddBody", "Workshop_Make_RemoveSetup", "Workshop_Make_PartReview"])

if __name__ == "__main__":
    unittest.main()
