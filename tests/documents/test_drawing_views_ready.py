# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make's page exported with no views: a live run (FreeCAD 1.1.3, the
# stem, A3 1:1) put every dimension and callout on the TechDraw page, but its
# PDF held only the frame, title block and dimensions floating on white. A
# view keeps its old lines readable while TechDraw works new ones out on
# another thread, so "has edges" let the export run before they were drawn.
# Now every view is waited for (touched ones recomputed once, the busy calls
# asked, the event loop run), the export refused while any is not ready, and
# the SVG checked for the views' lines. Also: two hole callouts' texts and
# leaders overlapped at the top of the sheet; each now clears every earlier
# one. FreeCAD and TechDraw stood in for.
import unittest

from _stubs import run

LATE_VIEW = r'''
import types
class View:
    """Lines arrive late: waiting for `late` turns of the event loop, its
    old lines readable all the while; touched until recomputed."""
    def __init__(self, label, late, touched=False, edges=("e",)):
        self.Label, self.late, self.recomputes = label, late, 0
        self.State = ["Touched"] if touched else []
        self.edges = list(edges)
    def isWaitingForHlr(self):
        return self.late > 0
    def getVisibleEdges(self):
        return self.edges
    def recompute(self):
        self.recomputes += 1
        self.State = []
turns = []
def pump():
    turns.append(1)
    for v in views:
        if v.late > 0:
            v.late -= 1
    return True
'''


class ViewsReady(unittest.TestCase):
    def test_waits_for_a_view_whose_lines_arrive_late(self):
        out = run(LATE_VIEW + r'''
from workshop_documents import td_wait
views = [View("Front", 0), View("Top", 5), View("Right", 0, touched=True)]
got = td_wait.views_ready(views, timeout=5, pump=pump, sleep=0)
OUT["got"] = got
OUT["turns"] = len(turns)
OUT["recomputes"] = [v.recomputes for v in views]
OUT["late"] = [v.late for v in views]
''')
        # Before: ready at once (each had edges), nothing waited for.
        self.assertEqual(out["got"]["notReady"], [])
        self.assertEqual(out["late"], [0, 0, 0])
        self.assertGreaterEqual(out["turns"], 5)
        # Only the touched view recomputed, once; a ready view never (that starts its lines afresh).
        self.assertEqual(out["recomputes"], [0, 0, 1])

    def test_timeout_named_per_view(self):
        out = run(LATE_VIEW + r'''
from workshop_documents import td_wait
views = [View("Front", 10 ** 9), View("Top", 0, edges=())]
got = td_wait.views_ready(views, timeout=0.05, pump=pump, sleep=0)
OUT["not"] = got["notReady"]
''')
        self.assertEqual(out["not"], [{"view": "Front", "why": "waiting"}, {"view": "Top", "why": "no edges"}])


EXPORT = LATE_VIEW + r'''
import os, sys, tempfile
from workshop_documents.handlers import drawing as D
from workshop_documents import td_wait
d = tempfile.mkdtemp()
D.TechDraw.writeDXFPage = lambda page, p: open(p, "w").write("0\nSECTION\n")
gui = types.ModuleType("TechDrawGui")
exports = []
def svg(page, p):
    exports.append(p)
    lines = "".join("<path d='M0 0'/>" for _ in range(40)) if page.drawn() else ""
    open(p, "w").write("<svg><text>StemV2</text><rect/>" + lines + "</svg>")
gui.exportPageAsSvg = svg
gui.exportPageAsPdf = lambda page, p: open(p, "w").write("%PDF")
sys.modules["TechDrawGui"] = gui
D.FreeCAD.GuiUp = True
tpl = os.path.join(d, "tpl.svg")
open(tpl, "w").write("<svg><rect/></svg>")
views = [View("Front", 0, edges=["e"] * 20)]
page = types.SimpleNamespace(Views=views, Template=types.SimpleNamespace(Template=tpl, EditableTexts={"t": "StemV2"}))
page.ViewObject = types.SimpleNamespace(show=lambda: None)
D._wait_views = lambda vs: td_wait.views_ready(vs, timeout=0.05, pump=pump, sleep=0)
'''


