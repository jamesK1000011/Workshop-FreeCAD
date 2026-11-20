# SPDX-License-Identifier: LGPL-2.1-or-later
# The drawing family: sheets, manuals, patent figures. The sheet writers and
# the layout are tested anywhere; the views need FreeCAD and TechDraw.
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", ".."), os.path.join(HERE, "..", "..")]
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401
    import TechDraw  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False

try:
    import agentlink.tools  # noqa: F401
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "FreeCAD with TechDraw and Agent Link are not importable here")
class Drawing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agentlink.tools import Session, build_server

        # With AGENTLINK_RENDERS set the sheets are kept there, to look at.
        keep = os.environ.get("AGENTLINK_RENDERS")
        cls.dir = os.path.join(keep, "drawing") if keep else tempfile.mkdtemp()
        os.makedirs(cls.dir, exist_ok=True)
        cls.session = Session(out_dir=cls.dir)
        cls.server = build_server(cls.session, lean=False)
        err, m = cls.call(cls, "gen_part", {"generator": "project_box", "params": {"length": 80, "width": 60, "height": 30, "bosses": True}, "name": "Box"})
        assert not err, m

    def call(self, name, args=None):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})["result"]
        return r.get("isError", False), json.loads(r["content"][0]["text"])

    def test_1_sheet(self):
        err, d = self.call("drawing_make", {"bodies": ["Box"], "name": "Box"})
        self.assertFalse(err, d)
        print("\ndrawing:", json.dumps({k: d.get(k) for k in ("paper", "scale", "dimensions", "techdrawPage", "page", "pageNote")}))
        for k in ("svg", "pdf", "dxf"):
            self.assertTrue(os.path.getsize(d["files"][k]) > 500, k)
        with open(d["files"]["svg"], encoding="utf-8") as f:
            svg = f.read()
        self.assertGreater(svg.count("<path"), 20, "the views have lines")
        dims = {x["axis"]: x["mm"] for x in d["dimensions"]}
        self.assertAlmostEqual(dims["x"], 80, delta=0.01)
        self.assertAlmostEqual(dims["y"], 60, delta=0.01)
        self.assertAlmostEqual(dims["z"], 30, delta=0.01)
        self.assertIn(d["scale"], ("1:1", "1:2"))
        # Where the time went: always the sheet and the total; the page's parts when a page was made.
        self.assertGreaterEqual(d["timing"]["total"], d["timing"]["sheet"])
        self.assertEqual(set(d["timing"]) - {"page", "export", "settle", "sheetSplit", "sheetLines"}, {"sheet", "turns", "turnMs", "total"})
        # The page in the document, when TechDraw could make it here.
        if d["techdrawPage"]:
            self.assertTrue(any(o.TypeId == "TechDraw::DrawPage" for o in self.session.doc.Objects))
        err, e = self.call("drawing_make", {"views": ["side"]})
        self.assertTrue(err)
        self.assertIn("front", e["error"]["message"])
        err, e = self.call("drawing_make", {"bodies": ["Box"], "scale": 5, "paper": "A4"})
        self.assertTrue(err)
        self.assertIn("scale", e["error"]["message"])

    def test_1b_features_and_title(self):
        err, d = self.call("drawing_make", {
            "bodies": ["Box"], "name": "Box detail", "file": "Box_detail",
            "dims": [
                {"view": "front", "kind": "length", "a": [-40, -30, 0], "b": [-40, -30, 30], "along": "v", "plus": 0.1, "offset": -10},
            ],
            "holes": True, "holeFits": {},
            "titleBlock": {"partNumber": "AL-001", "revision": "B", "drawnBy": "Agent Link", "material": "PETG"},
        })
        self.assertFalse(err, d)
        print("\nfeatures:", json.dumps({k: d.get(k) for k in ("dimensions", "holes", "titleBlock")}))
        self.assertTrue(any(x.get("label") == "30 ±0.1" for x in d["dimensions"]), d["dimensions"])
        self.assertTrue(d["holes"], d)
        self.assertTrue(any(h["count"] == 4 for h in d["holes"]), d["holes"])
        with open(d["files"]["svg"], encoding="utf-8") as f:
            svg = f.read()
        for t in ("AL-001", "PETG", "ISO 2768-m", "30 ±0.1", "4× ⌀"):
            self.assertIn(t, svg)
        # The same dims and callouts on the TechDraw page, measured by TechDraw.
        print("page:", json.dumps(d.get("page")), json.dumps(d.get("pageNote")))
        if d["techdrawPage"]:
            on = d["page"].get("dimensions") or []
            self.assertFalse(d["page"].get("notOnPage"), d["page"])
            self.assertTrue(any(x["type"] == "DistanceY" and abs(x["measured"] - 30) < 0.01 for x in on), on)
            self.assertTrue(any(x["type"] == "Diameter" for x in on), on)
            for x in on:
                self.assertNotIn("warning", x)
            texts = [o.FormatSpec for o in self.session.doc.Objects if o.TypeId == "TechDraw::DrawViewDimension"]
            self.assertTrue(any(t.startswith("4× ") for t in texts), texts)
        err, e = self.call("drawing_make", {"bodies": ["Box"], "dims": [{"view": "front", "kind": "diameter", "a": [0, 0, 0], "fit": "Q9"}]})
        self.assertTrue(err)

    def test_1c_section(self):
        # The project box cut through its middle, seen from the front: its
        # walls and floor one U-shaped cut face, hatched; the cutting line
        # in the top view; TechDraw's own section on the page.
        err, d = self.call("drawing_make", {"bodies": ["Box"], "name": "Box section", "file": "Box_section", "views": ["front", "top", "right"], "section": "front"})
        print("\nsection:", json.dumps({k: d.get(k) for k in ("section", "page", "pageNote")}))
        self.assertFalse(err, d)
        self.assertEqual(d["section"]["cutLineIn"], "top")
        self.assertEqual(d["section"]["cutFaces"], 1)
        with open(d["files"]["svg"], encoding="utf-8") as f:
            svg = f.read()
        self.assertIn("SECTION A-A", svg)
        if d["techdrawPage"]:
            self.assertIn("section", d["page"], d["page"])
            sv = next(o for o in self.session.doc.Objects if o.TypeId == "TechDraw::DrawViewSection")
            self.assertEqual(sv.BaseView.Label.lower()[:3], "top")
        err, e = self.call("drawing_make", {"bodies": ["Box"], "views": ["front", "top"], "section": "iso"})
        self.assertTrue(err)

    def test_2_exploded(self):
        steps = [{"title": "The box", "add": ["Box"]}, {"title": "The lid", "add": ["Box lid"], "note": "Four M3 screws."}]
        # As printed, the lid lies beside the box: said so.
        err, x = self.call("drawing_exploded", {"steps": steps, "name": "laid_out"})
        self.assertFalse(err, x)
        self.assertIn("Box lid", x["warnings"][0])
        # Put on: turned over about X (the 2 mm plate then lies from z -2 to
        # 0) and lifted onto the box's 30 mm rim.
        lid = self.session.body("Box lid")
        bb = lid.Shape.BoundBox
        err, r = self.call("object_set", {"object": "Box lid", "values": {"Placement": {"at": [-bb.Center.x, 0, 32], "axis": [1, 0, 0], "angle": 180}}})
        self.assertFalse(err, r)
        err, pic = self.call("view_render", {"views": ["iso", "front"], "inline": False, "path": os.path.join(self.dir, "box_assembled.png")})
        self.assertFalse(err, pic)
        err, x = self.call("drawing_exploded", {"steps": steps, "name": "box"})
        self.assertFalse(err, x)
        self.assertNotIn("warnings", x)
        self.assertEqual(len(x["steps"]), 2)
        self.assertEqual([b["item"] for b in x["bom"]], [1, 2])
        with open(x["manual"], encoding="utf-8") as f:
            md = f.read()
        self.assertIn("| 2 | Box lid | 1 |", md)
        self.assertIn("box_step02.svg", md)
        self.assertTrue(os.path.isfile(x["steps"][1]["svg"]))
        err, e = self.call("drawing_exploded", {"steps": [{"add": ["Box"]}, {"add": ["Box"]}]})
        self.assertTrue(err)
        self.assertIn("once", e["error"]["message"])

    def test_3_patent(self):
        err, p = self.call("patent_figures", {"name": "box"})
        self.assertFalse(err, p)
        print("\npatent:", json.dumps({k: p.get(k) for k in ("numerals", "notSeenIn")}))
        self.assertEqual(len(p["figures"]), 4)
        self.assertEqual(p["timing"]["figures"], 4)
        self.assertTrue(all(f["timing"]["total"] >= f["timing"]["sheet"] >= 0 for f in p["figures"]))
        self.assertGreaterEqual(p["timing"]["total"], sum(f["timing"]["total"] for f in p["figures"]) - 5)
        self.assertEqual(p["numerals"], {"Box": 10, "Box lid": 20})
        with open(p["figures"][0]["svg"], encoding="utf-8") as f:
            svg = f.read()
        self.assertIn("FIG. 1", svg)
        self.assertIn(">10<", svg)
        err, d = self.call("patent_draft", {"title": "Project box", "field": "Enclosures for electronics."})
        self.assertFalse(err, d)
        with open(d["draft"], encoding="utf-8") as f:
            md = f.read()
        self.assertIn("NOT FOR FILING", md)
        self.assertIn("box 10", md)
        self.assertIn("FIG. 1 is an isometric view", md)


if __name__ == "__main__":
    unittest.main()
