# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make judged on a live page (a bike stem, 102 × 49 × 47 mm, FreeCAD
# 1.1.3, 16 Nov 2026): A3 at 1:2 with the views about 12% of the sheet;
# the overall dimensions inside the views, their text over the geometry;
# the blank template (1.1's ISO 5457 templates were not found by name); hole
# callouts in a view that does not see the holes end on. Plain Python for
# the layout and the sheet writer; FreeCAD stood in for the template choice.
# WORKSHOP_SHEET_PNG=folder writes the test sheets there as SVG (and PNG
# with rsvg-convert) to look at.
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

from workshop_documents import sheets  # noqa: E402
from _stubs import run  # noqa: E402

AXES = {"front": ("x", "z"), "top": ("x", "y"), "right": ("y", "z")}
# FreeCAD 1.1.3's ISO 5457 templates: 20 mm filing margin, a 180 × 62 mm
# title block (drawing.ROOM, measured on the templates).
ISO = {"A4": ((20, 10, 287, 200), (180, 62)), "A3": ((20, 10, 410, 287), (180, 62))}


def papers():
    return [(p, sheets.PAPER[p], *ISO[p]) for p in ("A4", "A3")]


def stem_sizes(dx=102.0, dy=49.0, dz=47.0):
    iso = ((dx + dy) * 0.866, dz + (dx + dy) * 0.5)
    return {"front": (dx, dz), "top": (dx, dy), "right": (dy, dz), "iso": iso}, {"x": dx, "y": dy, "z": dz}


def build(paper, L, extent):
    s = sheets.Sheet(*sheets.PAPER[paper], title="fit")
    s.frame()
    for v, b in L["boxes"].items():
        s.line([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], "visible", closed=True)
        s.text((b[0] + b[2]) / 2, b[1] - 3, 3.0, v.upper(), "middle")
    for v, axis, pa, pb, off, mm in sheets.extent_dims({v: L["boxes"][v] for v in L["boxes"] if v in AXES}, AXES, extent):
        s.dimension(pa, pb, off, f"{mm:g}")
    if L.get("block"):
        b = L["block"]
        s.line([(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])], "thin", closed=True)
    return s


