# SPDX-License-Identifier: LGPL-2.1-or-later
# gen_make and gen_part in the window's words (fam_parts PHRASES, filled by
# Agent Link's own template code when its checkout is at hand). Window
# review round 4: 4001 (gen_make) and 4007 (gen_part) showed no new part;
# they are the model's measure: true calls (calls 1 and 7 of
# docs/hardening/workshop-parts-model.json), which build the part only to
# answer its sizes. Their words now say "nothing made".
import ast
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def hub():
    for d in (os.environ.get("AGENTLINK_DIR"), os.environ.get("AGENTLINK_SRC"),
              os.path.join(os.path.dirname(ROOT), "agentlink-freecad"), os.path.join(os.path.dirname(ROOT), "AgentLink-FreeCAD")):
        if d and os.path.isfile(os.path.join(d, "agentlink", "activity.py")):
            return d
    return None


def declared(name):
    tree = ast.parse(open(os.path.join(ROOT, "workshop_parts", "fam_parts.py"), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name:
            return ast.literal_eval(n.value)
    return None


STUBS = r"""
import json, sys, types
class Lax(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return type(k, (), {})
for n in ("FreeCAD", "Part", "FreeCADGui"):
    sys.modules[n] = Lax(n)
sys.path.insert(0, sys.argv[1])
from workshop_parts import api
print(json.dumps([api.measured_words([{"size": [83.5, 41.5, 32.4]}]), api.measured_words([{"size": [80, 60, 30]}, {"size": [80, 60, 5]}]),
                  api.measured_words([]), api.KIND_WORDS["gridfinity_baseplate"]]))
"""


class Words(unittest.TestCase):
    def test_measured_in_words(self):
        r = subprocess.run([sys.executable, "-I", "-c", STUBS, ROOT], capture_output=True, text=True)
        if r.returncode:
            self.skipTest("workshop_parts.api needs more of FreeCAD than the stand-ins give: " + r.stderr[-300:])
        self.assertEqual(json.loads(r.stdout), ["83.5 x 41.5 x 32.4 mm", "80 x 60 x 30 mm, and a lid", "", "Gridfinity baseplate"])

    def test_declared(self):
        p = declared("PHRASES")
        self.assertEqual(set(p), {"gen_make", "gen_part"})
        self.assertTrue(all(t[0].endswith(" if {measure}") for t in p.values()))
        self.assertEqual(declared("OUT_MORE"), {"gen_make": ("bodies",), "gen_part": ("bodies",)})

    @unittest.skipUnless(hub(), "Agent Link's checkout is not at hand")
    def test_filled_by_agent_links_templates(self):
        code = r"""
import json, sys, types
from agentlink import activity
activity.declare(types.SimpleNamespace(PHRASES=json.loads(sys.argv[1])))
rows = [("gen_make", {"measure": True}, {"generator": "gridfinity_bin", "kind": "Gridfinity bin", "measured": "83.5 x 41.5 x 32.4 mm", "made": False}),
        ("gen_make", {"name": "Bin"}, {"generator": "gridfinity_bin", "kind": "Gridfinity bin", "measured": "83.5 x 41.5 x 32.4 mm", "bodies": ["Bin"]}),
        ("gen_part", {"generator": "gridfinity_baseplate", "measure": True}, {"kind": "Gridfinity baseplate", "measured": "84 x 84 x 4.65 mm", "made": False}),
        ("gen_part", {"generator": "project_box", "name": "Box"}, {"kind": "project box", "measured": "80 x 60 x 30 mm, and a lid", "bodies": ["Box", "Box lid"]})]
print(json.dumps([activity.did(n, a, b) for n, a, b in rows]))
"""
        env = dict(os.environ, PYTHONPATH=hub())
        r = subprocess.run([sys.executable, "-c", code, json.dumps(declared("PHRASES"))], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), [
            "Measured a Gridfinity bin, 83.5 x 41.5 x 32.4 mm: nothing made", "Made Bin, a Gridfinity bin of 83.5 x 41.5 x 32.4 mm",
            "Measured a Gridfinity baseplate, 84 x 84 x 4.65 mm: nothing made",
            "Made Box and Box lid, a project box of 80 x 60 x 30 mm, and a lid"])


if __name__ == "__main__":
    unittest.main()