class ExportHoldsTheViews(unittest.TestCase):
    def test_never_exported_while_a_view_is_not_drawn(self):
        out = run(EXPORT + r'''
views[0].late = 10 ** 9
page.drawn = lambda: False
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["r"] = [sorted(paths), sorted(why), why.get("pdf", ""), rep.get("viewsNotReady"), len(exports)]
''')
        paths, why, pdf, not_ready, n = out["r"]
        self.assertEqual(paths, [])
        self.assertEqual(why, ["dxf", "pdf", "svg"])
        self.assertIn("had not drawn every view", pdf)
        self.assertEqual(not_ready, [{"view": "Front", "why": "waiting"}])
        self.assertEqual(n, 0)

    def test_svg_without_the_views_lines_exported_again_then_refused(self):
        out = run(EXPORT + r'''
# The scene fills only after the first export (the window redrawn by the wait).
state = {"n": 0}
def drawn():
    state["n"] += 1
    return state["n"] > 1
page.drawn = drawn
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["late"] = [sorted(paths), why, rep["viewsInExport"]["ok"], len(exports)]
exports.clear()
page.drawn = lambda: False
rep = {}
paths, why = D._export_page(page, d, "Stem2", report=rep)
OUT["never"] = [sorted(paths), sorted(why), why.get("pdf", ""), rep["viewsInExport"], len(exports)]
''')
        self.assertEqual(out["late"], [["dxf", "pdf", "svg"], {}, True, 2])
        paths, why, pdf, counts, n = out["never"]
        self.assertEqual(paths, ["dxf"])
        self.assertEqual(why, ["pdf", "svg"])
        self.assertEqual("noViewGeometry", pdf)
        self.assertFalse(counts["ok"])
        self.assertEqual(counts["viewEdges"], 20)
        self.assertEqual(n, 2)

    def test_dimensions_alone_are_not_the_views(self):
        out = run(EXPORT + r'''
# Nine dimensions' lines and arrows, no view lines: still refused.
page.Views = views + [types.SimpleNamespace(TypeId="TechDraw::DrawViewDimension", Name=f"Dimension{i}") for i in range(9)]
def svg(page, p):
    exports.append(p)
    open(p, "w").write("<svg><text>StemV2</text><rect/>" + "<path d='M0 0'/>" * 45 + "</svg>")
gui.exportPageAsSvg = svg
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["r"] = [sorted(paths), rep["viewsInExport"]["ok"]]
''')
        self.assertEqual(out["r"], [["dxf"], False])


