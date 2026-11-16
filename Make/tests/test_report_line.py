# SPDX-License-Identifier: LGPL-2.1-or-later
# The Report view's line: a sentence a person reads, with units, never the
# tool's fields (those stay in the answer, for agents).
import unittest

from _stubs import run


class Sentences(unittest.TestCase):
    def test_each_command_reads_as_a_sentence(self):
        out = run(r'''
from workshop_make import results as R
none = "none, so holes are assumed to print 0.2 mm small"
OUT["hole"] = R.sentence("hw_hole", "Hole for Hardware", {"body": "Body", "kind": "clearance", "size": "M3", "printerFit": none, "allowance": 0.2,
    "depth": "through", "through": 20.0, "removed": 203.58, "route": "PartDesign Hole", "features": ["HoleSketch", "Hole"], "sound": True})
OUT["part"] = R.sentence("hw_hole", "Hole for Hardware", {"body": "Plate", "kind": "magnet", "size": "6x2", "printerFit": "calibrated", "allowance": 0.15,
    "depth": 2.2, "route": "Part solid", "sound": True})
OUT["fit"] = R.sentence("fit", "Fit Size", {"of": "hole", "nominal": 5.0, "model": {"slide": 5.4}, "printerFit": none})
OUT["cal"] = R.sentence("fit", "Calibrate", {"calibration": {"hole": 0.15, "shaft": 0.05}})
OUT["setup"] = R.sentence("setup", "New Setup", {"added": {"id": "S1", "name": "Print", "bodies": ["Box", "Lid"]}, "setups": 1})
OUT["thread"] = R.sentence("thread_lookup", "Thread Lookup", {"thread": {"size": "M6", "major": 6.0, "pitch": 1.0, "tapDrill": 5.0, "insert": {"hole": 8.0}}})
OUT["send"] = R.sentence("printer_send", "Send", {"uploaded": "a.gcode", "printer": "Mk4", "started": False})
OUT["other"] = R.sentence("unknown_tool", "Something", {"body": "X", "a": 1})
OUT["dfm"] = R.sentence("dfm_check", "DFM Check", {"body": "Box", "findings": [], "wall": {"least": 1.2}})
''')
        self.assertEqual(out["hole"], "Workshop: M3 clearance hole in Body, through 20 mm (FreeCAD Hole, editable in Part Design). "
                                      "Printer calibration: none, so 0.2 mm added.")
        self.assertEqual(out["part"], "Workshop: 6 × 2 mm magnet pocket in Plate, 2.2 mm deep (cut as a shape: a plain Part solid, not in a Part Design Body). "
                                      "Printer calibration: the one kept with this document, 0.15 mm added.")
        self.assertEqual(out["fit"], "Workshop: For a 5 mm part, model the hole at: slide 5.4 mm. Printer calibration: none, so the typical 0.2 mm added.")
        self.assertEqual(out["cal"], "Workshop: Printer calibration kept: holes print 0.15 mm small, pegs 0.05 mm big.")
        self.assertEqual(out["setup"], "Workshop: Setup Print made with Box and Lid.")
        self.assertEqual(out["thread"], "Workshop: M6: major 6 mm, pitch 1 mm, tap drill 5 mm, heat-set insert hole 8 mm (FreeCAD's thread tables).")
        self.assertEqual(out["send"], "Workshop: a.gcode uploaded to Mk4; not started (starting it is up to you).")
        self.assertEqual(out["other"], "Workshop: Something done.")
        self.assertEqual(out["dfm"], "Workshop: Box is printable. DFM check: no problems, no warnings.")
        for k, v in out.items():
            self.assertNotIn(";  ", v)
            self.assertNotRegex(v, r"\b(route|removed|features|printerFit|sound) ", k)


if __name__ == "__main__":
    unittest.main()
