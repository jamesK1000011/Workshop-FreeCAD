# SPDX-License-Identifier: LGPL-2.1-or-later
# Mill Export on FreeCAD's CAM: the part's Job found (its model's clone of
# the part) or made with the stock and least tool, CAM's own Sanity report
# as the setup sheet with only Make's mill check added. CAM stood in for.
import unittest

from _stubs import run

FAKES = r'''
import types
from workshop_make import camjob as C
class O:
    def __init__(self, name, **kw):
        self.Name = self.Label = name
        self.__dict__.update(kw)
class D:
    def __init__(self, objs): self.Objects, self.removed = objs, []
    def removeObject(self, n): self.removed.append(n)
    def recompute(self): pass
'''


class Job(unittest.TestCase):
    def test_reuse_and_report(self):
        out = run(FAKES + r'''
part, other = O("Bracket"), O("Plate")
clone = O("Clone", Objects=[part])
job = O("Job", Proxy=1, Model=O("Model", Group=[clone]), Tools=O("Tools", Group=[]), Stock=None)
d = D([part, other, clone, job])
OUT["found"] = getattr(C.find_job(d, part), "Name", None)
OUT["none"] = C.find_job(d, other)
OUT["origin"] = C.stock_origin({"xmin": 0, "ymin": 0, "zmin": 0, "x": 20, "y": 10, "z": 5}, [24, 14, 7])
rep = "<html><body><h1>CAM Sanity</h1><p>Material: Not Specified</p></body></html>"
check = {"verdict": "fix", "leastWall": 0.6, "findings": [{"severity": "error", "rule": "reach", "says": "a pocket 30 mm deep, past the tool's reach"}],
         "assumed": {"tool": "Ø3 mm end mill"}}
OUT["html"] = C.extras(rep, check, "aluminium", "Bracket-mill.step")
OUT["html_mat"] = C.extras("<body>aluminium</body>", {"verdict": "pass"}, "aluminium", "x.step")
''')
        self.assertEqual(out["found"], "Job")
        self.assertIsNone(out["none"])
        self.assertEqual(out["origin"], [-2.0, -2.0, -1.0])
        h = out["html"]
        self.assertTrue(h.startswith("<html><body><h1>CAM Sanity</h1>"))
        self.assertTrue(h.endswith("</section></body></html>"))
        for bit in ("Workshop Make: mill check", "<b>fix</b>", "0.6 mm", "past the tool&#x27;s reach", "Stock material: aluminium", "Ø3 mm", "Bracket-mill.step"):
            self.assertIn(bit, h)
        self.assertNotIn("Stock material", out["html_mat"])

    def test_new_job_with_stock_and_tool(self):
        out = run(FAKES + r'''
made = []
bit = O("Bit", Diameter=6.0)
tc = O("TC", Tool=bit)
def create(name, base, tpl):
    j = O(name, Proxy=1, Model=O("Model", Group=base), Tools=O("Tools", Group=[tc]), Stock=O("Stock000"))
    made.append(j)
    return j
jm = types.ModuleType("Path.Main.Job"); jm.Create = create
sm = types.ModuleType("Path.Main.Stock"); sm.CreateBox = lambda job, ext, plc: O("Box", ext=ext, plc=plc)
path = types.ModuleType("Path"); main = types.ModuleType("Path.Main")
path.Main, main.Job, main.Stock = main, jm, sm
sys.modules.update({"Path": path, "Path.Main": main, "Path.Main.Job": jm, "Path.Main.Stock": sm})
F = sys.modules["FreeCAD"]
F.Vector = lambda *a: list(a)
F.Placement = lambda v, r: ("at", v)
F.Rotation = lambda: "r"
bb = types.SimpleNamespace(XMin=0, YMin=0, ZMin=0, XLength=20, YLength=10, ZLength=5)
part = O("Bracket", Shape=types.SimpleNamespace(BoundBox=bb))
d = D([part])
job, why = C.make_job(d, part, [24, 14, 7], 3.0, "Bracket mill")
OUT["job"] = [job.Label, job.Stock.ext, job.Stock.plc[1], bit.Diameter, d.removed, why]
OUT["labels"] = [tc.Label, bit.Label]
# The Job is made in FreeCAD's active document (Path.Main.Job.Create): the
# body's document is made the active one first.
d2 = D([part]); d2.Name = "Bracket_doc"
F.ActiveDocument = D([]); went = []
F.setActiveDocument = lambda n: went.append(n)
C.make_job(d2, part, [24, 14, 7], 3.0)
F.ActiveDocument = d2
C.make_job(d2, part, [24, 14, 7], 3.0)
OUT["active"] = went
jm.Create = lambda *a: (_ for _ in ()).throw(RuntimeError("no CAM here"))
OUT["fail"] = C.make_job(D([part]), part, [24, 14, 7], 3.0)[1]
''')
        self.assertEqual(out["active"], ["Bracket_doc"])
        self.assertEqual(out["job"], ["Bracket mill", [24, 14, 7], [-2.0, -2.0, -1.0], 3.0, ["Stock000"], None])
        self.assertIn("no CAM here", out["fail"])
        self.assertEqual(out["labels"], ["TC: 3 mm End Mill", "3 mm End Mill"])

    def test_the_tool_bits_new_body_is_recomputed(self):
        # Found live (16 Nov 2026, FreeCAD 1.1.3): after mill_export made a
        # Job, every later call's health said "3 objects not recomputed
        # yet" (Sketch001, Revolution, Endmill001). CAM's tool bit rebuilds
        # its body at the END of the recompute that follows a Diameter
        # change, copying new objects in; a second recompute takes them.
        out = run(FAKES + r'''
class Doc2(D):
    """A document whose first recompute ends with CAM's tool bit copying
    its new body in (objects that arrive touched), as FreeCAD does."""
    def __init__(self, objs, late):
        D.__init__(self, objs); self.late, self.runs = late, 0
    def recompute(self):
        self.runs += 1
        for o in self.Objects:
            o.State = []
        if self.runs == 1:
            for n in self.late:
                self.Objects.append(O(n, State=["Touched"]))
part = O("Block", State=[])
d = Doc2([part], ["Endmill001", "Sketch001", "Revolution"])
had = {o.Name for o in d.Objects}
d.recompute()
OUT["again"] = C.settle_new(d, had)
OUT["runs"] = d.runs
OUT["touched"] = [o.Name for o in d.Objects if "Touched" in o.State]
# Nothing new left touched: no second recompute. An object that was there
# before and is touched is not this call's to recompute.
old = O("Old", State=["Touched"])
d = Doc2([part, old], [])
had = {o.Name for o in d.Objects}
d.runs = 1
OUT["quiet"] = [C.settle_new(d, had), d.runs]
''')
        self.assertTrue(out["again"])
        self.assertEqual(out["runs"], 2)
        self.assertEqual(out["touched"], [])
        self.assertEqual(out["quiet"], [False, 1])


if __name__ == "__main__":
    unittest.main()
