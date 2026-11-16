# SPDX-License-Identifier: LGPL-2.1-or-later
# Every Workshop task panel and dock page fits FreeCAD's Tasks dock
# (narrow.WIDTH, 320 px): built over a measuring stand-in Qt
# (tests/_narrowqt.py), each one's minimum width is worked out as Qt's
# layouts do it (the widest row: label and field, or the field alone where a
# long row wraps) and must not pass it; long labels wrap; nothing sets a fixed
# width. Live on FreeCAD 1.1.3 Hole for Hardware ran ~140 px past the dock,
# clipping its OK button. Also: Hole for Hardware starts on the part, point,
# face and direction picked.
import json
import os
import subprocess
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)

PRELUDE = r'''
import json, sys, types
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import _narrowqt as N
N.install()

class Stub(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        v = Stub(f"{self.__name__}.{k}")
        setattr(self, k, v)
        return v
    def __call__(self, *a, **k):
        return Stub(self.__name__ + "()")

class V:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z

class Shape:
    def __init__(self, solid=True, normal=(0, 0, 1)):
        self.Solids, self.n = ([1] if solid else []), normal
    def isNull(self): return False
    def getElement(self, name):
        n = self.n
        return types.SimpleNamespace(Surface=types.SimpleNamespace(parameter=lambda p: (0.0, 0.0)), normalAt=lambda u, v: V(*n))

class Obj:
    def __init__(self, label, type_id="Part::Feature", parent=None, solid=True):
        self.Label = self.Name = label
        self.Shape, self.InList, self.Visibility, self.TypeId = Shape(solid), [], True, type_id
        self.parent, self.Group, self.Tip = parent, [], None
    def getParentGeoFeatureGroup(self): return self.parent
    def isDerivedFrom(self, t): return self.TypeId == t
    def getSubObject(self, sub, ret=0):
        o = self
        for name in [p for p in sub.split(".") if p]:
            o = next((c for c in o.Group if c.Name == name), None)
            if o is None:
                return None
        return o

class Doc:
    def __init__(self, objs):
        self.Objects = objs
        self.Meta, self.FileName, self.Name = {}, "", "Doc"
    def openTransaction(self, n): pass
    def commitTransaction(self): pass
    def abortTransaction(self): pass
    def recompute(self): pass
    def getObjectsByLabel(self, l): return [o for o in self.Objects if o.Label == l]

FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=lambda m: None, PrintWarning=lambda m: None, PrintError=lambda m: None, PrintLog=lambda m: None)
FreeCAD.GuiUp = False
FreeCAD.ParamGet = lambda p: types.SimpleNamespace(GetUnsigned=lambda n, d=0: 0, GetString=lambda n, d="": d, GetBool=lambda n, d=False: d, GetInt=lambda n, d=0: d, GetFloat=lambda n, d=0.0: d)
# Long part names: a combo must not take its width from them.
FreeCAD.ActiveDocument = Doc([Obj("Raspberry Pi 5 enclosure lid with vents and clips"), Obj("Mounting bracket, left hand, 3 mm PETG")])
FreeCAD.Vector = V
Gui = Stub("FreeCADGui")
SEL = []
Gui.Selection = types.SimpleNamespace(getSelectionEx=lambda *a: list(SEL), getSelection=lambda *a: [s.Object for s in SEL])
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "TechDrawGui"):
    sys.modules[n] = Stub(n)
OUT = {}
quiet = lambda tool, args=None, **k: (True, {"setups": [{"id": "S1", "name": "A print setup with a long name for the narrow dock"}]})
'''


def run(code):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "HOME": os.environ.get("HOME", "/tmp"),
           "AGENTLINK_HOME": os.environ.get("AGENTLINK_HOME", ""), "WORKSHOP_FASTENERS": "off"}
    src = PRELUDE + code + "\nprint(json.dumps(OUT, default=str))\n"
    r = subprocess.run([sys.executable, "-I", "-c", src, ROOT, TESTS], capture_output=True, text=True, env=env, cwd=ROOT)
    if r.returncode:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Fits(unittest.TestCase):
    def check(self, out):
        from workshop import narrow

        self.assertTrue(out)
        for name, rep in out.items():
            with self.subTest(panel=name):
                self.assertLessEqual(rep["width"], narrow.WIDTH, f"{name} asks {rep['width']} px; widest: {rep['worst']}")
                self.assertEqual(rep["unwrapped"], [], f"{name}: long labels that do not wrap")
                self.assertEqual(rep["fixed"], [], f"{name}: fixed widths")

    def test_make_task_panels(self):
        out = run(r'''
from workshop_make import taskpanels as T
T.screw_offered = lambda p: p == "hole"  # Fasteners installed: the checkbox and its type shown
for name in T.PANELS:
    N.FIXED_CALLS.clear()
    p = T.FormPanel(name, runner=quiet)
    OUT[name] = N.report(p.form)
''')
        self.assertIn("hole", out)
        self.check(out)

    def test_make_hole_was_too_wide_before(self):
        # The model reproduces the live finding: the old layout (X, Y, Z
        # across, combos sized to their longest entry, the screw's checkbox
        # and type side by side, rows never wrapped) is far past the dock.
        out = run(r'''
Q = N
f = Q.QWidget(); lay = Q.QFormLayout(f)
row = Q.QWidget(); h = Q.QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0)
for k in range(3):
    sb = Q.QDoubleSpinBox(); sb.setRange(-100000, 100000); sb.setDecimals(3); sb.setPrefix("XYZ"[k] + " "); sb.setSuffix(" mm"); h.addWidget(sb)
lay.addRow("Enters at", row)
OUT["old"] = N.report(f)
''')
        self.assertGreater(out["old"]["width"], 355)

    def test_make_tabs(self):
        out = run(r'''
from workshop_make import panel as P
for cls in (P.SetupsTab, P.MaterialsTab, P.FitsTab, P.ReviewTab):
    N.FIXED_CALLS.clear()
    t = cls(runner=quiet)
    try:
        t.fill()
    except Exception:
        pass
    OUT[cls.__name__] = N.report(t)
''')
        self.assertEqual(len(out), 4)
        self.check(out)

    def test_documents(self):
        out = run(r'''
from workshop_documents import taskpanels as T
from workshop_documents import panel as P
for name in T.PANELS:
    N.FIXED_CALLS.clear()
    OUT[name] = N.report(T.FormPanel(name, runner=quiet).form)
N.FIXED_CALLS.clear()
OUT["ManualTab"] = N.report(P.ManualTab(runner=quiet))
''')
        self.assertIn("patent", out)
        self.check(out)

    def test_electronics_kicad_board(self):
        out = run(r'''
from workshop_electronics import taskpanels as T
OUT["kicad"] = N.report(T.ImportBoardPanel(None, "").form)
''')
        self.check(out)

    def test_parts_generators(self):
        out = run(r'''
from workshop_parts import api, commands as C, form
for g in api.NAMES:
    N.FIXED_CALLS.clear()
    p = form.TaskPanel(C.title(api.NAMES[g]), api.params(g), C.TIPS[g], labels=C.LABELS.get(g), columns=C.COLUMNS.get(g), needs=C.NEEDS.get(g))
    OUT[g] = N.report(p.form)
''')
        self.assertIn("gridfinity_baseplate", out)
        self.assertIn("board_box", out)
        self.check(out)

    def test_safetynet(self):
        out = run(r'''
from safetynet import panel as P
for hosted in (True, False):
    N.FIXED_CALLS.clear()
    w = P.widget(lambda tool, args=None, **k: (True, {}), hosted=hosted)
    OUT[f"session hosted={hosted}"] = N.report(w)
''')
        self.check(out)


