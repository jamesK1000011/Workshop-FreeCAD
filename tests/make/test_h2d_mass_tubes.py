# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings of the bicycle design runs (OrcaSlicer 2.5.0, Bambu Studio, a
# Bambu Lab H2D with two nozzles), Make's part:
# 2a. slice via Bambu Studio's command line stopped on H2D presets (code -11,
#     "on_printer_model_change_cli: eid out of bounds"). A printer of more
#     than one extruder now goes to OrcaSlicer when it is here, and a Bambu
#     Studio slice that stops so is sliced once more with OrcaSlicer.
# 2b. The printed mass said 168 g for a saddle block OrcaSlicer sliced at
#     442 g. The estimate now comes with its band (massBand), and the slice's
#     own figure is used in its place while the body stays as sliced.
# 2c. A cut list for a weldment of round tubes (tube_cutlist).
import csv
import io
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.dirname(__file__))

from _stubs import run  # noqa: E402
from workshop_make import printmass as PM  # noqa: E402
from workshop_make import tubecut as TC  # noqa: E402


class H2DGoesToOrca(unittest.TestCase):
    def test_route(self):
        d = tempfile.mkdtemp()
        two = os.path.join(d, "m2.json")
        with open(two, "w") as f:
            json.dump({"nozzle_diameter": ["0.4", "0.4"]}, f)
        out = run(r'''
from workshop_make.handlers import slicing as S
two = %r
OUT["n"] = [S.extruders_of(two), S.extruders_of({"nozzle_diameter": ["0.4"]}), S.extruders_of("/nowhere.json"), S.extruders_of({"nozzle_diameter": "0.4;0.4"})]
OUT["multi"] = S.route_multi("bambustudio", two, True)
OUT["no_orca"] = S.route_multi("bambustudio", two, False)
OUT["one"] = S.route_multi("bambustudio", {"nozzle_diameter": ["0.4"]}, True)
OUT["orca"] = S.route_multi("orcaslicer", two, True)
OUT["crash"] = S.route_multi("bambustudio", None, True, crashed="The slicer stopped (code -11): on_printer_model_change_cli: eid out of bounds")
OUT["other"] = S.route_multi("bambustudio", None, True, crashed="The slicer stopped (code 1): no G-code written")
''' % two)
        self.assertEqual(out["n"], [2, 1, 1, 2])
        self.assertEqual(out["multi"][0], "orcaslicer")
        self.assertIn("2 extruders", out["multi"][1])
        self.assertEqual(out["no_orca"], ["bambustudio", None])
        self.assertEqual(out["one"], ["bambustudio", None])
        self.assertEqual(out["orca"], ["orcaslicer", None])
        self.assertEqual(out["crash"][0], "orcaslicer")
        self.assertEqual(out["other"], ["bambustudio", None])


class MassFromTheSlice(unittest.TestCase):
    def setUp(self):
        PM.SLICED.clear()

    def test_band_and_slice_figure(self):
        self.assertEqual(PM.band(168), [134.4, 453.6])  # the saddle block's 442 g is inside it
        doc = type("Doc", (), {"Name": "Bike"})()
        stats = {"volume": 1000.0, "faces": 6}
        last = {"statistics": {"weightG": 450.5, "weightBy": {"model": 442.0, "support": 8.5}}}
        rec = PM.remember_slice(doc, "Saddle block", stats, {"filamentG": 450.5}, last, "orcaslicer", "/out/s.gcode")
        self.assertEqual((rec["grams"], rec["modelGrams"], rec["supportGrams"]), (450.5, 442.0, 8.5))
        got, r = PM.slice_figure(doc, "Saddle block", stats)
        self.assertEqual(got, 442.0)
        self.assertIn("the part only", PM.slice_words(r))
        self.assertIn("supports 8.5 g more", PM.slice_words(r))
        # The body changed since the slice: the estimate stands again.
        self.assertEqual(PM.slice_figure(doc, "Saddle block", {"volume": 1001.0, "faces": 6}), (None, None))
        # Only the G-code's total (Bambu Studio, PrusaSlicer): said so.
        PM.remember_slice(doc, "Seat", stats, {"filamentG": 12.3}, {}, "prusaslicer")
        got, r = PM.slice_figure(doc, "Seat", stats)
        self.assertEqual(got, 12.3)
        self.assertIn("brim and supports included", PM.slice_words(r))
        self.assertIsNone(PM.remember_slice(doc, "Nothing", stats, {}, {}))


def phase_of(rows, name):
    return next(r for r in rows if r["name"] == name)


