# SPDX-License-Identifier: LGPL-2.1-or-later
# The handlers (workshop_documents/handlers): one function per tool the data defines,
# and no Agent Link import among them — read from the source, so no FreeCAD
# or Agent Link is needed.
import ast
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(os.path.dirname(os.path.dirname(HERE)), "workshop_documents")


def sources():
    one = os.path.join(PKG, "handlers.py")
    if os.path.exists(one):
        return [one]
    d = os.path.join(PKG, "handlers")
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".py")]


def handlers():
    """{tool name: True when it names a module-level function (or a call of
    one, a handler factory)} over every handler module."""
    out = {}
    for path in sources():
        t = ast.parse(open(path, encoding="utf-8").read())
        fns = {n.name for n in t.body if isinstance(n, ast.FunctionDef)}
        for n in t.body:
            if isinstance(n, ast.Assign) and any(getattr(x, "id", None) == "HANDLERS" for x in n.targets) and isinstance(n.value, ast.Dict):
                for k, v in zip(n.value.keys, n.value.values):
                    f = v.func if isinstance(v, ast.Call) else v
                    out[k.value] = isinstance(f, ast.Name) and f.id in fns
    return out


class Handlers(unittest.TestCase):
    def test_no_agentlink_import(self):
        for path in sources():
            for n in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                self.assertFalse(any(m.split(".")[0] == "agentlink" for m in mods), f"{os.path.basename(path)} imports {mods}")

    def test_every_tool_has_a_function(self):
        h = handlers()
        self.assertTrue(h)
        self.assertEqual([k for k, ok in h.items() if not ok], [])
    def test_handlers_match_the_data(self):
        with open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8") as f:
            defined = set(json.load(f)["entries"])
        self.assertEqual(set(handlers()), defined)