class HoleStartsOnThePick(unittest.TestCase):
    # Live on 1.1.3: a face of Body picked (Hole.Face5), Part stayed
    # "Choose a part" while Enters at took the point.
    SETUP = r'''
body = Obj("Body", "PartDesign::Body")
pad = Obj("Pad", "PartDesign::Pad", parent=body)
hole = Obj("Hole", "PartDesign::Hole", parent=body)
hole.Shape = Shape(normal=(1, 0, 0))  # a side face: the hole goes in along -X
body.Group, body.Tip = [pad, hole], hole
# Something built from the Body (a derived solid) keeps it out of the parts
# list; the pick still names it.
copy = Obj("Body copy")
body.InList = [copy]
other = Obj("Bracket")
FreeCAD.ActiveDocument = Doc([body, pad, hole, copy, other])
from workshop_make import taskpanels as T
'''

    def test_resolved_pick(self):
        out = run(self.SETUP + r'''
SEL[:] = [types.SimpleNamespace(Object=hole, SubElementNames=["Face5"], PickedPoints=[V(10.2651, 7.7624, 5.0)])]
p = T.FormPanel("hole", runner=quiet)
v = p.values()
OUT.update(body=v["body"], at=v["at"], dir=v["dir"], entry=p.entry, on=p.on.text())
''')
        self.assertEqual(out["body"], "Body")
        self.assertEqual(out["at"], [10.265, 7.762, 5.0])
        self.assertEqual(out["entry"], {"face": "Face5"})
        self.assertEqual(out["on"], "Face5 of Body")
        self.assertEqual(out["dir"], "-x")

    def test_pick_on_the_body_by_path(self):
        out = run(self.SETUP + r'''
SEL[:] = [types.SimpleNamespace(Object=body, SubElementNames=["Hole.Face5"], PickedPoints=[V(1, 2, 3)])]
p = T.FormPanel("hole", runner=quiet)
OUT.update(body=p.values()["body"], entry=p.entry)
OUT["owner_pad"] = T.owner(pad).Label
OUT["owner_plain"] = T.owner(other).Label
OUT["owner_none"] = T.owner(None)
''')
        self.assertEqual(out["body"], "Body")
        self.assertEqual(out["entry"], {"face": "Face5"})
        self.assertEqual(out["owner_pad"], "Body")
        self.assertEqual(out["owner_plain"], "Bracket")
        self.assertIsNone(out["owner_none"])

    def test_no_pick(self):
        out = run(self.SETUP + r'''
p = T.FormPanel("hole", runner=quiet)
OUT.update(body=p.values()["body"], on=hasattr(p, "on"), dir=p.values()["dir"])
''')
        self.assertEqual(out["body"], "")  # "Choose a part": several, none picked
        self.assertFalse(out["on"])
        self.assertEqual(out["dir"], "-z")

    def test_axis_and_items(self):
        out = run(r'''
from workshop_make import taskpanels as T
OUT["axes"] = [T.axis_into(n) for n in ([0, 0, 1], [0, 0, -1], [1, 0, 0], [0, -1, 0], [0.7, 0.7, 0], None)]
OUT["items"] = T.body_items(["A", "B"], "Body")
OUT["kept"] = T.body_items(["A", "B"], "B")
''')
        self.assertEqual(out["axes"], ["-z", "+z", "-x", "+y", None, None])
        self.assertEqual(out["items"], [[["Body", "Body"], ["A", "A"], ["B", "B"]], 0])
        self.assertEqual(out["kept"], [[["A", "A"], ["B", "B"]], 1])


if __name__ == "__main__":
    unittest.main()