class TubeCutList(unittest.TestCase):
    def test_square_tee(self):
        rows, warn = TC.cut_list([
            {"name": "Main", "from": [0, 0, 0], "to": [400, 0, 0], "od": 50, "wall": 2},
            {"name": "Branch", "from": [200, 0, 0], "to": [200, 300, 0], "od": 25, "wall": 1.5}])
        self.assertEqual(warn, [])
        b = phase_of(rows, "Branch")
        trim = math.sqrt(25 ** 2 - 12.5 ** 2)  # the long points sit at the sides
        self.assertAlmostEqual(b["cutLength"], round(300 - trim, 1), delta=0.05)
        self.assertEqual((b["from"]["meets"], b["from"]["includedAngle"], b["from"]["notcherAngle"]), ("Main", 90.0, 0.0))
        self.assertAlmostEqual(b["from"]["copeDepth"], 25 - trim, delta=0.05)
        self.assertEqual(b["to"]["cut"], "square")
        self.assertNotIn("phase", b)
        self.assertEqual(phase_of(rows, "Main")["cutLength"], 400.0)

    def test_angled_cope(self):
        th = math.radians(60)
        rows, _ = TC.cut_list([
            {"name": "Down", "from": [0, 0, 0], "to": [500, 0, 0], "od": 38, "wall": 1.2},
            {"name": "Stay", "from": [100, 0, 0], "to": [100 + 400 * math.cos(th), 400 * math.sin(th), 0], "od": 19, "wall": 1.0}])
        s = phase_of(rows, "Stay")
        R, r = 19.0, 9.5
        t_short, t_long = (R - r * math.cos(th)) / math.sin(th), (R + r * math.cos(th)) / math.sin(th)
        self.assertEqual((s["from"]["includedAngle"], s["from"]["notcherAngle"]), (60.0, 30.0))
        self.assertAlmostEqual(s["cutLength"], 400 - t_short, delta=0.1)
        self.assertAlmostEqual(s["from"]["copeDepth"], t_long - t_short, delta=0.1)

    def test_phase_between_copes(self):
        # A rung between two rails, both along x: the copes line up (0°).
        # The same rung onto a rail along z at its far end: turned 90°.
        base = [{"name": "Rail A", "from": [-100, 0, 0], "to": [100, 0, 0], "od": 30, "wall": 2},
                {"name": "Rung", "from": [0, 0, 0], "to": [0, 300, 0], "od": 20, "wall": 1.5}]
        rows, _ = TC.cut_list(base + [{"name": "Rail B", "from": [-100, 300, 0], "to": [100, 300, 0], "od": 30, "wall": 2}])
        self.assertEqual(phase_of(rows, "Rung")["phase"], 0.0)
        rows, _ = TC.cut_list(base + [{"name": "Post", "from": [0, 300, -100], "to": [0, 300, 100], "od": 30, "wall": 2}])
        self.assertEqual(phase_of(rows, "Rung")["phase"], 90.0)
        self.assertAlmostEqual(phase_of(rows, "Rung")["cutLength"], 300 - 2 * math.sqrt(15 ** 2 - 10 ** 2), delta=0.1)

    def test_shared_node_and_ends(self):
        # Two tubes end at one node: the smaller is coped onto the larger.
        rows, _ = TC.cut_list([
            {"name": "Seat tube", "from": [0, 0, 0], "to": [0, 0, 500], "od": 28.6, "wall": 1.0},
            {"name": "Top tube", "from": [0, 0, 500], "to": [550, 0, 500], "od": 25.4, "wall": 0.9}])
        self.assertEqual(phase_of(rows, "Top tube")["from"]["meets"], "Seat tube")
        self.assertEqual(phase_of(rows, "Seat tube")["to"]["cut"], "square")
        rows, _ = TC.cut_list([
            {"name": "Seat tube", "from": [0, 0, 0], "to": [0, 0, 500], "od": 28.6, "wall": 1.0},
            {"name": "Top tube", "from": [0, 0, 500], "to": [550, 0, 500], "od": 25.4, "wall": 0.9, "ends": {"from": "square"}}])
        self.assertEqual(phase_of(rows, "Top tube")["cutLength"], 550.0)

    def test_files_and_refusals(self):
        rows, warn = TC.cut_list([
            {"name": "Main", "from": [0, 0, 0], "to": [400, 0, 0], "od": 50, "wall": 2},
            {"name": "Branch", "from": [200, 0, 0], "to": [200, 300, 0], "od": 25, "wall": 1.5}])
        md = TC.markdown(rows, "Frame", warn)
        self.assertIn("| Branch | 25 | 1.5 | 300 |", md)
        self.assertIn("cope on Main (OD 50) at 90° (notcher 0°)", md)
        back = list(csv.DictReader(io.StringIO(TC.csv_text(rows))))
        self.assertEqual(back[1]["from_meets"], "Main")
        self.assertEqual(back[1]["to_meets"], "square")
        self.assertEqual(float(back[1]["cut_length_mm"]), rows[1]["cutLength"])
        for bad, says in (([], "members"), ([{"name": "A", "from": [0, 0, 0], "to": [0, 0, 0], "od": 10, "wall": 1}], "same point"),
                          ([{"name": "A", "from": [0, 0, 0], "to": [1, 0, 0], "od": 10, "wall": 6}], "wall"),
                          ([{"name": "A", "from": [0, 0, 0], "to": [9, 0, 0], "od": 10, "wall": 1, "ends": {"to": "B"}}], "another tube")):
            with self.assertRaises(TC.CutError) as e:
                TC.cut_list(bad)
            self.assertIn(says, str(e.exception))

    def test_tool_writes_the_files(self):
        out = run(r'''
import os, tempfile, csv
from workshop_make.handlers import cut as C
class S:
    out_dir = tempfile.mkdtemp()
    def body(self, ref):
        raise C.ToolError("not_found", ref)
r = C.tube_cutlist(S(), {"members": [{"name": "Main", "from": [0, 0, 0], "to": [400, 0, 0], "od": 50, "wall": 2},
                                    {"name": "Branch", "from": [200, 0, 0], "to": [200, 300, 0], "od": 25, "wall": 1.5}], "name": "frame"})
OUT["stock"] = r["stock"]
OUT["files"] = [os.path.basename(p) for p in r["files"].values()]
OUT["exist"] = all(os.path.isfile(p) for p in r["files"].values())
try:
    C.tube_cutlist(S(), {})
except C.ToolError as e:
    OUT["refused"] = str(e)
''')
        self.assertEqual(out["files"], ["frame.md", "frame.csv"])
        self.assertTrue(out["exist"])
        self.assertEqual(out["stock"], {"50 x 2": 400.0, "25 x 1.5": 278.3})
        self.assertIn("members", out["refused"])


if __name__ == "__main__":
    unittest.main()
