# SPDX-License-Identifier: LGPL-2.1-or-later
# The manual and patent modes on FreeCAD's own features: the manual's moves
# as an Assembly Exploded View (Assembly_CreateView's objects), the
# Assembly found through links, and patent numerals as TechDraw balloons
# with no bubble. FreeCAD, Assembly and TechDraw stood in for.
import unittest

from _stubs import run

FAKES = r'''
import types
class O:
    def __init__(self, name, type_="Part::Feature", group=None, linked=None):
        self.Name = self.Label = name
        self.TypeId = type_
        self.Group = list(group or [])
        if linked is not None:
            self.LinkedObject = linked
class FakeDoc:
    def __init__(self, objs): self.Objects, self.removed, self.n = objs, [], 0
    def recompute(self): pass
    def removeObject(self, n): self.removed.append(n)
    def addObject(self, t, n):
        self.n += 1
        o = O(f"{n}{self.n:03d}", t)
        self.Objects.append(o)
        return o
'''


class Explode(unittest.TestCase):
    def test_assembly_found_through_links_and_the_plan(self):
        out = run(FAKES + r'''
from workshop_documents import fcexplode as X
box, lid, screw = O("Box"), O("Lid"), O("Screw")
link = O("Link", "App::Link", linked=lid)
asm = O("Assembly", "Assembly::AssemblyObject", [box, link, O("Joints", "Assembly::JointGroup")])
d = FakeDoc([box, lid, screw, link, asm])
OUT["found"] = getattr(X.assembly_of(d, [box, lid]), "Name", None)
OUT["not"] = X.assembly_of(d, [box, screw])
OUT["child"] = X.child_for(asm, lid).Name
OUT["plan_up"] = X.plan([["Box"], ["Lid", "Screw"]], {"Box": (0, 0, 0), "Lid": (0, 0, 30), "Screw": (0, 0, 30)})
OUT["plan_out"] = X.plan([["A", "B"]], {"A": (10, 0, 0), "B": (-10, 0, 0)})
''')
        self.assertEqual(out["found"], "Assembly")
        self.assertIsNone(out["not"])
        self.assertEqual(out["child"], "Link")
        self.assertEqual(out["plan_up"], [[1, ["Box"], [0.0, 0.0, 0.0]], [2, ["Lid", "Screw"], [0.0, 0.0, 30.0]]])
        self.assertEqual(len(out["plan_out"]), 2)

    def test_freecads_exploded_view_objects(self):
        out = run(FAKES + r'''
from workshop_documents import fcexplode as X
made = []
class Grp(O):
    def newObject(self, t, n):
        o = O(n, t); made.append(("group", t, n)); return o
class Asm(O):
    def newObject(self, t, n):
        o = O(f"{n}{len(made)}", t); made.append(("asm", t, n)); return o
ccv = types.ModuleType("CommandCreateView")
ccv.ExplodedView = lambda o: setattr(o, "Proxy", "view")
ccv.ExplodedViewStep = lambda o, i: setattr(o, "MoveType", ["Normal", "Radial"][i])
ua = types.ModuleType("UtilsAssembly")
ua.getViewGroup = lambda a: Grp("Views")
sys.modules.update({"CommandCreateView": ccv, "UtilsAssembly": ua})
sys.modules["FreeCAD"].Placement = lambda v, r: ("placement", v)
sys.modules["FreeCAD"].Rotation = lambda: "rot"
box, lid = O("Box"), O("Lid")
asm = Asm("Assembly", "Assembly::AssemblyObject", [box, O("Link", "App::Link", linked=lid)])
view, why = X.make_view(FakeDoc([]), asm, [(2, ["Lid"], (0, 0, 30))], {"Box": box, "Lid": lid}, "Box exploded")
OUT["made"] = made
OUT["why"] = why
OUT["refs"] = [view.Group[0].References[0].Name, view.Group[0].References[1]]
OUT["move"] = [view.Group[0].MoveType, view.Group[0].MovementTransform[1]]
ua.getViewGroup = lambda a: (_ for _ in ()).throw(RuntimeError("no Assembly here"))
OUT["fail"] = X.make_view(FakeDoc([]), asm, [], {}, "x")[1]
''')
        self.assertEqual(out["made"], [["group", "App::FeaturePython", "Box exploded"], ["asm", "App::FeaturePython", "Move"]])
        self.assertIsNone(out["why"])
        self.assertEqual(out["refs"], ["Assembly", ["Link."]])
        self.assertEqual(out["move"], ["Normal", [0, 0, 30]])
        self.assertIn("no Assembly here", out["fail"]["error"])


class Pages(unittest.TestCase):
    def test_numerals_as_plain_balloons(self):
        out = run(FAKES + r'''
from workshop_documents.handlers import drawing as D
D.views.point = lambda p, v: (p[0], p[1])
OUT["at"] = D.balloon_at((12.0, 8.0, 0), (2.0, 3.0, 0), "front", 2.0, (10, 4))
d = FakeDoc([])
class Page:
    def __init__(self): self.views = []
    def addView(self, v): self.views.append(v)
pg, v = Page(), O("View")
b = D._balloon(d, pg, v, (10.0, 5.0), (15.0, 7.0), 20, plain=True)
OUT["b"] = [b.Text, b.OriginX, b.OriginY, b.X, b.Y, b.BubbleShape, b.EndType, b.SourceView.Name, b.TypeId]
''')
        self.assertEqual(out["at"], [[10.0, 5.0], [15.0, 7.0]])
        self.assertEqual(out["b"], ["20", 10.0, 5.0, 15.0, 7.0, "None", "None", "View", "TechDraw::DrawViewBalloon"])


if __name__ == "__main__":
    unittest.main()
