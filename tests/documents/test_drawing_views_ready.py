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
        self.assertIn("no view geometry", pdf)
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


if __name__ == "__main__":
    unittest.main()
