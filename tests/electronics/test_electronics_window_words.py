# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 8 (17 Nov): what Workshop Electronics tells Agent Link's echo
# — pcb_order_package's words and the board it selects (07-018), and
# printed_channel's body made see-through (03-015). Plain Python: the
# handlers (which need FreeCAD) are stood in for.
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..")]


def _fam():
    had = sys.modules.get("workshop_electronics.handlers")
    if had is None:
        sys.modules["workshop_electronics.handlers"] = types.ModuleType("workshop_electronics.handlers")
    try:
        sys.modules.pop("workshop_electronics.fam_electronics", None)
        from workshop_electronics import fam_electronics
        return fam_electronics
    finally:
        if had is None:
            sys.modules.pop("workshop_electronics.handlers", None)


class WindowWords(unittest.TestCase):
    def setUp(self):
        self.f = _fam()

    def test_order_words_name_vendor_files_and_board(self):
        body = {"gerberZip": "/o/PCB_test_gerbers.zip", "package": "/o/PCB_test_order.zip", "orderSheet": "/o/PCB_test_ORDER.md",
                "vendor": "JLCPCB", "board": {"size": [50.0, 30.0], "layers": 2, "thickness": 1.6},
                "files": {"gerbers": 3, "drill": 1, "bom": 1, "cpl": 1, "other": 0}}
        w = self.f.WORDS("pcb_order_package", {}, body)
        self.assertEqual(w, "Packed the PCB order for JLCPCB: PCB_test_order.zip (3 Gerbers, 1 drill file, 1 BOM, 1 placement), "
                            "board 50 x 30 mm, 2 layers")
        self.assertNotIn("/o/", w)
        self.assertIsNone(self.f.WORDS("printed_channel", {}, body))
        self.assertIsNone(self.f.WORDS("pcb_order_package", {}, {"error": "x"}))

    def test_order_selects_its_board(self):
        self.assertEqual(self.f.SELECTS_FOR("pcb_order_package", {"board": "PCB test"}, {}, None), ["PCB test"])
        self.assertIsNone(self.f.SELECTS_FOR("pcb_order_package", {}, {}, None))
        self.assertIsNone(self.f.SELECTS_FOR("kicad_import", {"board": "PCB test"}, {}, None))

    def test_channel_body_is_see_through(self):
        self.assertEqual(self.f.SEE_THROUGH, {"printed_channel": "body"})


if __name__ == "__main__":
    unittest.main()