def look(name, s):
    folder = os.environ.get("WORKSHOP_SHEET_PNG")
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, name + ".svg")
    with open(p, "w", encoding="utf-8") as f:
        f.write(s.svg())
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "1600", "-b", "white", p, "-o", p[:-4] + ".png"], check=False)


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class Fit(unittest.TestCase):
    def test_stem_fills_the_sheet(self):
        sizes, extent = stem_sizes()
        paper, L = sheets.choose(sizes, papers(), "first")
        look("stem", build(paper, L, extent))
        # At 1:1 the three views with their dimensions do not clear A4's
        # 62 mm title block; A3 at 1:1 does (A3 at 1:2 was the old answer).
        self.assertEqual((paper, L["scale"]), ("A3", 1))
        self.assertGreaterEqual(L["fill"], 0.3)
        self.assertLessEqual(L["fill"], sheets.FILL_MAX)

    def test_small_part_on_a4_at_the_largest_scale(self):
        sizes, extent = stem_sizes(40, 20, 12)
        paper, L = sheets.choose(sizes, papers(), "first")
        look("small", build(paper, L, extent))
        self.assertEqual(paper, "A4")
        self.assertGreaterEqual(L["scale"], 2)
        self.assertLessEqual(L["fill"], sheets.FILL_MAX)
        self.assertGreaterEqual(L["fill"], 0.3)

    def test_views_clear_the_title_block_and_each_other(self):
        for dims, proj in (((102, 49, 47), "first"), ((102, 49, 47), "third"), ((300, 80, 60), "first"), ((15, 15, 60), "third")):
            sizes, extent = stem_sizes(*dims)
            paper, L = sheets.choose(sizes, papers(), proj)
            cells = list(L["cells"].items())
            for v, c in cells:
                self.assertFalse(hit(c, L["block"]), (dims, proj, v))
                a = L["area"]
                self.assertTrue(a[0] - 1e-6 <= c[0] and c[2] <= a[2] + 1e-6 and a[1] - 1e-6 <= c[1] and c[3] <= a[3] + 1e-6, (dims, v))
            for i, (v, c) in enumerate(cells):
                for w, d in cells[i + 1:]:
                    self.assertFalse(hit(c, d), (dims, proj, v, w))
            if proj == "first":
                self.assertLess(L["centres"]["right"][0], L["centres"]["front"][0])
            else:
                self.assertGreater(L["centres"]["right"][0], L["centres"]["front"][0])

    def test_dimension_text_off_the_views_and_each_other(self):
        for dims in ((102, 49, 47), (40, 20, 12), (300, 80, 60)):
            sizes, extent = stem_sizes(*dims)
            paper, L = sheets.choose(sizes, papers(), "first")
            s = build(paper, L, extent)
            n_views = len(L["boxes"])
            texts = [sheets.text_box(t) for t in s.texts[n_views:]]  # the dimensions' texts
            self.assertEqual(len(texts), 3, dims)  # x, y and z once each
            for t in texts:
                for v, b in L["boxes"].items():
                    self.assertFalse(hit(t, b), (dims, v, t))
            for i, t in enumerate(texts):
                for u in texts[i + 1:]:
                    self.assertFalse(hit(t, u), (dims, t, u))
            # Outside the outline: every dimension line 10 mm or more off it.
            for v, axis, pa, pb, off, mm in sheets.extent_dims({v: L["boxes"][v] for v in L["boxes"] if v in AXES}, AXES, extent):
                self.assertGreaterEqual(off, 10)

    def test_old_layout_was_too_empty(self):
        # What 86e6636 chose for the stem, by the room it left (full-width
        # 45 mm foot): A3 at 1:2, the views a small part of the sheet.
        sizes, _ = stem_sizes()
        views_area = sum(w * h for v, (w, h) in sizes.items() if v != "iso") * 0.25
        self.assertLess(views_area / (400 * 277), 0.05)

    def test_a_scale_that_does_not_fit_is_refused(self):
        sizes, _ = stem_sizes()
        with self.assertRaises(ValueError):
            sheets.layout(sizes, sheets.PAPER["A4"], "first", scale=2, area=ISO["A4"][0], block=ISO["A4"][1])


