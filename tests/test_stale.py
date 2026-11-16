# SPDX-License-Identifier: LGPL-2.1-or-later
# Old WorkshopParts/Make/Electronics/Documents or SafetyNet Mod folders left
# beside the one add-on (an install by an older launcher): Workshop's own
# packages still win on the path, the old folders are said in one line and
# never touched, and an old folder's InitGui.py does nothing instead of
# failing. Run in a fresh Python per case, as FreeCAD starts.
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CASE = r"""
import json, os, sys, types
mod, said = sys.argv[1], []
# FreeCAD's order: every Mod folder on the path, the old ones first.
sys.path[:0] = [os.path.join(mod, d) for d in sorted(os.listdir(mod))]
import importlib, importlib.util
from workshop import stale
old = stale.prefer_own(warn=said.append)
stale.prefer_own(warn=said.append)  # said once
import safetynet, workshop_make
out = {"old": old, "said": said, "first": sys.path[0],
       "safetynet": safetynet.__file__, "make": workshop_make.__file__,
       "families": importlib.util.find_spec("safetynet.families") is not None}
# An old folder's InitGui.py, as it was: does nothing now.
from safetynet import workbench as w1
from workshop_parts import workbench as w2
out["initgui"] = [w1.add(None), w2.add(None)]
print(json.dumps(out))
"""


def make_mod(old):
    mod = tempfile.mkdtemp()
    os.symlink(ROOT, os.path.join(mod, "Workshop"))
    for d, name, pkg in old:
        os.makedirs(os.path.join(mod, d, pkg))
        open(os.path.join(mod, d, pkg, "__init__.py"), "w").write("OLD = True\n")
        open(os.path.join(mod, d, "package.xml"), "w").write(f"<package format=\"1\"><name>{name}</name></package>\n")
    return mod


def run(mod):
    r = subprocess.run([sys.executable, "-I", "-c", CASE, mod], capture_output=True, text=True,
                       env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"})
    if r.returncode:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Stale(unittest.TestCase):
    def test_old_folders_said_once_and_ours_win(self):
        mod = make_mod([("SafetyNet", "SafetyNet", "safetynet"), ("WorkshopMake", "Workshop Make", "workshop_make"),
                        ("WorkshopParts", "Someone else's parts", "workshop_parts")])
        try:
            out = run(mod)
            self.assertEqual(out["old"], ["WorkshopMake", "SafetyNet"])
            self.assertEqual(len(out["said"]), 1, out["said"])
            self.assertIn("WorkshopMake, SafetyNet", out["said"][0])
            self.assertIn("agentlink_update", out["said"][0])
            self.assertEqual(os.path.realpath(out["first"]), os.path.realpath(ROOT))
            for k in ("safetynet", "make"):
                self.assertTrue(os.path.realpath(out[k]).startswith(os.path.realpath(ROOT) + os.sep), out[k])
            self.assertTrue(out["families"])
            self.assertEqual(out["initgui"], [None, None])
            # Never touched.
            for d in ("SafetyNet", "WorkshopMake", "WorkshopParts"):
                self.assertTrue(os.path.isfile(os.path.join(mod, d, "package.xml")), d)
        finally:
            shutil.rmtree(mod)

    def test_nothing_said_without_old_folders(self):
        mod = make_mod([])
        try:
            out = run(mod)
            self.assertEqual((out["old"], out["said"]), ([], []))
        finally:
            shutil.rmtree(mod)


if __name__ == "__main__":
    unittest.main()
