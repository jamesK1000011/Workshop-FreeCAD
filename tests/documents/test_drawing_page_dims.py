# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make's dimensions and hole callouts on the TechDraw page: every
# item on its own. A live run lost every callout to one TypeError ("list
# indices must be integers or slices, not str": the views' frames, kept by
# view name, were overwritten with the hole's list of frames after the first
# hole), and the error replaced the overall sizes already listed as not on
# the page. FreeCAD, Part and TechDraw stood in for.
import unittest

from _stubs import run

PAGE = r'''
import sys, types
from workshop_documents.handlers import drawing as D
Part = sys.modules["Part"]
class Circle:
    def __init__(self, x, y, r):
        self.Center, self.Radius = types.SimpleNamespace(x=x, y=y), r
Part.Circle, Part.ArcOfCircle = Circle, type("Arc", (), {})
class View:
    def __init__(self, name, circles):
        self.Label, self.Scale, self.circles = name, 1.0, circles
    def getEdgeByIndex(self, i):
        if i >= len(self.circles): raise IndexError(i)
        return types.SimpleNamespace(Curve=Circle(*self.circles[i]))
    def getVertexByIndex(self, i):
        raise IndexError(i)
class Dim:
    n = 0
    def __init__(self):
        Dim.n += 1
        self.Name, self.FormatSpec = f"Dimension{Dim.n:03d}", "%.2f"
        self.ViewObject = types.SimpleNamespace()
    def getRawValue(self):
        (v, e), = self.References2D
        return 2 * v.circles[int(e[4:])][2] if self.Type == "Diameter" else v.circles[int(e[4:])][2]
added = []
doc = types.SimpleNamespace(addObject=lambda t, n: Dim(), recompute=lambda: None)
page = types.SimpleNamespace(addView=added.append)
front = View("Front", [(0, 0, 10.5), (30, 0, 4.0), (-30, 0, 4.0)])
top = View("Top", [(0, 0, 3.0), (20, 0, 3.0), (0, 20, 14.0)])
made = [("front", front), ("top", top)]
drawn = {"front": {"box": (-51, -23.5, 51, 23.5)}, "top": {"box": (-51, -24.5, 51, 24.5)}}
# The fitted frame: the view's geometry as views.project's, scale 1.
D._view_frame = lambda v, box: (1.0, 1, 1, 0.0, 0.0)
def sp(view, dia, centre, prefix="", label=None):
    return {"view": view, "type": "Diameter", "centre": centre, "radius": dia / 2, "value": dia, "prefix": prefix, **({"label": label} if label else {})}
specs = [sp("front", 21, (0, 0)), sp("front", 8, (30, 0), "2× ", "2× ⌀8 ⌴⌀13 ↧9"), sp("top", 6, (0, 0), "4× "), sp("top", 28, (0, 20))]
'''


class PageDims(unittest.TestCase):
    def test_every_hole_callout_reaches_the_page(self):
        out = run(PAGE + r'''
done, missed = D._page_dims(doc, page, made, drawn, specs)
OUT["done"] = [(d["view"], d["item"], d["measured"]) for d in done]
OUT["missed"] = missed
OUT["on_page"] = len(added)
''')
        # Before: the second spec raised the str index and none came back.
        self.assertEqual(out["missed"], [])
        self.assertEqual(out["done"], [["front", "⌀21", 21.0], ["front", "2× ⌀8 ⌴⌀13 ↧9", 8.0], ["top", "4× ⌀6", 6.0], ["top", "⌀28", 28.0]])
        self.assertEqual(out["on_page"], 4)

    def test_one_failing_item_never_drops_the_rest(self):
        out = run(PAGE + r'''
class Broken(View):
    @property
    def Scale(self):
        return [][str("Scale")]  # the live TypeError, in one view only
    @Scale.setter
    def Scale(self, v): pass
made[1] = ("top", Broken("Top", top.circles))
done, missed = D._page_dims(doc, page, made, drawn, specs)
OUT["done"] = [d["item"] for d in done]
OUT["missed"] = [(m["view"], m["item"], m["why"]) for m in missed]
''')
        self.assertEqual(out["done"], ["⌀21", "2× ⌀8 ⌴⌀13 ↧9"])
        self.assertEqual([m[:2] for m in out["missed"]], [["top", "4× ⌀6"], ["top", "⌀28"]])
        self.assertIn("list indices must be integers or slices, not str", out["missed"][0][2])

    def test_the_page_keeps_the_sizes_already_listed(self):
        out = run(PAGE + r'''
# The whole page: an overall size TechDraw measured differently is already
# under notOnPage; a failure of the callouts adds to it, never replaces it.
D._wait_views = lambda vs: None
D._template = lambda paper: (None, False)
D.sheets.PAPER = {"A3": (420, 297)}
D.sheets.extent_dims = lambda boxes, axes, ext: [("front", "z", (0, 0), (0, 47), 10, 47.0)]
D._extent_dim = lambda doc, page, v, horizontal, mm: {"why": f"TechDraw measured 45 between the view's extreme vertices, not {mm:g}: left off"}
D.views.VIEWS = {"front": ((0, -1, 0), (1, 0, 0)), "top": ((0, 0, 1), (1, 0, 0))}
D._page_dims = lambda *a, **k: [][ "front"]
class FakeDoc:
    def addObject(self, t, n):
        return types.SimpleNamespace(addView=lambda v: None, Views=[], EditableTexts={})
    def recompute(self): pass
p, res = D._techdraw_page(FakeDoc(), [], [("front", (100, 100)), ("top", (100, 200))], 1.0, "A3", "Stem drawing", True, specs, drawn,
                          boxes={"front": (0, 0, 102, 47), "top": (0, 0, 102, 49)})
OUT["res"] = res
''')
        res = out["res"]
        self.assertIsInstance(res, dict)
        why = [m["why"] for m in res["notOnPage"]]
        self.assertIn("not 47", why[0])  # the overall size's own reason kept
        self.assertEqual(len(why), 1 + 4)  # and every callout named after it
        self.assertEqual(res["notOnPage"][2]["item"], "2× ⌀8 ⌴⌀13 ↧9")
        self.assertEqual(res["dimensions"], [])


if __name__ == "__main__":
    unittest.main()
