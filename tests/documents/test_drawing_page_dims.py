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
        # A whole circle: its parameters run a full turn (a diameter is
        # called out only on a circle drawn all the way round).
        return types.SimpleNamespace(Curve=Circle(*self.circles[i]), FirstParameter=0.0, LastParameter=6.283185307179586)
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


class LiveStem(unittest.TestCase):
    """The stem on f7a5078 (102 x 49 x 47, 1:1): the front's height read
    55.5 and the top's 54.68 (an arc's centre, which TechDraw keeps among
    the view's vertices, picked as the extreme), and five of six hole
    callouts found "no circle there" (the frame fitted on a B-spline's
    poles; projectPoint taken about the origin, not the part's centre)."""

    EXT = r"""
import types
from workshop_documents.handlers import drawing as D
P = lambda x, y: types.SimpleNamespace(x=x, y=y)
corners = [(-51, -23.5), (51, -23.5), (51, 23.5), (-51, 23.5)]
class View:
    Scale = 1.0
    def __init__(self, verts, edges):
        self.verts, self.edges = verts, edges
    def getVertexByIndex(self, i):
        if i >= len(self.verts): raise IndexError(i)
        return types.SimpleNamespace(Point=P(*self.verts[i]))
    def getEdgeByIndex(self, i):
        if i >= len(self.edges): raise IndexError(i)
        a, b = self.edges[i]
        return types.SimpleNamespace(Vertexes=[types.SimpleNamespace(Point=P(*a)), types.SimpleNamespace(Point=P(*b))])
class Dim:
    Name = "Dimension"
    def getRawValue(self):
        (v, a), (_, b) = self.References2D
        i, j = int(a[6:]), int(b[6:])
        k = 0 if self.Type == "DistanceX" else 1
        return abs(v.verts[j][k] - v.verts[i][k])
removed = []
doc = types.SimpleNamespace(addObject=lambda t, n: Dim(), recompute=lambda: None, removeObject=removed.append)
page = types.SimpleNamespace(addView=lambda d: None, removeView=lambda d: None)
"""

    def test_an_arc_centre_is_never_the_extreme(self):
        out = run(self.EXT + r"""
# A flat arc on the top edge: its centre 32 up, among the vertices (and
# listed before the corners, as TechDraw's own order may have it).
verts = [(0, 32)] + corners
edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
got = D._extent_dim(doc, page, View(verts, edges), False, 47)
OUT["got"] = [got.get("measured"), [r[1] for r in got["dim"].References2D] if "dim" in got else got]
OUT["x"] = D._extent_dim(doc, page, View(verts, edges), True, 102).get("measured")
OUT["removed"] = len(removed)
""")
        self.assertEqual(out["got"][0], 47)  # before: 55.5, left off
        self.assertNotIn("Vertex0", out["got"][1])
        self.assertEqual(out["x"], 102)
        self.assertEqual(out["removed"], 0)  # the right pair first time

    def test_edges_unread_the_next_pair_that_measures_it(self):
        out = run(self.EXT + r"""
verts = [(0, 31.18)] + corners  # no edges read: every vertex a candidate
got = D._extent_dim(doc, page, View(verts, []), False, 47)
OUT["got"] = got.get("measured")
OUT["removed"] = len(removed)
bad = D._extent_dim(doc, page, View(verts, []), False, 60)
OUT["bad"] = bad["why"]
""")
        self.assertEqual(out["got"], 47)
        self.assertEqual(out["removed"], 1)  # the extremes tried, measured 54.68, taken off
        self.assertIn("not 60", out["bad"])

    CIRC = PAGE + r"""
# The front view as TechDraw holds it: centred on the part's bounding box
# centre (51, 24.5, 23.5), y turned over; projectPoint about the origin.
c3 = (51.0, 24.5, 23.5)
holes3 = {"⌀21": (51.0, 0.0, 23.5, 10.5), "2× ⌀8": (20.0, 0.0, 10.0, 4.0), "4× ⌀6": (85.0, 0.0, 35.0, 3.0)}
td = [(x - c3[0], -(z - c3[2]), r) for x, _y, z, r in holes3.values()]
front = View("Front", td)
front.projectPoint = lambda p: types.SimpleNamespace(x=p[0], y=p[2])
D._source_centre = lambda v: c3
# The frame fitted on a B-spline's poles: scale 1.17, centre off.
D._view_frame = lambda v, box: (1.17, 1, 1, 0.0, 4.25)
made = [("front", front)]
def hsp(item, p):
    x, y, z, r = p
    return {"view": "front", "type": "Diameter", "centre": (x - 51, z - 23.5), "centre3": [x, y, z], "radius": r, "value": 2 * r, "label": item}
"""

    def test_holes_found_about_the_parts_centre(self):
        out = run(self.CIRC + r"""
specs = [hsp(k, p) for k, p in holes3.items()]
done, missed = D._page_dims(doc, page, made, drawn, specs)
OUT["done"] = [(d["item"], d["measured"], d.get("warning")) for d in done]
OUT["refs"] = [r[1] for d in added for r in d.References2D]
OUT["missed"] = missed
""")
        self.assertEqual(out["missed"], [])  # before: "no vertex or circle of the view there"
        self.assertEqual(out["done"], [["⌀21", 21.0, None], ["2× ⌀8", 8.0, None], ["4× ⌀6", 6.0, None]])
        self.assertEqual(out["refs"], ["Edge0", "Edge1", "Edge2"])

    def test_a_circle_of_its_size_when_no_frame_places_it(self):
        out = run(self.CIRC + r"""
front.projectPoint = None
del front.projectPoint
sp_ = hsp("2× ⌀8", holes3["2× ⌀8"]); sp_.pop("centre3")
sp2 = {**hsp("⌀9", holes3["2× ⌀8"]), "radius": 4.5, "value": 9.0}; sp2.pop("centre3")
done, missed = D._page_dims(doc, page, made, drawn, [sp_, sp2])
OUT["done"] = [(d["item"], d["measured"], d.get("warning", "")) for d in done]
OUT["missed"] = [m["item"] for m in missed]
""")
        self.assertEqual([d[:2] for d in out["done"]], [["2× ⌀8", 8.0]])
        self.assertIn("check it is the hole meant", out["done"][0][2])
        self.assertEqual(out["missed"], ["⌀9"])  # no circle of that size: still left off, said


