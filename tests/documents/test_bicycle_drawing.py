# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make on the bicycle (FreeCAD 1.1.3, 20 Nov 2026): 291 s, of which
# 249 s were "sheet", and the front view had no edges after 30 s, so its
# overall dimensions were not placed.
#
# - sheet: Workshop's own hidden-line removal of every view ran for files
#   that TechDraw then wrote itself. With a page and no hole callouts the
#   layout now takes each view's box from the tessellation, and the lines
#   are worked out after the export, only for a file the page did not
#   write. The polylines' deflection grows with the size of the parts.
# - wait: each view has its own limit, longer for many edges; the overall
#   sizes go on each view as soon as it is drawn, and on a view drawn after
#   its limit when it is drawn before the export. A large assembly gets
#   TechDraw's coarse lines unless holes are asked.
# FreeCAD and TechDraw stood in for.
import unittest

from _stubs import run

VEC = r'''
import math
import FreeCAD
class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)
    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z
    def cross(self, o):
        return Vec(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)
    def normalize(self):
        n = math.sqrt(self.dot(self)) or 1.0
        self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
        return self
FreeCAD.Vector = Vec
class Box:
    def __init__(self, x0, y0, z0, x1, y1, z1):
        self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = x0, y0, z0, x1, y1, z1
        self.DiagonalLength = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2)
    def add(self, b):
        self.__init__(min(self.XMin, b.XMin), min(self.YMin, b.YMin), min(self.ZMin, b.ZMin), max(self.XMax, b.XMax), max(self.YMax, b.YMax), max(self.ZMax, b.ZMax))
class Solid:
    """A wheel-like part: its tessellation's points lie inside its loose
    bounding box (OCC's box is larger than the part on curved faces)."""
    def __init__(self, pts, edges=12, loose=5.0):
        self.pts = [Vec(*p) for p in pts]
        xs, ys, zs = [p.x for p in self.pts], [p.y for p in self.pts], [p.z for p in self.pts]
        self.box = (min(xs) - loose, min(ys) - loose, min(zs) - loose, max(xs) + loose, max(ys) + loose, max(zs) + loose)
        self.Edges = [None] * edges
        self.Vertexes = []
        self.asked = []
    @property
    def BoundBox(self):
        return Box(*self.box)
    def tessellate(self, tol):
        self.asked.append(tol)
        return self.pts, []
'''


class Extents(unittest.TestCase):
    def test_boxes_from_the_tessellation(self):
        out = run(VEC + r'''
from workshop_documents import views
wheel = Solid([(0, 0, 0), (700, 0, 0), (350, 30, 350), (350, -30, -350)], edges=2400)
frame = Solid([(200, -40, 100), (1100, 40, 600)], edges=900)
got = views.extents([wheel, frame], ["front", "top", "right"])
OUT["front"] = [round(x, 3) for x in got["front"]]
OUT["top"] = [round(x, 3) for x in got["top"]]
OUT["right"] = [round(x, 3) for x in got["right"]]
OUT["tol"] = wheel.asked
OUT["edges"] = views.edge_count([wheel, frame])
OUT["defl"] = [round(views.deflection_for([wheel, frame]), 4), views.deflection_for([Solid([(0, 0, 0), (50, 20, 10)])])]
''')
        self.assertEqual(out["front"], [0, -350, 1100, 600])     # x right, z up; not the loose box
        self.assertEqual(out["top"], [0, -40, 1100, 40])
        self.assertEqual(out["right"], [-40, -350, 40, 600])
        self.assertEqual(len(out["tol"]), 1)                      # one tessellation a part for all views
        self.assertGreater(out["tol"][0], 0.5)                    # coarse enough for a 1.4 m assembly
        self.assertEqual(out["edges"], 3300)
        self.assertGreater(out["defl"][0], 0.1)                   # a large assembly: coarser polylines
        self.assertEqual(out["defl"][1], 0.02)                    # a small part: as before


