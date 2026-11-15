# SPDX-License-Identifier: LGPL-2.1-or-later
# Each add-on folder's FILES lists its files, so the Claude extension's
# launcher can fetch them as plain files. A file added or removed without
# FILES following fails here. Regenerate them with
#   for d in Parts Make Electronics Documents; do (cd $d && git ls-files | grep -v -E '(^|/)__pycache__/|^FILES$|^\.' | sort > FILES); done
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = [d for d in sorted(os.listdir(ROOT)) if os.path.isfile(os.path.join(ROOT, d, "package.xml"))]


class Files(unittest.TestCase):
    def test_each_addon_lists_its_files(self):
        self.assertTrue(ADDONS)
        for d in ADDONS:
            try:
                out = subprocess.run(["git", "ls-files"], cwd=os.path.join(ROOT, d), capture_output=True, text=True, check=True).stdout
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("not a git checkout")
            tracked = sorted(p for p in out.splitlines() if p != "FILES" and "__pycache__/" not in p and not p.startswith("."))
            with open(os.path.join(ROOT, d, "FILES"), encoding="utf-8") as f:
                listed = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
            self.assertEqual(listed, tracked, f"{d}/FILES is stale: regenerate it (see the top of this test)")
