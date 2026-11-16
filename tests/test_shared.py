# SPDX-License-Identifier: LGPL-2.1-or-later
# The helper files Agent Link vendors into its add-ons (Agent Link's
# scripts/sync_shared.py lists them) have one copy here, equal to Agent
# Link's but for the first (licence) line; the old per-part module names are
# aliases of that one copy, not copies. Agent Link is looked for beside this
# repository (or at $AGENTLINK_DIR / $AGENTLINK_SRC); without it the drift
# check is skipped. Fix drift with Agent Link's
#   python3 scripts/sync_shared.py <this repository>
import ast
import importlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# Shared file -> its old names in the parts (aliases now).
ALIASES = {
    "layout": ("workshop_make", "workshop_documents", "safetynet"),
    "tooldata": ("workshop_make", "workshop_documents", "workshop_electronics"),
}


def agentlink():
    for d in (os.environ.get("AGENTLINK_DIR"), os.environ.get("AGENTLINK_SRC"),
              os.path.join(os.path.dirname(ROOT), "agentlink-freecad"), os.path.join(os.path.dirname(ROOT), "AgentLink-FreeCAD"),
              os.path.join(ROOT, "agentlink-addon")):
        if d and os.path.isfile(os.path.join(d, "scripts", "sync_shared.py")):
            return d
    return None


def shared_list(al):
    """Agent Link's SHARED: {its file: the line every copy carries}."""
    tree = ast.parse(open(os.path.join(al, "scripts", "sync_shared.py"), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "SHARED" for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError("no SHARED in sync_shared.py")


def body(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n", 1)[1]


def copies(name, mark):
    out = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in {".git", "__pycache__", "tests", "build", "dist", "agentlink-addon", "orcalink-addon"}]
        for f in files:
            if f == name:
                p = os.path.join(d, f)
                if mark in open(p, encoding="utf-8").read():
                    out.append(p)
    return out


class Shared(unittest.TestCase):
    def test_vendored_files_match_agent_link(self):
        al = agentlink()
        if al is None:
            self.skipTest("Agent Link is not checked out beside this repository")
        shared = shared_list(al)
        self.assertTrue(shared)
        for name, mark in shared.items():
            found = copies(os.path.basename(name), mark)
            self.assertEqual(len(found), 1, f"one copy of {name} in the add-on, found {found}")
            self.assertEqual(body(found[0]), body(os.path.join(al, name)),
                             f"{os.path.relpath(found[0], ROOT)} differs from Agent Link's {name}: run Agent Link's scripts/sync_shared.py on this repository")

    def test_the_one_copy_is_workshops(self):
        self.assertIn("This file is the same in every add-on but for its first line", open(os.path.join(ROOT, "workshop", "layout.py"), encoding="utf-8").read())

    def test_old_names_are_the_same_module(self):
        for name, parts in ALIASES.items():
            one = importlib.import_module(f"workshop.{name}")
            for p in parts:
                path = os.path.join(ROOT, p, name + ".py")
                self.assertLess(len(open(path, encoding="utf-8").read().splitlines()), 10, f"{p}/{name}.py is a copy, not an alias")
                self.assertIs(importlib.import_module(f"{p}.{name}"), one, f"{p}.{name}")


if __name__ == "__main__":
    unittest.main()
