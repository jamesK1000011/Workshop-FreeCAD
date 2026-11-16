# SPDX-License-Identifier: LGPL-2.1-or-later
# FILES lists the add-on's files, so the Claude extension's launcher can
# fetch them as plain files. A file added or removed without FILES following
# fails here. Regenerate it with
#   git ls-files | grep -v -E '(^|/)__pycache__/|^FILES$|^\.' | sort > FILES
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Files(unittest.TestCase):
    def test_lists_its_files(self):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        tracked = sorted(p for p in out.splitlines() if p != "FILES" and "__pycache__/" not in p and not p.startswith("."))
        with open(os.path.join(ROOT, "FILES"), encoding="utf-8") as f:
            listed = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
        self.assertEqual(listed, tracked, "FILES is stale: regenerate it (see the top of this test)")

    def test_no_old_addon_folders(self):
        # One add-on since the combine: no folder of the old layout left.
        for d in ("Parts", "Make", "Electronics", "Documents"):
            self.assertFalse(os.path.isdir(os.path.join(ROOT, d)), d)


if __name__ == "__main__":
    unittest.main()
