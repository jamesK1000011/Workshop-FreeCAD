# SPDX-License-Identifier: LGPL-2.1-or-later
# The sheet writers (SVG, PDF) and the layout, plain Python (from AddonKit's
# and Agent Link's sheet tests; Documents owns sheets.py, 14 Nov 2026).
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workshop_documents import sheets  # noqa: E402


class Writers(unittest.TestCase):
    def sheet(self):
        s = sheets.Sheet(297, 210, "Test (1)")
        s.frame()
        s.line([(20, 20), (60, 20), (60, 50)], "visible")
        s.line([(20, 30), (40, 30)], "hidden")
        s.dimension((20, 50), (60, 50), 8, "40")
        s.dimension((60, 50), (60, 20), 8, "30")
        s.text(100, 100, 3, "FRONT — A&B", "middle")
        return s

    def test_svg(self):
        svg = self.sheet().svg()
        self.assertTrue(svg.startswith("<?xml"))
        self.assertIn('width="297mm"', svg)
        self.assertIn("stroke-dasharray", svg)
        self.assertIn("A&amp;B", svg)
        self.assertIn("rotate(-90", svg)

    def test_pdf(self):
        pdf = self.sheet().pdf()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        xref = int(pdf[pdf.rindex(b"startxref") + 9:].split()[0])
        self.assertEqual(pdf[xref:xref + 4], b"xref")
        self.assertIn(b"/MediaBox [0 0 841.89 595.28]", pdf)

    def test_layout(self):
        sizes = {"front": (80, 30), "top": (80, 60), "right": (60, 30), "iso": (100, 80)}
        first = sheets.layout(sizes, sheets.PAPER["A4"], "first")
        third = sheets.layout(sizes, sheets.PAPER["A4"], "third")
        f, t = first["centres"], third["centres"]
        self.assertGreater(f["top"][1], f["front"][1], "first angle: top under the front")
        self.assertLess(f["right"][0], f["front"][0], "first angle: right on the left")
        self.assertLess(t["top"][1], t["front"][1], "third angle: top over the front")
        self.assertGreater(t["right"][0], t["front"][0])
        self.assertAlmostEqual(f["top"][0], f["front"][0])
        self.assertIn(first["scale"], sheets.SCALES)
        self.assertEqual(sheets.scale_text(0.5), "1:2")
        self.assertEqual(sheets.scale_text(2), "2:1")
        with self.assertRaises(ValueError):
            sheets.layout(sizes, sheets.PAPER["A4"], "first", scale=10)
        big = sheets.layout({"front": (900, 300), "top": (900, 600)}, sheets.PAPER["A3"])
        self.assertLess(big["scale"], 1)


if __name__ == "__main__":
    unittest.main()
