# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make's TechDraw page fine in the window (views, sizes, hole
# callouts measured right) but TechDraw's own SVG and PDF exports held no
# view lines, twice (a live run, FreeCAD 1.1.3: 72 drawn elements, 48 the
# template's, 8 dimensions, 280 view edges), so the sheet writer made the
# files. TechDrawGui exports the scene of the page's tab, whose views'
# graphics items are made only once the tab is shown and painted: now the
# page is shown, its tab made the active one, painted, every view asked to
# repaint and the event loop run, then exported and checked. Also: two of
# the sheet writer's hole callouts landed on the wrong round edge (4x 6 on
# a slot's end, 20 on a 13 bore): a leader now lands only on a drawn
# circle of the hole's size where it projects, else the callout is left
# off and listed. FreeCAD, FreeCADGui and TechDraw stood in for.
import unittest

from _stubs import run

SCENE = r'''
import os, sys, types, tempfile
from workshop_documents.handlers import drawing as D
d = tempfile.mkdtemp()
log = []
D.TechDraw.writeDXFPage = lambda page, p: open(p, "w").write("0\nSECTION\n")
D._wait_views = lambda vs: {"seconds": 0.0, "notReady": []}

class View:
    Label = "Front"
    def getVisibleEdges(self):
        return ["e"] * 20
    def requestPaint(self):
        log.append("redraw")
        scene["asked"] = True

scene = {"shown": False, "active": False, "painted": False, "asked": False, "items": False}
views = [View()]
tpl = os.path.join(d, "tpl.svg")
open(tpl, "w").write("<svg><rect/></svg>")
page = types.SimpleNamespace(Name="Page", Label="Stem drawing", Views=views, Document=types.SimpleNamespace(Name="Doc"),
                             Template=types.SimpleNamespace(Template=tpl, EditableTexts={"t": "StemV2"}))
def show():
    log.append("show")
    scene["shown"] = True
page.ViewObject = types.SimpleNamespace(show=show)

class Tab:
    def getPage(self):
        return page
class Other:
    def getPage(self):
        return types.SimpleNamespace(Name="Page001")
mw = types.SimpleNamespace(setActiveWindow=lambda t: (log.append("activate"), scene.__setitem__("active", isinstance(t, Tab))))
gdoc = types.SimpleNamespace(mdiViewsOfType=lambda t: [Other(), Tab()] if scene["shown"] else [])
fg = types.ModuleType("FreeCADGui")
fg.getDocument = lambda name: gdoc
fg.getMainWindow = lambda: mw
sys.modules["FreeCADGui"] = fg

def pump():
    log.append("process")
    # The window paints the active tab: its views' items made on its first
    # paint, their lines drawn once asked to repaint and painted again.
    if scene["shown"] and scene["active"]:
        if scene["painted"] and scene["asked"]:
            scene["items"] = True
        scene["painted"] = True
    return True
D._pump_gui = pump

gui = types.ModuleType("TechDrawGui")
def svg(pg, p):
    log.append("export")
    lines = "<path d='M0 0'/>" * 40 if scene["items"] else ""
    open(p, "w").write("<svg><text>StemV2</text><rect/>" + lines + "</svg>")
gui.exportPageAsSvg = svg
gui.exportPageAsPdf = lambda pg, p: (log.append("exportPdf"), open(p, "w").write("%PDF"))
sys.modules["TechDrawGui"] = gui
D.FreeCAD.GuiUp = True
'''


class ExportDrawsTheScene(unittest.TestCase):
    def test_shown_activated_painted_redrawn_processed_then_exported(self):
        out = run(SCENE + r'''
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["r"] = [sorted(paths), why, rep["viewsInExport"]["ok"], rep["exportScene"], log]
''')
        paths, why, ok, steps, log = out["r"]
        self.assertEqual(paths, ["dxf", "pdf", "svg"])
        self.assertEqual(why, {})
        self.assertTrue(ok)
        self.assertEqual(steps, ["show", "activate", "paint", "redraw", "process"])
        # In order: show, activate the page's own tab (not the other page's),
        # paint, ask each view to repaint, run the loop, then export once.
        first = log.index("export")
        self.assertEqual(log[:4], ["show", "activate", "process", "redraw"])
        self.assertTrue(all(x == "process" for x in log[4:first]))
        self.assertGreaterEqual(first - 4, 1)
        self.assertEqual(log.count("export"), 1)
        self.assertEqual(log[-1], "exportPdf")

    def test_before_the_tab_was_shown_the_export_had_no_views(self):
        out = run(SCENE + r'''
# As before: exported straight after show(), no tab made active, no paint.
show()
p = os.path.join(d, "old.svg")
svg(page, p)
OUT["old"] = D.views_in_svg(p, page, views, {})
''')
        self.assertFalse(out["old"])

    def test_scene_never_drawn_falls_back_to_the_sheet_writer(self):
        out = run(SCENE + r'''
D._page_tab = lambda pg: None   # no tab found: the scene stays empty
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["r"] = [sorted(paths), sorted(why), why.get("svg", ""), rep["exportScene"], log.count("export")]
''')
        paths, why, svg_why, steps, n = out["r"]
        self.assertEqual(paths, ["dxf"])
        self.assertEqual(why, ["pdf", "svg"])
        self.assertEqual("noViewGeometry", svg_why)
        self.assertNotIn("activate", steps)
        self.assertEqual(n, 2)


