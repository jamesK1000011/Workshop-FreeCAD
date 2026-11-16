# SPDX-License-Identifier: LGPL-2.1-or-later
# The Tutor's lessons Workshop ships (workshop/lessons/, the lessons/ folder
# beside the agentlink_families module, where the Tutor looks): each parses
# as JSON, its id starts with the package (the Tutor refuses one that does
# not), and every tool it calls is a Workshop tool or, when an Agent Link
# checkout is at hand ($AGENTLINK_DIR / $AGENTLINK_SRC, as in CI's run with
# Agent Link), one of Agent Link's; every Workshop command it names exists.
import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "workshop", "lessons")
SUFFIX = ".lesson.json"
TOOL = re.compile(r'\bTool\(\s*"([a-z][a-z0-9_]*)"')


def lessons():
    return sorted(glob.glob(os.path.join(FOLDER, "*" + SUFFIX)))


def _py_names(folders):
    out = set()
    for top in folders:
        for d, _, files in os.walk(top):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(d, f), encoding="utf-8") as fh:
                        out |= set(TOOL.findall(fh.read()))
    return out


def workshop_tools():
    """Workshop's tool names: its tool data and the Tool(...) it builds."""
    out = set()
    for p in glob.glob(os.path.join(ROOT, "*", "data", "tools.json")):
        with open(p, encoding="utf-8") as f:
            out |= set(json.load(f).get("entries", {}))
    pkgs = [os.path.join(ROOT, d) for d in os.listdir(ROOT)
            if os.path.isfile(os.path.join(ROOT, d, "__init__.py"))]
    return out | _py_names(pkgs)


def agentlink_tools():
    """Agent Link's tool names, read from a checkout's source, else None."""
    for d in (os.environ.get("AGENTLINK_DIR"), os.environ.get("AGENTLINK_SRC"),
              os.path.join(ROOT, "agentlink-addon")):
        pkg = os.path.join(d or "", "agentlink")
        if d and os.path.isfile(os.path.join(pkg, "tools.py")):
            out = _py_names([pkg])
            data = os.path.join(pkg, "data", "tools.json")
            if os.path.isfile(data):
                with open(data, encoding="utf-8") as f:
                    out |= set(json.load(f).get("entries", {}))
            return out
    return None


def workshop_commands():
    """Every string in Workshop's code that could be a command name."""
    out = set()
    for p in glob.glob(os.path.join(ROOT, "*", "**", "*.py"), recursive=True):
        if os.sep + "tests" + os.sep in p:
            continue
        with open(p, encoding="utf-8") as f:
            out |= set(re.findall(r'"(Workshop_[A-Za-z0-9_]+)"', f.read()))
    return out


def walk(x, calls, cmds):
    """The tool calls ({tool, args}) and command names in a lesson."""
    if isinstance(x, dict):
        if isinstance(x.get("tool"), str) and "args" in x:
            calls.append(x["tool"])
            if x["tool"] == "cmd_run" and isinstance((x.get("args") or {}).get("name"), str):
                cmds.append(x["args"]["name"])
        for k, v in x.items():
            if k in ("cmd", "menu") and isinstance(v, str):
                cmds.append(v)
            walk(v, calls, cmds)
    elif isinstance(x, list):
        for v in x:
            walk(v, calls, cmds)


class Lessons(unittest.TestCase):
    def test_hole_for_hardware_is_here(self):
        names = [os.path.basename(p) for p in lessons()]
        self.assertIn("hole-for-hardware.lesson.json", names)
        # Beside the agentlink_families module: where the Tutor looks.
        self.assertTrue(os.path.isfile(os.path.join(FOLDER, os.pardir, "agentlink_families.py")))

    def test_parse_and_named_for_the_package(self):
        for p in lessons():
            with open(p, encoding="utf-8") as f:
                lesson = json.load(f)
            self.assertEqual(lesson.get("schema"), 1, p)
            self.assertTrue(lesson["id"].startswith("workshop."), p)
            self.assertTrue(lesson.get("steps"), p)
            ids = [s["id"] for s in lesson["steps"]]
            self.assertEqual(len(ids), len(set(ids)), p)

    def test_tools_and_commands_exist(self):
        ours, al, cmds_known = workshop_tools(), agentlink_tools(), workshop_commands()
        self.assertIn("hw_hole", ours)
        for p in lessons():
            with open(p, encoding="utf-8") as f:
                lesson = json.load(f)
            calls, cmds = [], []
            walk(lesson, calls, cmds)
            self.assertTrue(calls, p)
            self.assertTrue(set(calls) & ours, f"{p}: calls no Workshop tool")
            # Without Agent Link only Workshop's own can be told apart; the
            # rest are checked in CI's run with Agent Link.
            unknown = [] if al is None else [t for t in calls if t not in ours and t not in al]
            self.assertEqual(unknown, [], f"{os.path.basename(p)}: tools that do not exist")
            bad = [c for c in cmds if c.startswith("Workshop") and c not in cmds_known]
            self.assertEqual(bad, [], f"{os.path.basename(p)}: Workshop commands that do not exist")


if __name__ == "__main__":
    unittest.main()