class PatentNumerals(unittest.TestCase):
    """Found live (run 2, Documents model call 12): bodies ["Body"] drew the
    body whose label is "Tut" (bodies takes an object's name), and numerals
    { Body: 0 } was refused "Body is not among the bodies drawn — Tut" where
    the number itself was what was wrong."""

    CODE = r"""
import types
from workshop_documents.handlers import drawing as D
objs = [types.SimpleNamespace(Label="Tut", Name="Body"), types.SimpleNamespace(Label="Base plate", Name="Box")]
def tried(given):
    try:
        return D._numerals(objs, given)
    except Exception as e:
        return [getattr(e, "code", type(e).__name__), getattr(e, "message", str(e))]
OUT["byName"] = tried({"Body": 30})
OUT["byLabel"] = tried({"Tut": 30, "base plate": 12})
OUT["none"] = tried({})
OUT["zero"] = tried({"Body": 0})
OUT["bool"] = tried({"Tut": True})
OUT["unknown"] = tried({"Lid": 5})
OUT["twice"] = tried({"Body": 5, "Tut": 6})
OUT["same"] = tried({"Body": 5, "Box": 5})
"""

    def test_a_body_is_named_by_label_or_by_object_name(self):
        out = run(self.CODE)
        self.assertEqual(out["byName"], {"Tut": 30, "Base plate": 10})
        self.assertEqual(out["byLabel"], {"Tut": 30, "Base plate": 12})
        self.assertEqual(out["none"], {"Tut": 10, "Base plate": 20})
        self.assertEqual(out["zero"][0], "invalid_input")
        self.assertIn("numerals.Body: a whole number over 0", out["zero"][1])
        self.assertEqual(out["bool"][0], "invalid_input")
        self.assertEqual(out["unknown"][0], "not_found")
        self.assertIn("Lid is not among the bodies drawn — Tut, Base plate", out["unknown"][1])
        self.assertEqual(out["twice"][0], "invalid_input")
        self.assertIn("the same body (Tut)", out["twice"][1])
        self.assertEqual(out["same"][0], "invalid_input")


if __name__ == "__main__":
    unittest.main()