class CalloutsApart(unittest.TestCase):
    def test_texts_and_leaders_clear_each_other(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
from workshop_documents import sheets
# Two views side by side; a hole near the left view's right edge leads up
# right, one near the right view's left edge up left: as before, only the
# sheet's texts tested against the texts drawn, the leaders crossed and
# the page's larger texts overlapped.
left, right = (60, 80, 160, 130), (170, 80, 270, 130)
a = ((155, 90), 3, left, "4× ⌀6")
b = ((175, 90), 4, right, "2× ⌀8 ⌴⌀13 ↧9")
def old(pa, r, outline, label, texts):
    for extra in range(12):
        tip, elbow, tail, anchor = D.callout_leader(pa, r, outline, extra)
        t = (tail[0] + (1 if anchor == "start" else -1), tail[1] - 1, 3.0, label, anchor)
        if not any(D._boxes_hit(sheets.text_box(t), x) for x in [left, right] + texts):
            return (tip, elbow, tail), t
olda = old(*a[:3], a[3], [])
oldb = old(*b[:3], b[3], [sheets.text_box(olda[1])])
def cross(p, q):
    return any(D._segs_cross(p[i], p[i + 1], q[j], q[j + 1]) for i in range(2) for j in range(2))
OUT["old_cross"] = cross(olda[0], oldb[0])
placed = []
for pa, r, box, label in (a, b):
    placed.append(D.place_callout(pa, r, box, 0, label, [left, right], placed))
p, q = placed
OUT["clashes"] = [p["clashes"], q["clashes"]]
OUT["cross"] = any(D._segs_cross(s[0], s[1], t[0], t[1]) for s in p["segs"] for t in q["segs"])
OUT["hit"] = any(D._boxes_hit(x, y) for x in p["boxes"] for y in q["boxes"])
OUT["page_hit"] = D._boxes_hit(D.page_text_box(p["textAt"], a[3]), D.page_text_box(q["textAt"], b[3]))
OUT["clear_of_views"] = [not D._boxes_hit(sheets.text_box(c["text"]), v) for c in placed for v in (left, right)]
''')
        self.assertTrue(out["old_cross"])
        self.assertEqual(out["clashes"], [0, 0])
        self.assertFalse(out["cross"])
        self.assertFalse(out["hit"])
        self.assertFalse(out["page_hit"])
        self.assertTrue(all(out["clear_of_views"]))


class HealthReading(unittest.TestCase):
    """Documents' reading for Agent Link's shared health check: a page
    without a template, a view whose source is gone (red), a view the call
    recomputed that TechDraw has not drawn yet."""

    def test_pages_state(self):
        out = run(LATE_VIEW + r'''
from workshop_documents import td_wait as T
body = types.SimpleNamespace(Label="Bracket")
class PView(View):
    def __init__(self, label, late, source, **kw):
        super().__init__(label, late, **kw)
        self.Source = source
dim = types.SimpleNamespace(Label="Dimension")           # no Source: passed over
ok = PView("Front", 0, [body])
late = PView("Top", 3, [body])
orphan = PView("Right", 0, [])
page = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Label="Sheet", Template=object(), Views=[ok, late, orphan, dim])
bare = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Label="Bare", Template=None, Views=[])
ses = types.SimpleNamespace(doc=types.SimpleNamespace(Objects=[body, page, bare]))
OUT["after_body_change"] = T.page_reading(ses, "pd_pad", [body])
OUT["after_other_change"] = T.page_reading(ses, "setup", [])
OUT["no_doc"] = T.page_reading(types.SimpleNamespace(doc=None), "x", [])
''')
        got = out["after_body_change"]
        self.assertEqual([x["red"] for x in got], [False, True, False])
        self.assertIn("Top", got[0]["line"])
        self.assertIn("waiting", got[0]["line"])
        self.assertIn("Right", got[1]["line"])
        self.assertNotIn("todo", got[1])
        self.assertIn("Bare", got[2]["line"])
        # A call that recomputed neither a view nor its source asks no view whether it is drawn.
        self.assertEqual([x["red"] for x in out["after_other_change"]], [True, False])
        self.assertEqual(out["no_doc"], [])


# A page as FreeCAD 1.1's TechDraw source reads (see td_wait.py, "what an
# export leaves marked"): a property set marks its object changed and tells
# the document's observers; an object recomputed by itself executes, tells
# them, and keeps its mark (Document::recomputeFeature) — only purgeTouched
# or a document recompute takes it off; drawing the template writes its
# size back; a dimension on a view at a scale other than 1 writes its
# references again whenever it executes; a part view recomputed by itself
# starts its lines afresh and, some turns of the event loop later,
# recomputes its dimensions.
TECHDRAW_AS_THE_SOURCE_READS = r"""
import types
import FreeCAD
from workshop_documents import td_wait

observers = []
FreeCAD.addDocumentObserver = observers.append
FreeCAD.removeDocumentObserver = observers.remove
doc = types.SimpleNamespace(Name="Doc")
queue = []   # [turns left, fn]: what a view's thread hands back to the event loop


class Obj:
    def __init__(self, name, kind):
        self.Name, self.TypeId, self.Document, self.State, self.executed, self.OutList = name, kind, doc, [], 0, []

    def write(self, prop):                      # a property set, to any value
        if "Touched" not in self.State:
            self.State.append("Touched")
        for o in list(observers):
            o.slotChangedObject(self, prop)

    def execute(self):
        self.executed += 1

    def recompute(self):                        # by itself: the mark stays
        self.execute()
        for o in list(observers):
            o.slotRecomputedObject(self)

    def purgeTouched(self):
        self.State = []


class Template(Obj):
    def __init__(self, name):
        super().__init__(name, "TechDraw::DrawSVGTemplate")

    def draw(self):                             # QGISVGTemplate::draw -> processTemplate
        for p in ("Width", "Height", "Orientation"):
            self.write(p)


class PartView(Obj):
    def __init__(self, name, scale=2.0, late=2):
        super().__init__(name, "TechDraw::DrawViewPart")
        self.Scale, self.late, self.CoarseView, self.dims = scale, late, False, []

    def getVisibleEdges(self):
        return ["e"]

    def execute(self):
        super().execute()
        if not self.CoarseView:                 # lines afresh on a thread; faces after them
            queue.append([self.late, lambda: [d.recompute() for d in self.dims]])


class Dimension(Obj):
    def __init__(self, name, view):
        super().__init__(name, "TechDraw::DrawViewDimension")
        self.view, self.OutList = view, [view]
        view.dims.append(self)

    def execute(self):
        super().execute()
        if self.view.Scale != 1.0:              # the saved geometry is unscaled, the check reads it scaled
            for p in ("References2D", "SavedGeometry", "BoxCorners"):
                self.write(p)


turns = []
def pump():
    turns.append(1)
    for item in list(queue):
        item[0] -= 1
        if item[0] <= 0:
            queue.remove(item)
            item[1]()
    return True


def export_svg(page):                           # QGSPage::saveSvg
    page.Template.draw()


def export_pdf(page):                           # PagePrinter::printPdf -> DrawPage::redrawCommand
    page.Template.draw()
    for v in page.Views:
        if isinstance(v, PartView):
            v.recompute()
    for v in page.Views:
        if not isinstance(v, PartView):
            v.recompute()


def sheet(scale=2.0, late=2):
    tpl = Template("Template001")
    front, top = PartView("View", scale, late), PartView("View001", scale, late + 1)
    dims = [Dimension("Dimension003", front), Dimension("Dimension004", front), Dimension("Dimension005", top)]
    page = Obj("Page001", "TechDraw::DrawPage")
    page.Template, page.Views = tpl, [front, top] + dims
    return page, tpl, [front, top], dims


def marked(page):
    return [o.Name for o in [page.Template] + page.Views + [page] if "Touched" in o.State]
"""


class PageSettled(unittest.TestCase):
    """Found live (run 2): the call after drawing_make read "6 objects not
    recomputed yet" — the section page's template and its five dimensions.
    The first fix recomputed each of them by itself, which is the very call
    that leaves the mark."""

    def test_recomputing_each_by_itself_never_took_the_mark_off(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
export_svg(page)
export_pdf(page)
for _ in range(6):
    pump()
OUT["after"] = marked(page)
for o in [tpl] + dims:
    o.recompute()                               # what settle_page did
OUT["after_old_fix"] = marked(page)
""")
        self.assertEqual(out["after"], ["Template001", "Dimension003", "Dimension004", "Dimension005"])
        self.assertEqual(out["after_old_fix"], out["after"])

    def test_an_export_leaves_the_page_unmarked_and_waits_for_what_arrives_late(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_svg(page)
    export_pdf(page)
OUT["settled"] = px.settled
OUT["marked"] = marked(page)
OUT["turns"] = len(turns)
OUT["views_executed"] = [v.executed for v in views]
OUT["dims_executed"] = [d.executed for d in dims]
for _ in range(10):                             # and nothing arrives after the call
    pump()
OUT["marked_later"] = marked(page)
OUT["observers"] = len(observers)
""")
        s = out["settled"]
        self.assertEqual(s["cleared"], ["Template001", "Dimension003", "Dimension004", "Dimension005"])
        self.assertNotIn("late", s)
        self.assertNotIn("left", s)
        self.assertEqual((out["marked"], out["marked_later"]), ([], []))
        # waited for the later of the two views (3 turns), then the quiet turns
        self.assertGreaterEqual(out["turns"], 3)
        # nothing recomputed by the settle itself: a part view would start its lines afresh
        self.assertEqual(out["views_executed"], [1, 1])
        self.assertEqual(out["dims_executed"], [2, 2, 2])  # the export's redraw, and when its view's lines came
        self.assertEqual(out["observers"], 0)  # the watch is taken away again

    def test_an_svg_only_export_waits_for_nothing(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_svg(page)
OUT["settled"] = px.settled
OUT["turns"] = len(turns)
OUT["marked"] = marked(page)
""")
        self.assertEqual(out["settled"]["cleared"], ["Template001"])
        self.assertEqual((out["turns"], out["marked"]), (0, []))

    def test_at_one_to_one_only_the_template_is_marked(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet(scale=1.0)
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_pdf(page)
OUT["settled"] = px.settled
OUT["marked"] = marked(page)
""")
        self.assertEqual(out["settled"]["cleared"], ["Template001"])
        self.assertEqual(out["marked"], [])

    def test_what_was_marked_before_or_changed_otherwise_keeps_its_mark(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
dims[0].write("FormatSpec")                     # before the export: someone's change, not recomputed yet
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_pdf(page)
    dims[1].write("X")                          # during it: a position moved
    page.State.append("Touched")                # marked with nothing written (touch())
OUT["settled"] = px.settled
OUT["marked"] = marked(page)
""")
        s = out["settled"]
        self.assertEqual(s["cleared"], ["Template001", "Dimension005"])
        self.assertEqual([x["object"] for x in s["left"]], ["Dimension003", "Dimension004", "Page001"])
        self.assertEqual("changedBefore", s["left"][0]["why"])
        self.assertEqual(("changedDuring", ["X"]), (s["left"][1]["why"], s["left"][1]["props"]))
        self.assertEqual("nothingWritten", s["left"][2]["why"])
        self.assertEqual(out["marked"], ["Dimension003", "Dimension004", "Page001"])

    def test_a_dimension_not_seen_again_in_time_is_said(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet(late=10 ** 6)    # its lines never arrive
with td_wait.PageExport(page, timeout=0.05, pump=pump, sleep=0.01) as px:
    export_pdf(page)
OUT["settled"] = px.settled
OUT["marked"] = marked(page)
""")
        s = out["settled"]
        self.assertEqual(s["late"], ["Dimension003", "Dimension004", "Dimension005"])
        # what is marked now is still taken off; the mark that may follow is named, not hidden
        self.assertEqual(s["cleared"], ["Template001", "Dimension003", "Dimension004", "Dimension005"])
        self.assertEqual(out["marked"], [])

    def test_a_coarse_view_is_not_waited_for_and_no_event_loop_is_no_wait(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
for v in views:
    v.CoarseView = True                         # its lines at once: nothing arrives later
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_pdf(page)
OUT["coarse"] = px.settled
OUT["coarse_turns"] = len(turns)
page, tpl, views, dims = sheet()
with td_wait.PageExport(page, timeout=5, pump=lambda: False, sleep=0) as px:
    export_pdf(page)
OUT["no_loop"] = px.settled
""")
        self.assertNotIn("late", out["coarse"])
        self.assertEqual(out["coarse_turns"], 0)
        self.assertEqual(out["no_loop"]["late"], ["Dimension003", "Dimension004", "Dimension005"])
        self.assertLess(out["no_loop"]["waited"], 1.0)

    def test_an_export_that_raises_is_not_settled_and_nothing_to_watch_with_clears_nothing(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
page, tpl, views, dims = sheet()
px = td_wait.PageExport(page, timeout=5, pump=pump, sleep=0)
try:
    with px:
        export_svg(page)
        raise RuntimeError("the export failed")
except RuntimeError as e:
    OUT["raised"] = str(e)
OUT["settled"] = px.settled
OUT["observers"] = len(observers)
OUT["marked"] = marked(page)
def refuse(o):
    raise RuntimeError("no observers here")
FreeCAD.addDocumentObserver = refuse
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px2:
    export_svg(page)
OUT["unwatched"] = px2.settled
OUT["marked_unwatched"] = marked(page)
""")
        self.assertEqual((out["raised"], out["settled"], out["observers"]), ("the export failed", None, 0))
        self.assertEqual(out["marked"], ["Template001"])
        self.assertEqual(out["unwatched"], {"cleared": [], "waited": 0.0, "unwatched": True, "exportMs": out["unwatched"]["exportMs"]})
        self.assertGreaterEqual(out["unwatched"]["exportMs"], 0)
        self.assertEqual(out["marked_unwatched"], ["Template001"])

    def test_the_wait_is_sized_by_how_long_the_views_took(self):
        out = run(r"""
from workshop_documents.handlers import drawing as D
OUT["t"] = [D._settle_timeout(x) for x in ({"viewsReadyIn": 0.24}, {"viewsReadyIn": 3.0}, {"viewsReadyIn": 60}, {}, None, "no page")]
OUT["say"] = [D._worth_saying(x) for x in ({"cleared": ["Template"], "waited": 0.0}, {"cleared": [], "waited": 5.0, "late": ["Dimension"]},
                                             {"cleared": [], "waited": 0.0, "unwatched": True}, None)]
""")
        self.assertEqual(out["t"], [5.0, 14.0, 30.0, 5.0, 5.0, 5.0])
        self.assertEqual(out["say"], [False, True, True, False])


class WhereTheTimeGoes(unittest.TestCase):
    """Found live (run 3): with the wait after the export in, drawing_make
    took 4.6 and 5.7 s where it had taken 0.8 s, and patent_figures 6.6 s
    for 1.2 s; page.settled.waited said 0.95 and 1.49 s of it, and 2 to
    2.6 s a drawing (5.3 s in patent_figures) were in no field. The answer
    now carries the split, the turns of the event loop a call ran are
    counted and timed, and two things that were done twice are done once:
    the turns that draw the window's scene before an export that readies
    its scene itself, and reading the exported SVG back."""

    def test_a_wait_that_only_asks_runs_no_turns_to_draw_the_scene(self):
        out = run(LATE_VIEW + r'''
