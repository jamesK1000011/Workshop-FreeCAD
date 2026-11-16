# SPDX-License-Identifier: LGPL-2.1-or-later
# Drawing… as a normal TechDraw page: TechDraw's own template with its
# title block (its preference first), the title block's fields filled by
# name, and the files as the page's own TechDraw exports where TechDraw
# can write them. FreeCAD and TechDraw stood in for.
import unittest

from _stubs import run


class Template(unittest.TestCase):
    def test_title_block_fields_by_name(self):
        out = run(r'''
from workshop_documents.handlers import drawing as D
iso = ["DRAWING_TITLE", "SUBTITLE", "AUTHOR_NAME", "FC-SC", "FC-SH", "PN", "DATE", "MATERIAL"]
OUT["iso"] = D.template_texts(iso, {"title": "Bracket", "scale": "1:2", "drawnBy": "J. Maker", "material": "PLA", "partNumber": "B-1", "generalTolerance": "ISO 2768-m"})
OUT["other"] = D.template_texts(["Title", "Scale", "Revision"], {"title": "Lid", "scale": "1:1", "revision": "B", "company": "Shop"})
OUT["none"] = D.template_texts([], {"title": "X"})
''')
        self.assertEqual(out["iso"], {"DRAWING_TITLE": "Bracket", "FC-SC": "1:2", "AUTHOR_NAME": "J. Maker", "MATERIAL": "PLA", "PN": "B-1"})
        self.assertEqual(out["other"], {"Title": "Lid", "Scale": "1:1", "Revision": "B"})
        self.assertEqual(out["none"], {})

    def test_techdraws_own_template_first(self):
        out = run(r'''
import os, tempfile
from workshop_documents.handlers import drawing as D
res = tempfile.mkdtemp()
tpl = os.path.join(res, "Mod", "TechDraw", "Templates", "ISO")
os.makedirs(tpl)
for n in ("A4_Landscape_ISO7200TD.svg", "A4_Landscape_blank.svg", "A3_Landscape_blank.svg"):
    open(os.path.join(tpl, n), "w").write("<svg/>")
mine = os.path.join(res, "A4_Landscape_mine.svg")
open(mine, "w").write("<svg/>")
pref = {"TemplateFile": ""}
class Params:
    def GetString(self, k, d=""): return pref.get(k, d)
D.FreeCAD.getResourceDir = lambda: res
D.FreeCAD.ParamGet = lambda path: Params()
got = [D._template("A4"), D._template("A3")]
pref["TemplateFile"] = mine
got.append(D._template("A4"))
got.append(D._template("A3"))
OUT["got"] = [(os.path.basename(p) if p else None, t) for p, t in got]
OUT["room"] = D.TITLE_H
''')
        self.assertEqual(out["got"], [["A4_Landscape_ISO7200TD.svg", True], ["A3_Landscape_blank.svg", False],
                                      ["A4_Landscape_mine.svg", True], ["A3_Landscape_blank.svg", False]])
        self.assertGreater(out["room"]["true"], out["room"]["false"])


class Export(unittest.TestCase):
    def test_the_pages_own_exports(self):
        out = run(r'''
import os, tempfile, types
from workshop_documents.handlers import drawing as D
d = tempfile.mkdtemp()
def write(page, p): open(p, "w").write("0\nSECTION\n")
D.TechDraw.writeDXFPage = write
gui = types.ModuleType("TechDrawGui")
gui.exportPageAsPdf = lambda page, p: open(p, "w").write("%PDF")
gui.exportPageAsSvg = lambda page, p: open(p, "w").write("<svg/>")
sys.modules["TechDrawGui"] = gui
D._wait_views = lambda vs: None
page = types.SimpleNamespace(Views=[])
D.FreeCAD.GuiUp = False
paths, why = D._export_page(page, d, "Box")
OUT["headless"] = [sorted(os.path.basename(p) for p in paths.values()), sorted(why)]
D.FreeCAD.GuiUp = True
paths, why = D._export_page(page, d, "Box")
OUT["gui"] = [sorted(os.path.basename(p) for p in paths.values()), why]
def broken(page, p): raise RuntimeError("no views")
D.TechDraw.writeDXFPage = broken
paths, why = D._export_page(page, d, "Box2")
OUT["broken"] = [sorted(paths), why.get("dxf", "")]
''')
        self.assertEqual(out["headless"], [["Box.dxf"], ["pdf", "svg"]])
        self.assertEqual(out["gui"], [["Box.dxf", "Box.pdf", "Box.svg"], {}])
        self.assertEqual(out["broken"][0], ["pdf", "svg"])
        self.assertIn("no views", out["broken"][1])


if __name__ == "__main__":
    unittest.main()
