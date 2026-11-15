# SPDX-License-Identifier: LGPL-2.1-or-later
# Documents with no agent: its data files, its API in a fresh Python (no
# Agent Link imported), the tool definitions, and a view projected.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [ROOT, os.path.join(ROOT, "..", "Common")]
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False

from workshop_documents import datafiles as data  # noqa: E402

DATA = os.path.join(ROOT, "workshop_documents", "data")


class Data(unittest.TestCase):
    def test_every_file_checks(self):
        self.assertEqual(data.check_folder(DATA), [])

    def test_tool_definitions(self):
        with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
            tools = json.load(f)["entries"]
        self.assertEqual(sorted(tools), ["drawing_exploded", "drawing_make", "library_pack", "patent_draft", "patent_figures"])
        self.assertEqual({v["group"] for v in tools.values()}, {"drawing", "share"})

    def test_library_pack_papers(self):
        from workshop_documents import api

        self.assertIn("CC-BY-4.0", api.LICENSES)
        self.assertIn("MIT License", api.license_text("MIT", "A. Maker", "Bins"))


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Api(unittest.TestCase):
    def test_no_agent_link_needed(self):
        code = ("import sys; sys.path[:0] = %r; import FreeCAD; from workshop_documents import api; api.views(); "
                "print(sorted(m for m in sys.modules if m.split('.')[0] == 'agentlink'))") % (sys.path[:],)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "[]")

    def test_project_a_box(self):
        import Part

        from workshop_documents import api

        self.assertIn("front", api.views())
        got = api.project([Part.makeBox(30, 20, 10)], "front")
        self.assertTrue(got)
        with self.assertRaises(Exception):
            api.project([Part.makeBox(1, 1, 1)], "sideways")


if __name__ == "__main__":
    unittest.main()
