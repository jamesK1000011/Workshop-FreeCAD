# SPDX-License-Identifier: LGPL-2.1-or-later
# The words the person sees in FreeCAD (panels, menus, tooltips, dialogs, task panels, status text) are neutral: the add-on works
# with any MCP client. "Claude" may appear only where the help is about Claude
# Desktop itself (its extension, its log folder). No FreeCAD needed: string
# literals are read from the source (docstrings are not shown, so they are
# left out). The same test is in Agent Link (tests/test_gui_words_neutral.py).
import ast
import os
import re
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GUI = [
    "InitGui.py",
    "safetynet/commands.py",
    "safetynet/local.py",
    "safetynet/macros.py",
    "safetynet/panel.py",
    "safetynet/recovery.py",
    "safetynet/startup.py",
    "safetynet/theme.py",
    "safetynet/workbench.py",
    "workshop/layout.py",
    "workshop/narrow.py",
    "workshop/placement.py",
    "workshop/workbench.py",
    "workshop_documents/commands.py",
    "workshop_documents/handlers/drawing.py",
    "workshop_documents/panel.py",
    "workshop_documents/taskpanels.py",
    "workshop_documents/td_wait.py",
    "workshop_documents/theme.py",
    "workshop_documents/workbench.py",
    "workshop_electronics/commands.py",
    "workshop_electronics/taskpanels.py",
    "workshop_electronics/workbench.py",
    "workshop_fasteners/api.py",
    "workshop_fasteners/fam_fasteners.py",
    "workshop_fasteners/fs.py",
    "workshop_fasteners/keep.py",
    "workshop_make/commands.py",
    "workshop_make/panel.py",
    "workshop_make/taskpanels.py",
    "workshop_make/theme.py",
    "workshop_make/workbench.py",
    "workshop_parts/commands.py",
    "workshop_parts/form.py",
    "workshop_parts/workbench.py",
]
# Allowed: help about Claude Desktop itself, and its log folder's name.
ALLOWED = re.compile(r"Claude Desktop|^Claude$")


def strings(path):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def offending():
    bad = []
    for rel in GUI:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        for line, s in strings(p):
            if "Claude" in s and not ALLOWED.search(s):
                bad.append(f"{rel}:{line}: {s[:90]!r}")
    return bad


class NeutralWords(unittest.TestCase):
    def test_gui_files_are_there(self):
        missing = [rel for rel in GUI if not os.path.exists(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [], "A GUI file in this list moved or is gone: update GUI")

    def test_no_client_name_in_gui_words(self):
        bad = offending()
        self.assertEqual(bad, [], "GUI words name Claude for a general function; say 'the agent' or 'your AI assistant', "
                                  "or name Claude Desktop only where the help is about it:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
