# SPDX-License-Identifier: LGPL-2.1-or-later
# What a person reads in Documents' GUI, under stand-ins for FreeCAD and Qt:
# task panels that start on the tools' own defaults with their choices
# capitalised (the tools still get their values), Title Case titles,
# refusals without the agent's tool syntax, Report-view lines without raw
# dicts, and a second task refused while one is open.
import unittest

from _stubs import run


class Panels(unittest.TestCase):
    def test_defaults_and_shown_text(self):
        out = run(r'''
from workshop_documents import taskpanels as T
OUT["drawing"] = T.FormPanel("drawing", runner=lambda t, a: (True, {})).values()
OUT["exploded"] = T.FormPanel("exploded", runner=lambda t, a: (True, {})).values()
OUT["args"] = T.args_of("drawing", OUT["drawing"])
OUT["titles"] = [v[0] for v in T.PANELS.values()]
OUT["shown"] = [T.shown(v) for v in ("first", "A4", "MIT")]
''')
        self.assertEqual((out["drawing"]["projection"], out["drawing"]["paper"]), ("first", "auto"))
        self.assertEqual(out["exploded"]["direction"], "up")
        self.assertNotIn("scale", out["args"][1])
        self.assertEqual(out["titles"], ["Drawing", "Exploded Drawing", "Library Pack", "Patent Draft"])
        self.assertEqual(out["shown"], ["First angle (ISO)", "A4", "MIT"])

    def test_a_second_task_is_refused(self):
        out = run(r'''
told, shown = [], []
class Box:
    @staticmethod
    def information(parent, title, text): told.append([title, text])
sys.modules["PySide.QtGui"].QMessageBox = Box
Gui.Control = types.SimpleNamespace(activeDialog=lambda: object(), showDialog=shown.append, closeDialog=lambda: None)
from workshop_documents import taskpanels as T
OUT["got"] = T.show("drawing", runner=lambda t, a: (True, {}))
OUT["told"], OUT["shown"] = told, len(shown)
''')
        self.assertIsNone(out["got"])
        self.assertEqual(out["told"], [["Workshop Documents", "Finish or cancel the open task first."]])
        self.assertEqual(out["shown"], 0)


class Report(unittest.TestCase):
    def test_person_words_and_one_line(self):
        out = run(r'''
from workshop_documents import commands as C
OUT["err"] = C.person_error({"error": {"message": "no parts to draw — gen_part makes one"}})
OUT["line"] = C.sentence("drawing_make", "Drawing", {"paper": "A4", "scale": "1:2", "files": {"svg": "/o/a.svg", "pdf": "/o/a.pdf"}, "titleBlock": {"title": "Box"}, "techdrawPage": "Box drawing"})
OUT["other"] = C.sentence("bogus", "Drawing", {"paper": "A4"})
''')
        self.assertEqual(out["err"], "No parts to draw.")
        self.assertEqual(out["line"], "Workshop: Drawing of Box on A4 at 1:2: the TechDraw page Box drawing (edit it in TechDraw); files a.svg, a.pdf.")
        self.assertEqual(out["other"], "Workshop: Drawing done.")


if __name__ == "__main__":
    unittest.main()
