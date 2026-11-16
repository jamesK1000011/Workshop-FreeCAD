# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make's check of TechDraw's SVG export for the views' lines
# (views_in_svg) refused an export whose views were there. A live run
# (FreeCAD 1.1.3) counted 72 drawn elements, 48 the template's, 8
# dimensions and 280 view edges every time, while TechDraw's PDF of the
# same page held all four views: TechDraw writes a view's lines of one
# style as a few <path> elements of many subpaths each, so counting
# elements could not see them. The check now also counts the points drawn
# (path data's coordinate pairs). A stand-in of the live counts with the
# views' lines grouped passes; the same with only the template and the
# dimensions fails. FreeCAD and TechDraw stood in for.
import unittest

from _stubs import run

CASE = r'''
import os, types, tempfile
from workshop_documents.handlers import drawing as D
d = tempfile.mkdtemp()
# The template: 48 elements, its frame and title block lines.
tpl_marks = "".join("<path d='M %d 0 L %d 10'/>" % (i, i) for i in range(44)) + "<rect x='0' y='0' width='10' height='10'/>" * 4
tpl = os.path.join(d, "tpl.svg")
open(tpl, "w").write("<svg>" + tpl_marks + "<text>Title</text></svg>")

class View:
    def getVisibleEdges(self):
        return ["e"] * 70
class Dim:
    TypeId = "TechDraw::DrawViewDimension"
views = [View(), View(), View(), View()]       # 280 edges
dims = [Dim() for _ in range(8)]
page = types.SimpleNamespace(Views=views + dims, Template=types.SimpleNamespace(Template=tpl, EditableTexts={}))

# Qt writes the template's rects as paths of five points.
tpl_out = "".join("<path d='M %d 0 L %d 10'/>" % (i, i) for i in range(44)) + "<path d='M0 0 L10 0 L10 10 L0 10 Z'/>" * 4
# Each dimension: its lines in one path, its arrows in another, its text.
dim_out = "<g><path d='M0 0 L50 0 M0 -2 L0 5 M50 -2 L50 5'/><path d='M0 0 L3 1 L3 -1 Z M50 0 L47 1 L47 -1 Z'/><text>102</text></g>" * 8
def view_paths(edges):
    # One view's visible lines in one path, its hidden ones in another:
    # an edge a subpath of a move and a line (or a cubic for an arc).
    vis = " ".join("M %d %d L %d %d" % (i, i, i + 5, i) if i % 3 else "M %d %d C %d %d %d %d %d %d" % (i, i, i, i + 1, i + 1, i + 2, i + 2, i + 2) for i in range(edges))
    return "<g class='view'><path d='%s'/><path stroke-dasharray='2,1' d='M 0 0 L 1 1'/></g>" % vis

def write(name, body):
    p = os.path.join(d, name)
    open(p, "w").write("<svg>" + tpl_out + body + "<text>Title</text></svg>")
    return p

OUT = {}
rep = {}
p = write("views.svg", dim_out + "".join(view_paths(70) for _ in range(4)))
OUT["grouped"] = [D.views_in_svg(p, page, views, rep), rep["viewsInExport"]]
rep = {}
p = write("bare.svg", dim_out)
OUT["bare"] = [D.views_in_svg(p, page, views, rep), rep["viewsInExport"]]
rep = {}
# A view drawn only in part (a dozen of its 280 edges): still refused.
p = write("part.svg", dim_out + view_paths(12))
OUT["part"] = [D.views_in_svg(p, page, views, rep), rep["viewsInExport"]]
OUT["pts"] = [D._svg_points("<path d='M0,0L10,0C1,2 3,4 5,6'/>"), D._svg_points("<polyline points='0,0 1,1 2,2'/><rect/><circle/>")]
'''


class GroupedViewLines(unittest.TestCase):
    def setUp(self):
        self.out = run(CASE)

    def test_grouped_multi_subpath_views_pass(self):
        ok, counts = self.out["grouped"]
        self.assertTrue(ok)
        # The live counts: 72 elements, 48 the template's, 8 dimensions.
        self.assertEqual((counts["drawn"], counts["template"], counts["dimensions"], counts["viewEdges"]), (72, 48, 8, 280))
        self.assertFalse(counts["byElements"])
        self.assertTrue(counts["byPoints"])

    def test_template_and_dimensions_alone_fail(self):
        ok, counts = self.out["bare"]
        self.assertFalse(ok)
        self.assertFalse(counts["byPoints"])
        self.assertFalse(counts["byElements"])
        self.assertEqual(counts["templatePoints"], 44 * 2 + 4 * 5)

    def test_a_view_drawn_only_in_part_fails(self):
        ok, _ = self.out["part"]
        self.assertFalse(ok)

    def test_points_counted_from_path_data_and_shapes(self):
        self.assertEqual(self.out["pts"], [5, 3 + 5 + 13])


if __name__ == "__main__":
    unittest.main()