from workshop_documents import td_wait
views = [View("Front", 0), View("Top", 0)]
td_wait.views_ready(views, timeout=5, pump=pump, sleep=0)
OUT["drawn"] = len(turns)
del turns[:]
got = td_wait.views_ready(views, timeout=5, pump=pump, sleep=0, draw=False)
OUT["asked"] = [len(turns), got["notReady"]]
del turns[:]
views = [View("Front", 0), View("Top", 4)]
got = td_wait.views_ready(views, timeout=5, pump=pump, sleep=0, draw=False)
OUT["waited"] = [len(turns), got["notReady"], [v.late for v in views]]
''')
        self.assertEqual(out["drawn"], 3)                 # as before: three turns for the scene
        self.assertEqual(out["asked"], [0, []])           # ready at once: nothing run
        self.assertEqual(out["waited"], [4, [], [0, 0]])  # still waits for lines that are late, and no longer

    def test_turns_are_counted_and_timed(self):
        out = run(LATE_VIEW + r'''
import time
from workshop_documents import td_wait
def slow():
    time.sleep(0.01)
    return pump()
mark = td_wait.turns_now()
views = [View("Top", 2)]
td_wait.views_ready(views, timeout=5, pump=slow, sleep=0)
OUT["since"] = td_wait.turns_since(mark)
OUT["none"] = td_wait.turns_since(td_wait.turns_now())
OUT["turning_after"] = td_wait._TURNING[0]
''')
        self.assertEqual(out["since"]["turns"], 5)        # two to wait, three to draw
        self.assertGreaterEqual(out["since"]["turnMs"], 45)
        self.assertLess(out["since"]["turnMs"], 2000)
        self.assertEqual(out["none"], {"turns": 0, "turnMs": 0})
        self.assertEqual(out["turning_after"], 0)

    def test_settled_says_what_the_export_and_the_wait_cost(self):
        out = run(TECHDRAW_AS_THE_SOURCE_READS + r"""
import time
page, tpl, views, dims = sheet()
with td_wait.PageExport(page, timeout=5, pump=pump, sleep=0) as px:
    export_svg(page)
    time.sleep(0.03)                            # the export itself
    export_pdf(page)
OUT["settled"] = px.settled
OUT["turns"] = len(turns)
OUT["marked"] = marked(page)
""")
        s = out["settled"]
        self.assertEqual(set(s), {"cleared", "waited", "exportMs", "turns", "turnMs", "seen"})
        self.assertEqual(s["cleared"], ["Template001", "Dimension003", "Dimension004", "Dimension005"])  # the proven result, unchanged
        self.assertEqual(out["marked"], [])
        self.assertGreaterEqual(s["exportMs"], 30)
        self.assertLess(s["exportMs"], 2000)
        self.assertEqual(s["turns"], out["turns"])        # every turn the wait ran, and no other
        self.assertGreaterEqual(s["turnMs"], 0)
        # the template drawn twice (3 writes each), two views and three
        # dimensions recomputed by the redraw, the dimensions once more when
        # their views' lines came; a dimension writes 3 properties each time
        self.assertEqual(s["seen"], {"changed": 6 + 9 + 9, "recomputed": 2 + 3 + 3})

    def test_the_export_gives_its_split_and_reads_the_svg_back_once(self):
        out = run(EXPORT + r'''