class Limits(unittest.TestCase):
    def test_a_view_of_many_edges_waits_longer(self):
        out = run(r'''
from workshop_documents import td_wait
OUT["l"] = [td_wait.view_limit(x) for x in (0, 200, 3300, 20000, 10 ** 6, None)]
OUT["c"] = [td_wait.view_limit(x, coarse=True) for x in (0, 3300, 10 ** 6)]
''')
        self.assertEqual(out["l"], [30.0, 33.0, 79.5, 240.0, 240.0, 30.0])
        self.assertEqual(out["c"], [30.0, 46.5, 120.0])

    def test_each_view_its_own_limit_and_dimensions_as_each_is_drawn(self):
        out = run(r'''
from workshop_documents import td_wait
class View:
    def __init__(self, label, late):
        self.Label, self.late, self.State = label, late, []
    def isWaitingForHlr(self):
        return self.late > 0
    def getVisibleEdges(self):
        return [] if self.late > 0 else ["e"]
clock = [0.0]
td_wait.time = type("T", (), {"time": staticmethod(lambda: clock[0]), "sleep": staticmethod(lambda s: None), "perf_counter": staticmethod(lambda: clock[0])})
views = [View("Front", 40), View("Top", 2), View("Right", 400)]
order = []
def pump():
    clock[0] += 1.0                      # a turn: one second
    for v in views:
        v.late = max(0, v.late - 1)
    order.append([v.Label for v in views if v.late == 0 and v.Label not in [x[0] for x in told]])
    return True
told = []
got = td_wait.views_ready(views, pump=pump, sleep=0, draw=False, limits=[60, 60, 60], on_ready=lambda v: told.append([v.Label, clock[0]]))
OUT["told"] = told
OUT["not"] = got["notReady"]
OUT["seconds"] = got["seconds"]
''')
        # Top is told at once when drawn, Front at 40 s (past the old 30 s), Right never within 60 s.
        self.assertEqual(out["told"], [["Top", 2.0], ["Front", 40.0]])
        self.assertEqual(out["not"], [{"view": "Right", "why": "waiting", "limit": 60.0}])
        self.assertEqual(out["seconds"], 60.0)

    def test_a_wait_that_cannot_tell_still_places_after(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
class V:
    def __init__(self, label): self.Label = label
vs = [V("Front"), V("Top")]
D._wait_views = lambda vs, **kw: (_ for _ in ()).throw(TypeError("no words")) if kw else {"seconds": 0.1, "notReady": [{"view": "Top", "why": "waiting"}]}
told = []
got = D._settle(vs, draw=False, limits=[60, 60], on_ready=lambda v: told.append(v.Label))
OUT["told"] = told
OUT["got"] = got
''')
        self.assertEqual(out["told"], ["Front"])
        self.assertEqual(out["got"]["notReady"], [{"view": "Top", "why": "waiting"}])

    def test_coarse_choice(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
OUT["c"] = [D.coarse_choice(None, 200, False), D.coarse_choice(None, 9000, False), D.coarse_choice(None, 9000, True),
            D.coarse_choice(False, 9000, False), D.coarse_choice(True, 10, True)]
''')
        c = out["c"]
        self.assertEqual([x[0] for x in c], [False, True, False, False, True])
        self.assertIn("large assembly", c[1][1])
        self.assertIn("hole callouts", c[2][1])
        self.assertEqual(c[3][1], "asked")


LATE = r'''
import types
from workshop_documents.handlers import drawing as D
class View:
    def __init__(self, label, ready):
        self.Label, self.ready, self.State = label, ready, []
    def isWaitingForHlr(self):
        return not self.ready
    def getVisibleEdges(self):
        return ["e"] if self.ready else []
class Dim:
    def __init__(self, n): self.Name, self.X, self.Y = f"Dimension{n:03d}", 0, 0
dims = []
def extent_dim(doc, page, v, horizontal, mm):
    if not v.ready:
        return {"why": "the view has no vertices yet (TechDraw had not drawn it)"}
    d = Dim(len(dims)); dims.append(d)
    return {"dim": d, "dimension": d.Name, "measured": mm, "value": mm}
D._extent_dim = extent_dim
recomputes = []
doc = types.SimpleNamespace(recompute=lambda: recomputes.append(1))
front, top = View("Front", False), View("Top", True)
def todo(view, v, axis, horizontal, mm):
    return {"view": view, "v": v, "axis": axis, "horizontal": horizontal, "off": 10, "mm": mm, "box": (0, 0, 100, 50)}
'''