class CalloutOnTheHole(unittest.TestCase):
    def test_lands_only_on_a_circle_of_its_size_where_it_projects(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
# Front view: a groove slot's round end (r 4) right by the first 6 mm
# hole, which is hidden there; the other three are drawn.
front = [(10.4, 0.0, 4.0), (30, 0, 3.0), (50, 0, 3.0), (70, 0, 3.0)]
holes = [(10, 0), (30, 0), (50, 0), (70, 0)]
OUT["front"] = D.hole_circle(front, holes, 3.0)
# Right view: a 13 bore drawn where the 20 counterbore projects (the 20 hidden).
right = [(0, 0, 6.5), (25, 0, 6.5)]
OUT["right"] = D.hole_circle(right, [(0, 0)], 10.0)
# The old way: nearest round edge to the first hole.
near = lambda cs, p: min(cs, key=lambda c: (c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2)
OUT["old"] = [near(front, holes[0]), near(right, (0, 0))]
# Size within 2%, place within 0.1 mm + 5% of r; a thread's tap drill accepted.
OUT["edge"] = [D.hole_circle([(0, 0, 3.05)], [(0, 0)], 3.0), D.hole_circle([(0, 0, 3.1)], [(0, 0)], 3.0),
               D.hole_circle([(0.2, 0, 3.0)], [(0, 0)], 3.0), D.hole_circle([(0.3, 0, 3.0)], [(0, 0)], 3.0)]
OUT["thread"] = [D.hole_circle([(0, 0, 1.25)], [(0, 0)], 1.5), D.hole_circle([(0, 0, 1.25)], [(0, 0)], 1.5, thread=True)]
OUT["none"] = D.hole_circle(None, [(0, 0)], 3.0)
''')
        self.assertEqual(out["old"], [[10.4, 0.0, 4.0], [0, 0, 6.5]])
        self.assertEqual(out["front"], [1, [30, 0, 3.0]])
        self.assertIsNone(out["right"])
        self.assertEqual(out["edge"][0], [0, [0, 0, 3.05]])
        self.assertIsNone(out["edge"][1])
        self.assertEqual(out["edge"][2], [0, [0.2, 0, 3.0]])
        self.assertIsNone(out["edge"][3])
        self.assertEqual(out["thread"], [None, [0, [0, 0, 1.25]]])
        self.assertIsNone(out["none"])

    def test_a_diameter_is_only_called_out_on_a_whole_circle(self):
        out = run(r'''
import math
from workshop_documents.handlers import drawing as D
# A slot 6 wide: two R3 half arcs at its ends; a 6 mm hole drawn whole; a
# 6 mm hole TechDraw drew as two halves; an R3 fillet's quarter.
circles = [(0, 0, 3.0), (20, 0, 3.0), (40, 10, 3.0), (60, 10, 3.0), (60, 10, 3.0), (80, 0, 3.0)]
turns = [math.pi, math.pi, 2 * math.pi, math.pi, math.pi, math.pi / 2]
OUT["keep"] = D.full_circles(circles, turns)
OUT["none"] = D.full_circles([], [])
''')
        self.assertEqual(out["keep"], [2, 3, 4])
        self.assertEqual(out["none"], [])

    def test_the_view_keeps_its_drawn_circles(self):
        out = run(r'''
import types
from workshop_documents import views
class Circle:
    def __init__(self, x, y, r):
        self.Center, self.Radius = types.SimpleNamespace(x=x, y=y), r
class Line:
    pass
def edge(cu):
    return types.SimpleNamespace(Curve=cu, discretize=lambda **k: [types.SimpleNamespace(x=0, y=0), types.SimpleNamespace(x=1, y=1)])
comp = types.SimpleNamespace(isNull=lambda: False, Edges=[edge(Circle(1, 2, 3)), edge(Circle(1, 2, 3)), edge(Line())])
lines, circles = [], []
views._polys(comp, "visible", lines, 0.02, circles)
OUT["r"] = [len(lines), circles]
''')
        self.assertEqual(out["r"], [3, [[1, 2, 3]]])


if __name__ == "__main__":
    unittest.main()
