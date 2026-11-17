# SPDX-License-Identifier: LGPL-2.1-or-later
# Window round 8 (17 Nov): drawing_exploded's words in Agent Link's window
# (fam_drawing.WORDS). Read from the module's source so no FreeCAD or Agent
# Link is needed here.
import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "workshop_documents", "fam_drawing.py")


def _words():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "WORDS")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), SRC, "exec"), ns)
    return ns["WORDS"]


class ExplodedWords(unittest.TestCase):
    def test_counts_and_page(self):
        body = {"manual": "/o/tutorial_assembly.md", "steps": [{"step": 1}, {"step": 2}], "bom": [{"item": 1}, {"item": 2}],
                "explode": 51.9, "route": "Workshop's own exploded shapes", "page": "Tutorial assembly steps"}
        w = _words()("drawing_exploded", {"title": "Tutorial assembly"}, body)
        self.assertEqual(w, "Drew the manual of Tutorial assembly: 2 steps, 2 BOM items, parts lifted 51.9 mm; "
                            "page Tutorial assembly steps shows step 2")
        self.assertNotIn("/o/", w)

    def test_assembly_route_and_others(self):
        W = _words()
        got = W("drawing_exploded", {"name": "box"}, {"steps": [{"step": 1}], "bom": [{}], "explodedView": "box exploded"})
        self.assertEqual(got, "Drew the manual of box: 1 step, 1 BOM item; Assembly view box exploded")
        self.assertIsNone(W("drawing_make", {}, {"steps": []}))
        self.assertIsNone(W("drawing_exploded", {}, {"error": "x"}))


if __name__ == "__main__":
    unittest.main()
