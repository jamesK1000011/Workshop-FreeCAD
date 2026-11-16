# SPDX-License-Identifier: LGPL-2.1-or-later
# The one add-on loads as FreeCAD loads it: InitGui.py run in a fresh Python
# whose path holds only this repository and stand-ins for FreeCAD's own
# modules (no Agent Link). One workbench (Make), every part's commands
# registered once, the dropdowns, the manipulator placing the rest, no
# separate Parts, Electronics, Documents or SafetyNet workbench, and the
# Tools ▸ SafetyNet fallback by Qt for a FreeCAD without manipulators.
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

said, commands, benches, manips, icons, added = [], {}, [], [], [], []
FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=said.append, PrintWarning=said.append, PrintError=said.append, PrintLog=lambda m: None)
FreeCAD.ActiveDocument = None
class GuiStub(Stub):
    def __getattr__(self, k):
        if k == "addWorkbenchManipulator" and sys.argv[2] != "manipulators":
            raise AttributeError(k)  # a FreeCAD before workbench manipulators
        return Stub.__getattr__(self, k)

Gui = GuiStub("FreeCADGui")

class Workbench:
    def __init__(self):
        self.toolbars, self.menus = {}, {}
    def appendToolbar(self, name, cmds):
        self.toolbars[name] = list(cmds)
    def appendMenu(self, name, cmds):
        self.menus[name if isinstance(name, str) else "/".join(name)] = list(cmds)

Gui.Workbench = Workbench
def add_command(name, c):
    added.append(name)
    commands[name] = c
Gui.addCommand = add_command
Gui.addWorkbench = benches.append
Gui.addIconPath = icons.append
if sys.argv[2] == "manipulators":
    Gui.addWorkbenchManipulator = manips.append
else:
    connected = []
    class MW:
        class workbenchActivated:
            @staticmethod
            def connect(slot):
                connected.append(slot)
    Gui.getMainWindow = lambda: MW
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "TechDrawGui", "PySide", "PySide.QtGui", "PySide.QtCore"):
    sys.modules[n] = Stub(n)

path = sys.argv[1]
sys.path.insert(0, path)
# As FreeCAD runs it: its globals hold only FreeCAD, FreeCADGui and the
# builtins, and InitGui's own names land in a separate locals dict.
ns = {}
exec(compile(open(path + "/InitGui.py", encoding="utf-8").read(), path + "/InitGui.py", "exec"),
     {"__builtins__": __builtins__, "FreeCAD": FreeCAD, "FreeCADGui": Gui}, ns)
out = {"said": said, "how": ns.get("_WORKSHOP_MENUS"), "icons": icons, "added": added, "benches": []}
for b in benches:
    b.Initialize()
    out["benches"].append({"class": type(b).__name__, "MenuText": b.MenuText, "Icon": b.Icon, "classname": b.GetClassName(),
                           "toolbars": b.toolbars, "menus": b.menus})
out["commands"] = {k: c.GetResources().get("MenuText") for k, c in commands.items()}
out["groups"] = {k: list(c.GetCommands()) for k, c in commands.items() if hasattr(c, "GetCommands")}
out["menus"] = manips[0].modifyMenuBar() if manips else None
out["toolbars"] = manips[0].modifyToolBars() if manips else None
out["modules"] = sorted(m for m in sys.modules if m.split(".")[0] in ("agentlink", "addonkit"))
if sys.argv[2] != "manipulators":
    out["connected"] = len(connected)
print(json.dumps(out))
'''


def load(mode="manipulators"):
    r = subprocess.run([sys.executable, "-I", "-c", HARNESS, ROOT, mode], capture_output=True, text=True,
                       env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}, cwd=ROOT)
    if r.returncode:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Loads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = load()

    def test_one_workbench_make(self):
        out = self.out
        self.assertEqual(out["said"], [])
        self.assertEqual(out["how"], "manipulator")
        [b] = out["benches"]
        self.assertEqual((b["class"], b["MenuText"], b["classname"]), ("WorkshopMakeWorkbench", "Make", "Gui::PythonWorkbench"))
        self.assertTrue(os.path.isfile(b["Icon"]), b["Icon"])
        tb = b["toolbars"]
        self.assertEqual(list(tb), ["Setup", "Fits", "Hardware", "Output", "Printer", "Make Panels"])
        self.assertEqual(tb["Make Panels"], ["Workshop_Make_Panel", "Workshop_Documents_Panel"])
        on_make = {c for cmds in tb.values() for c in cmds}
        # What moved to FreeCAD's workbenches is not on Make's toolbars.
        for moved in ("Workshop_Make_Hole", "Workshop_Make_ThreadLookup", "Workshop_Make_DfmCheck", "Workshop_Make_PartReview",
                      "Workshop_Make_MassProperties", "Workshop_Parts_GridfinityBin", "Workshop_Documents_Drawing", "SafetyNet_Checkpoint"):
            self.assertNotIn(moved, on_make)
        self.assertEqual(b["menus"]["&Make"][-2:], ["Workshop_Make_Panel", "Workshop_Documents_Panel"])

    def test_every_part_registers_its_commands_once(self):
        out = self.out
        self.assertEqual(len(out["added"]), len(set(out["added"])), "a command registered twice")
        names = set(out["commands"])
        for want in ("Workshop_Parts_GridfinityBin", "Workshop_Parts_BoardBox", "Workshop_Make_NewSetup", "Workshop_Make_Hole",
                     "Workshop_Electronics_ImportBoard", "Workshop_Documents_Drawing", "Workshop_Documents_Panel",
                     "SafetyNet_Checkpoint", "SafetyNet_Recover", "SafetyNet_Menu", "Workshop_Parts_Group", "Workshop_Make_Checks"):
            self.assertIn(want, names)
        self.assertEqual(out["groups"]["Workshop_Make_Checks"], ["Workshop_Make_DfmCheck", "Workshop_Make_PartReview", "Workshop_Make_MassProperties"])
        self.assertEqual(len(out["groups"]["Workshop_Parts_Group"]), 4)
        for d in ("workshop_parts", "workshop_make", "workshop_electronics", "workshop_documents", "safetynet"):
            self.assertIn(os.path.join(ROOT, d, "icons"), out["icons"])

    def test_manipulator_places_the_rest(self):
        out = self.out
        self.assertIn({"insert": "SafetyNet_Menu", "menuItem": "Std_DlgCustomize"}, out["menus"])
        self.assertIn({"insert": "Workshop_Make_Hole", "toolItem": "PartDesign_Groove"}, out["toolbars"])
        self.assertIn({"insert": "Workshop_Electronics_ImportBoard", "menuItem": "Std_Export"}, out["menus"])
        # Every command placed is a registered one (or a separator).
        for e in out["menus"] + out["toolbars"]:
            cmd = e.get("insert") or e.get("append")
            self.assertTrue(cmd == "Separator" or cmd in out["commands"], cmd)

    def test_never_imports_agent_link(self):
        self.assertEqual(self.out["modules"], [])

    def test_qt_fallback_without_manipulators(self):
        out = load("qt")
        self.assertEqual(out["how"], "qt")
        self.assertEqual(out["connected"], 1)
        self.assertEqual(len(out["benches"]), 1)


if __name__ == "__main__":
    unittest.main()