class Template(unittest.TestCase):
    def test_freecad_11_iso5457_template_and_its_fields(self):
        out = run(r'''
import os, tempfile
from workshop_documents.handlers import drawing as D
res = tempfile.mkdtemp()
base = os.path.join(res, "Mod", "TechDraw", "Templates", "ISO")
os.makedirs(os.path.join(base, "localized", "ca"))
for n in ("A3_Landscape_ISO5457_advanced.svg", "A3_Landscape_ISO5457_minimal.svg", "A3_Landscape_TD.svg", "A3_Landscape_blank.svg",
          "A4_Landscape_TD.svg", "A4_Landscape_blank.svg"):
    open(os.path.join(base, n), "w").write("<svg/>")
open(os.path.join(base, "localized", "ca", "A4_Landscape_ISO5457_advanced.svg"), "w").write("<svg/>")
class Params:
    def GetString(self, k, d=""): return d
    def GetInt(self, k, d=0): return d
D.FreeCAD.getResourceDir = lambda: res
D.FreeCAD.ParamGet = lambda path: Params()
a3, a4 = D._template("A3"), D._template("A4")
OUT["a3"] = [os.path.basename(a3[0]), a3[1]]
OUT["a4"] = [os.path.relpath(a4[0], base), a4[1]]
OUT["room"] = [list(x) for x in D.template_room(a3[0], "A3")]
keys = ["approval_person", "creator", "date_of_issue", "document_status", "document_type", "drawing_number", "general_tolerances", "language_code",
        "legal_owner_1", "part_material", "revision_index", "scale", "sheet_number", "supplementary_title_1", "title"]
OUT["fields"] = D.template_texts(keys, {"title": "StemV2", "material": "AW-6061", "scale": "1:1", "date": "2026-11-16", "generalTolerance": "ISO 2768-m",
                                        "sheet": "1 / 1", "projection": "first angle"})
OUT["proj"] = D.default_projection(None)
OUT["label"] = D.hole_label(4, "⌀8", "THRU ⌴⌀13 ↧8.5")
''')
        self.assertEqual(out["a3"], ["A3_Landscape_ISO5457_advanced.svg", True])
        # A4: the plain TD one before a localized copy of the ISO 5457 one.
        self.assertEqual(out["a4"][1], True)
        self.assertNotIn("localized", out["a4"][0])
        self.assertEqual(out["room"], [[20, 10, 410, 287], [180, 62]])
        self.assertEqual(out["fields"], {"title": "StemV2", "part_material": "AW-6061", "scale": "1:1", "date_of_issue": "2026-11-16",
                                         "general_tolerances": "ISO 2768-m", "sheet_number": "1 / 1"})
        self.assertEqual(out["proj"], ["first", "ISO default"])
        self.assertEqual(out["label"], "4× ⌀8 THRU ⌴⌀13 ↧8.5")

    def test_callout_leader_clears_the_view(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
from workshop_documents import sheets
box = (100, 50, 202, 97)
got = []
for k, at in enumerate([(110, 70), (190, 70), (150, 60)]):
    tip, elbow, tail, anchor = D.callout_leader(at, 4, box, k)
    t = (tail[0] + (1 if anchor == "start" else -1), tail[1] - 1, 3.0, D.hole_label(4, "⌀8", "THRU ⌴⌀13 ↧8.5"), anchor)
    got.append(sheets.text_box(t))
OUT["boxes"] = got
''')
        for b in out["boxes"]:
            self.assertLess(b[3], 50, b)  # the text over the view's top edge


class PageLive(unittest.TestCase):
    """Found on the TechDraw page itself (f6c14e2, the stem): the front
    view's extents read 0, six of eight hole groups were not found though
    drawn, a counterbore came out as two callouts."""

    def test_extent_between_the_extreme_vertices_checked(self):
        out = run(r"""
import types
from workshop_documents.handlers import drawing as D
pts = [(10, 5), (112, 5), (60, 30), (10, 52), (112, 52)]
class View:
    def getVertexByIndex(self, i):
        if i >= len(pts): raise IndexError(i)
        return types.SimpleNamespace(Point=types.SimpleNamespace(x=pts[i][0], y=pts[i][1]))
class Dim:
    Name = "Dimension"
    def getRawValue(self):
        (_, a), (_, b) = self.References2D
        i, j = int(a[6:]), int(b[6:])
        return abs(pts[j][0] - pts[i][0]) if self.Type == "DistanceX" else abs(pts[j][1] - pts[i][1])
removed = []
doc = types.SimpleNamespace(addObject=lambda t, n: Dim(), recompute=lambda: None, removeObject=removed.append)
page = types.SimpleNamespace(addView=lambda d: None, removeView=lambda d: None)
v = View()
ok = D._extent_dim(doc, page, v, True, 102)
OUT["ok"] = [ok["measured"], [r[1] for r in ok["dim"].References2D]]
OUT["v"] = D._extent_dim(doc, page, v, False, 47)["measured"]
OUT["bad"] = D._extent_dim(doc, page, v, False, 49)
OUT["removed"] = len(removed)
""")
        self.assertEqual(out["ok"], [102, ["Vertex0", "Vertex1"]])
        self.assertEqual(out["v"], 47)
        self.assertEqual((out["bad"]["why"], out["bad"]["wanted"]), ("measuredOther", 49))  # a wrong size is left off, said
        self.assertEqual(out["removed"], 1)

    def test_circle_found_in_whichever_frame_the_view_uses(self):
        out = run(r"""
from workshop_documents.handlers import drawing as D
# The view's circles scaled 1 and turned over in y; the fitted frame is
# off by 3 mm (its extents thrown by a hidden line).
circles = [(20, -10, 6.5), (-20, -10, 6.5), (0, 0, 14)]
fitted = (lambda p: (p[0] + 3, p[1] + 3), 1.0)
own = (lambda p: (p[0], -p[1]), 1.0)
OUT["fitted_only"] = D.match_circle(circles, (20, 10), 6.5, [fitted])
OUT["with_own"] = D.match_circle(circles, (20, 10), 6.5, [fitted, own])
OUT["big"] = D.match_circle(circles, (0, 0), 14, [own])
OUT["wrong_size"] = D.match_circle(circles, (0, 0), 10, [own])
""")
        self.assertIsNone(out["fitted_only"])  # 4.2 mm off: more than half its radius
        self.assertEqual(out["with_own"], 0)
        self.assertEqual(out["big"], 2)
        self.assertIsNone(out["wrong_size"])

    def test_a_pocket_round_a_hole_is_its_counterbore(self):
        out = run(r"""
from workshop_documents.handlers import drawing as D
holes = [{"diameter": 8.0, "centres": [(0, 0), (30, 0), (0, 20), (30, 20)], "thread": None, "suffix": "THRU", "cut": None, "cutDiameter": None, "features": ["Hole"]},
         {"diameter": 13.0, "centres": [(0, 0), (30, 0), (0, 20), (30, 20)], "thread": None, "suffix": None, "cut": None, "cutDiameter": None, "features": [], "depths": [8.5] * 4},
         {"diameter": 28.0, "centres": [(15, 50)], "thread": None, "suffix": None, "cut": None, "cutDiameter": None, "features": []}]
m = D.merge_counterbores(holes, lambda c: c)
OUT["labels"] = [D.hole_label(len(g["centres"]), "⌀%g" % g["diameter"], g.get("suffix")) for g in m]
""")
        self.assertEqual(out["labels"], ["4× ⌀8 THRU ⌴⌀13 ↧8.5", "⌀28"])

    def test_template_in_the_export(self):
        out = run(r"""
import os, tempfile, types
from workshop_documents.handlers import drawing as D
d = tempfile.mkdtemp()
page = types.SimpleNamespace(Template=types.SimpleNamespace(EditableTexts={"title": "StemV2", "scale": "1:1"}))
a, b = os.path.join(d, "a.svg"), os.path.join(d, "b.svg")
open(a, "w").write("<svg><g><path d='M0 0'/></g></svg>")
open(b, "w").write("<svg><text>StemV2</text></svg>")
OUT["r"] = [D.template_in_svg(a, page), D.template_in_svg(b, page)]
""")
        self.assertEqual(out["r"], [False, True])

    def test_a_blank_template_has_nothing_to_be_left_out(self):
        # Found live (run 2, patent_figures): on TechDraw's blank template
        # the check found none of a title block's words in the export and
        # said "TechDraw left the template out", so the figure's files came
        # from Workshop's sheet writer, not the page that was made.
        out = run(r"""
import os, tempfile, types
from workshop_documents.handlers import drawing as D
d = tempfile.mkdtemp()
blank, framed, svg = (os.path.join(d, n) for n in ("blank.svg", "framed.svg", "out.svg"))
open(blank, "w").write("<svg width='210mm' height='297mm'></svg>")
open(framed, "w").write("<svg><text>Title</text><text>Scale</text></svg>")
open(svg, "w").write("<svg><g><path d='M0 0'/></g></svg>")
page = lambda path, texts: types.SimpleNamespace(Template=types.SimpleNamespace(EditableTexts=texts, Template=path))
OUT["blank"] = D.template_in_svg(svg, page(blank, {}))
OUT["framed"] = D.template_in_svg(svg, page(framed, {}))
OUT["gone"] = D.template_in_svg(svg, page(os.path.join(d, "none.svg"), {}))
""")
        self.assertEqual((out["blank"], out["framed"], out["gone"]), (True, False, False))


if __name__ == "__main__":
    unittest.main()
