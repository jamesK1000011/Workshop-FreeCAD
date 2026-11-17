# SPDX-License-Identifier: LGPL-2.1-or-later
# The words Agent Link's Activity tab and caption give Make's heavy reads
# (fam_make, fam_slicing, fam_frame PHRASES), filled by Agent Link's own
# template code when its checkout is at hand ($AGENTLINK_DIR, or beside this
# repository). Window review round 3: dfm_check, part_review, slice,
# slice_with and fea_frame kept an earlier call's caption. Also dfm_check's
# verdict words.
import ast
import os
import subprocess
import sys
import unittest

from _stubs import run

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def hub():
    for d in (os.environ.get("AGENTLINK_DIR"), os.environ.get("AGENTLINK_SRC"),
              os.path.join(os.path.dirname(ROOT), "agentlink-freecad"), os.path.join(os.path.dirname(ROOT), "AgentLink-FreeCAD")):
        if d and os.path.isfile(os.path.join(d, "agentlink", "activity.py")):
            return d
    return None


def declared(path, name):
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name:
            return ast.literal_eval(n.value)
    return None


FAMS = ("workshop_make/fam_make.py", "workshop_make/fam_slicing.py", "workshop_make/fam_frame.py")


class Words(unittest.TestCase):
    def test_every_stale_read_has_words(self):
        got = {}
        for p in FAMS:
            got.update(declared(p, "PHRASES") or {})
        self.assertTrue({"dfm_check", "part_review", "slice", "slice_with", "fea_frame"} <= set(got))
        sel = {**(declared(FAMS[0], "SELECTS") or {}), **(declared(FAMS[1], "SELECTS") or {})}
        self.assertEqual(sel, {"dfm_check": "body", "part_review": "body", "slice": "body", "slice_with": "body"})
        self.assertEqual(declared(FAMS[2], "SELECTS"), {"fea_frame": "bodies"})
        # A job's first answer has words of its own (not the earlier call's).
        for name in ("dfm_check", "part_review", "slice", "slice_with", "fea_frame"):
            self.assertTrue(any(t.endswith(" if {job}") for t in got[name]), name)

    @unittest.skipUnless(hub(), "Agent Link's checkout is not at hand")
    def test_filled_by_agent_links_templates(self):
        phrases = {}
        for p in FAMS:
            phrases.update(declared(p, "PHRASES") or {})
        code = r"""
import json, sys, types
from agentlink import activity
f = types.SimpleNamespace(PHRASES=json.loads(sys.argv[1]))
activity.declare(f)
rows = [("dfm_check", {"body": "Bracket"}, {"body": "Bracket", "verdict": "printable, 2 warnings"}),
        ("part_review", {"body": "Bracket"}, {"body": "Bracket", "verdict": "pass"}),
        ("slice", {"body": "Bracket"}, {"body": "Bracket", "slicer": "prusa-slicer", "gcode": "/out/Bracket.gcode", "time": "12m 3s", "filamentG": 3.21}),
        ("slice", {"body": "Bracket"}, {"body": "Bracket", "slicer": "prusa-slicer", "gcode": "/out/Bracket.gcode"}),
        ("slice_with", {"body": "Bracket", "slicer": "orcaslicer", "project": True},
         {"body": "Bracket", "slicer": "orcaslicer", "project": "/out/b.3mf", "time": "1h 2m", "filamentG": 12.5}),
        ("slice_with", {"body": "Bracket"}, {"body": "Bracket", "slicer": "bambustudio", "time": "9m", "filamentG": 2}),
        ("fea_frame", {}, {"loadTotalN": 500, "worst": "Rafter"}),
        ("fea_frame", {}, {"loadTotalN": 500, "worst": None}),
        ("dfm_check", {"body": "Bracket"}, {"job": "job-1", "tool": "dfm_check", "status": "running"}),
        ("slice_with", {"body": "Bracket", "slicer": "orcaslicer"}, {"job": "job-2", "tool": "slice_with", "status": "running"}),
        ("slice", {"body": "Bracket"}, {"body": "Bracket", "slicer": "prusa-slicer", "gcode": "/out/Bracket.gcode", "verdict": "G-code written"}),
        ("fea_frame", {"bodies": ["Rafter", "Post"]}, {"loadTotalN": [0, 0, -500], "loadN": 500, "verdict": "least safety 2.4, Rafter",
                                                      "bodies": ["Rafter", "Post"]}),
        ("fea_frame", {}, {"loadTotalN": [0, 0, -500], "loadN": 500, "verdict": "least safety 2.4, M1"}),
        ("fea_frame", {}, {"loadTotalN": [0, 0, -10000], "loadN": 10000, "verdict": "at most 15.1 MPa, no yield to judge",
                           "deflectionMaxMm": 0.156})]
print(json.dumps([activity.did(n, a, b) for n, a, b in rows]))
"""
        import json

        env = dict(os.environ, PYTHONPATH=hub())
        r = subprocess.run([sys.executable, "-c", code, json.dumps(phrases)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [
            "Checked Bracket for printing: printable, 2 warnings", "Reviewed Bracket: pass",
            "Sliced Bracket with prusa-slicer: 12m 3s, 3.21 g", "Sliced Bracket with prusa-slicer: Bracket.gcode",
            "Sliced Bracket with orcaslicer into a project and G-code: 1h 2m, 12.5 g", "Sliced Bracket with bambustudio: 9m, 2 g",
            "Solved the frame under 500 N: least safe member Rafter", "Solved the frame under 500 N",
            "Checking Bracket for printing in the background", "Slicing Bracket with orcaslicer in the background",
            "Sliced Bracket with prusa-slicer: G-code written", "Solved the frame of Rafter and Post under 500 N: least safety 2.4, Rafter",
            "Solved the frame under 500 N: least safety 2.4, M1",
            "Solved the frame under 10000 N: at most 15.1 MPa, no yield to judge; sags 0.156 mm"])


class Verdict(unittest.TestCase):
    def test_dfm_verdict(self):
        out = run(r"""
from workshop_make import api
OUT["v"] = [api.dfm_verdict([]), api.dfm_verdict([{"severity": "warning"}, {"severity": "warning"}, {"severity": "info"}]),
            api.dfm_verdict([{"severity": "error"}, {"severity": "warning"}]),
            api.dfm_verdict([{"severity": "error", "waived": True}, {"severity": "error"}, {"severity": "error"}])]
""")
        self.assertEqual(out["v"], ["printable", "printable, 2 warnings", "not printable: 1 problem, 1 warning", "not printable: 2 problems"])

    def test_slice_and_frame_verdicts(self):
        out = run(r"""
from workshop_make import api
OUT["s"] = [api.slice_verdict({"time": "12m 3s", "filamentG": 3.21}), api.slice_verdict({"time": "9m", "filamentG": None}),
            api.slice_verdict({"filamentG": 2.0}), api.slice_verdict({})]
OUT["f"] = [api.frame_verdict([{"member": "Rafter", "safety": 2.4}, {"member": "Post", "safety": 5.0}]),
            api.frame_verdict([{"member": "Post", "safety": 0.8}]),
            api.frame_verdict([{"member": "M1", "vonMisesMPa": 12.53}]), api.frame_verdict([])]
""")
        self.assertEqual(out["s"], ["12m 3s, 3.21 g", "9m", "2 g", "G-code written"])
        self.assertEqual(out["f"], ["least safety 2.4, Rafter", "past yield: safety 0.8, Post", "at most 12.5 MPa, no yield to judge", "solved"])
        for v in out["s"] + out["f"]:
            self.assertLessEqual(len(v), 40)   # Agent Link reads a verdict of at most 40 characters as the result


if __name__ == "__main__":
    unittest.main()


class FrameMarks(unittest.TestCase):
    def test_members_supports_and_sag_for_the_window(self):
        # Round 7, make 04-085: the frame is only in the deck, so the view
        # kept the last bodies; the answer's sceneMarks are what Agent Link's
        # echo draws and frames.
        out = run(r"""
from workshop_make.handlers import frame
OUT["m"] = frame.scene_marks([{"name": "Beam", "from": [0, 0, 0], "to": [1000, 0, 0]}],
                             [{"member": "Beam", "deflectionMm": 0.156}],
                             [{"at": [0, 0, 0], "kind": "pinned"}, {"at": [1000, 0, 0], "kind": "roller"}, {"at": [1, 2]}])
""")
        m = out["m"]
        self.assertEqual(m["lines"], [[[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]]])
        self.assertEqual(m["points"], [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]])
        self.assertEqual(m["labels"], [[[500.0, 0.0, 0.0], "Beam: sags 0.156 mm"]])