asked, reads = [], []
D._wait_views = lambda vs, **kw: (asked.append(kw), td_wait.views_ready(vs, timeout=0.05, pump=pump, sleep=0, **kw))[1]
real = D.views_in_svg
def counted(*a, **k):
    reads.append(1)
    return real(*a, **k)
D.views_in_svg = counted
page.drawn = lambda: True
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)
OUT["good"] = [sorted(paths), why, rep["viewsInExport"]["ok"], sorted(rep["ms"]), len(reads), list(asked), len(turns), len(exports)]
del reads[:], asked[:], exports[:]
state = {"n": 0}
def drawn():
    state["n"] += 1
    return state["n"] > 1
page.drawn = drawn
rep = {}
paths, why = D._export_page(page, d, "Stem2", report=rep)
OUT["again"] = [sorted(paths), why, rep["viewsInExport"]["ok"], len(reads), list(asked), len(exports)]
del reads[:], exports[:]
page.drawn = lambda: False
rep = {}
paths, why = D._export_page(page, d, "Stem3", report=rep)
OUT["never"] = [sorted(paths), sorted(why), len(reads), len(exports)]
OUT["ints"] = all(isinstance(v, int) and v >= 0 for v in rep["ms"].values())
''')
        paths, why, ok, keys, reads, asked, n_turns, n_exports = out["good"]
        self.assertEqual((paths, why, ok), (["dxf", "pdf", "svg"], {}, True))
        self.assertEqual(keys, ["check", "dxf", "pdf", "scene", "svg", "wait"])
        self.assertEqual(reads, 1)                        # before: read and counted twice
        self.assertEqual(asked, [{"draw": False}])        # the wait before the export only asks
        self.assertEqual(n_exports, 1)
        # written again when its views are missing: that file is read again, and the wait then draws
        paths, why, ok, reads, asked, n_exports = out["again"]
        self.assertEqual((paths, why, ok, reads, n_exports), (["dxf", "pdf", "svg"], {}, True, 2, 2))
        self.assertEqual(asked, [{"draw": False}, {}])
        paths, why, reads, n_exports = out["never"]
        self.assertEqual((paths, why, reads, n_exports), (["dxf"], ["pdf", "svg"], 2, 2))
        self.assertTrue(out["ints"])

    def test_a_wait_that_knows_no_draw_is_still_used(self):
        out = run(EXPORT + r'''