class LateViews(unittest.TestCase):
    def test_dimensions_go_on_a_view_drawn_late_before_the_export(self):
        out = run(LATE + r'''
ext = {"done": [], "missed": [], "todo": [todo("front", front, "x", True, 1100), todo("front", front, "z", False, 950), todo("top", top, "y", False, 80)], "doc": doc, "page": None}
D.place_extents(ext, top)                       # Top drawn in time: placed at once
missed = [{"view": "front", "type": t, "value": v, "why": "the view was not drawn within its time limit: placed when it is drawn before the export (page.lateExtents), else left off"}
          for t, v in (("DistanceX", 1100), ("DistanceY", 950))]
made = {"extentDimensions": 1, "extents": list(ext["done"]), "notOnPage": list(missed) + [{"view": "front", "item": "R5", "why": "other"}], "_late": ext}
OUT["early"] = D.place_late(dict(made, _late={"done": [], "missed": [], "todo": [], "doc": doc, "page": None}))
made2 = dict(made)
made2["_late"] = {"done": list(ext["done"]), "missed": [], "todo": list(ext["todo"]), "doc": doc, "page": None}
OUT["not_yet"] = [D.place_late(made2), "_late" in made2, len(made2["notOnPage"])]
front.ready = True                              # drawn after its limit, before the export
OUT["late"] = D.place_late(made)
OUT["made"] = {k: made[k] for k in made}
OUT["recomputes"] = len(recomputes)
''')
        self.assertEqual(out["early"], [])
        self.assertEqual(out["not_yet"], [[], False, 3])  # still not drawn: left off, said
        self.assertEqual(out["late"], ["front"])
        m = out["made"]
        self.assertNotIn("_late", m)
        self.assertEqual(m["extentDimensions"], 3)
        self.assertEqual(sorted((e["view"], e["axis"]) for e in m["extents"]), [("front", "x"), ("front", "z"), ("top", "y")])
        self.assertEqual(m["notOnPage"], [{"view": "front", "item": "R5", "why": "other"}])  # the time-limit rows gone, the rest kept
        self.assertEqual(m["lateExtents"], ["front"])
        self.assertEqual(out["recomputes"], 1)

    def test_the_export_places_them_after_its_wait_and_before_writing(self):
        out = run(LATE + r'''
import os, tempfile
calls = []
D._part_views = lambda page: [front]
D._wait_views = lambda vs, **kw: (calls.append(["wait", kw.get("limits")]), {"seconds": 0.0, "notReady": []})[1]
D.TechDraw.writeDXFPage = lambda page, p: (calls.append(["dxf"]), open(p, "w").write("0\nEOF\n"))
D.FreeCAD.GuiUp = False
rep = {}
paths, why = D._export_page(object(), tempfile.mkdtemp(), "Bicycle", report=rep, limit=79.5, before=lambda: calls.append(["late"]))
OUT["calls"] = calls
OUT["ms"] = sorted(rep["ms"])
OUT["paths"] = sorted(paths)
''')
        self.assertEqual(out["calls"], [["wait", [79.5]], ["late"], ["dxf"]])
        self.assertIn("late", out["ms"])
        self.assertEqual(out["paths"], ["dxf"])


class LinesLater(unittest.TestCase):
    def test_lines_go_where_the_layout_put_the_view(self):
        out = run(r'''
from workshop_documents import sheets, views
from workshop_documents.handlers import drawing as D
asked = []
views.project = lambda shapes, v, hidden=False: (asked.append(v), {"lines": [("visible", [(0, 0), (10, 0)])], "box": (0, 0, 10, 0), "circles": []})[1]
sh = sheets.Sheet(420, 297)
sh.frame()
at_front = len(sh.lines)
sh.line([(1, 1), (2, 2)], "thin")               # a dimension drawn after the front view's place
at_top = len(sh.lines)
sh.line([(3, 3), (4, 4)], "thin")
D.fill_later(sh, [(at_front, "front", (0, -5, 10, 5), (100, 100), 2.0), (at_top, "top", (0, -5, 10, 5), (300, 100), 1.0)], ["shape"])
OUT["asked"] = sorted(asked)
OUT["kinds"] = [l[0] for l in sh.lines]
OUT["front"] = [list(p) for p in sh.lines[at_front][1]]
''')
        self.assertEqual(out["asked"], ["front", "top"])
        k = out["kinds"]
        # frame lines, then front's, the first dimension, top's, the second dimension
        i = k.index("visible")
        self.assertEqual(k[i:], ["visible", "thin", "visible", "thin"])
        # on the box the layout used: its centre (5, 0) at the centre given, at the scale given
        self.assertEqual(out["front"], [[90.0, 100.0], [110.0, 100.0]])


if __name__ == "__main__":
    unittest.main()
