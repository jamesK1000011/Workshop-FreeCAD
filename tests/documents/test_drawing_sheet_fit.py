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


if __name__ == "__main__":
    unittest.main()
