# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics with no agent: its data files, its API in a fresh Python (no
# Agent Link imported), the tool definitions every handler binds to, and a
# board read into a document.
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, ROOT]
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD

    HAVE = True
except ImportError:
    HAVE = False

from workshop_electronics import datafiles as data  # noqa: E402

DATA = os.path.join(ROOT, "workshop_electronics", "data")


class Data(unittest.TestCase):
    def test_every_file_checks(self):
        self.assertEqual(data.check_folder(DATA), [])

    def test_vendors(self):
        from workshop_electronics import pcb

        v = pcb.vendors()
        self.assertEqual(sorted(v), ["jlcpcb", "oshpark", "pcbway"])
        self.assertEqual(v["oshpark"]["quantity"], 3)

    def test_tool_definitions(self):
        with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
            tools = json.load(f)["entries"]
        self.assertEqual(sorted(tools), ["board_enclosure", "kicad_import", "pcb_order_package", "printed_channel"])
        self.assertEqual({v["group"] for v in tools.values()}, {"electronics"})


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Api(unittest.TestCase):
    def test_no_agent_link_needed(self):
        code = ("import sys; sys.path[:0] = %r; import FreeCAD; from workshop_electronics import api; "
                "print(sorted(m for m in sys.modules if m.split('.')[0] == 'agentlink'))") % (sys.path[:],)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "[]")

    def test_board_into_a_document(self):
        from test_electronics import BOARD
        from workshop_electronics import api

        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.kicad_pcb")
        with open(p, "w") as f:
            f.write(BOARD)
        doc = FreeCAD.newDocument("el_api")
        try:
            o = api.add_board(doc, api.read_board(p))
            self.assertEqual(o.Label, "Test board")
            bb = o.Shape.BoundBox
            self.assertAlmostEqual(bb.XLength, 50, places=2)
            self.assertAlmostEqual(bb.ZLength, 1.6, places=3)
            # Two M3 holes and one 2.2 mm: three holes through.
            self.assertLess(o.Shape.Volume, 50 * 30 * 1.6)
        finally:
            FreeCAD.closeDocument(doc.Name)
        with self.assertRaises(Exception):
            api.read_board("/no/such.kicad_pcb")


if __name__ == "__main__":
    unittest.main()