page.drawn = lambda: True
rep = {}
paths, why = D._export_page(page, d, "Stem", report=rep)   # EXPORT's wait takes the views only
OUT["r"] = [sorted(paths), why, rep.get("viewsNotReady")]
''')
        self.assertEqual(out["r"], [["dxf", "pdf", "svg"], {}, None])

    def test_the_answers_timing(self):
        out = run(r"""
import time
from workshop_documents import td_wait
from workshop_documents.handlers import drawing as D
t0, mark = time.perf_counter(), td_wait.turns_now()
td_wait.views_ready([], pump=lambda: True, sleep=0)       # three turns
whole = D._timing(t0, mark, 12, 340, {"ms": {"wait": 1, "dxf": 2, "scene": 30, "svg": 40, "check": 5, "pdf": 60}, "viewsReadyIn": 0.0},
                  {"cleared": ["Template"], "waited": 0.95, "exportMs": 140, "turns": 9, "turnMs": 20})
OUT["whole"] = whole
OUT["files_only"] = D._timing(t0, td_wait.turns_now(), 12, None, {}, None)
OUT["no_export"] = D._timing(t0, td_wait.turns_now(), 12, 5, {}, None)
""")
        w = out["whole"]
        self.assertEqual(list(w), ["sheet", "page", "export", "settle", "turns", "turnMs", "total"])
        self.assertEqual((w["sheet"], w["page"], w["settle"], w["turns"]), (12, 340, 950, 3))
        self.assertEqual(w["export"], {"wait": 1, "dxf": 2, "scene": 30, "svg": 40, "check": 5, "pdf": 60})
        self.assertGreaterEqual(w["total"], 0)
        self.assertEqual(list(out["files_only"]), ["sheet", "turns", "turnMs", "total"])  # page: false — a part left out did not run
        self.assertEqual(list(out["no_export"]), ["sheet", "page", "turns", "turnMs", "total"])


if __name__ == "__main__":
    unittest.main()
