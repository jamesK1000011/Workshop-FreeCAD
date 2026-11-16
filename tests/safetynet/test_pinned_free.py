# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet declares its recovery tool PINNED_FREE: answered after the person
# closed the document the agent worked in, so Agent Link's window link learns
# it from the add-on and need not name it. Read from the source: no Agent Link
# or FreeCAD needed.
import ast
import os
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "safetynet", "fam_safety.py")


class PinnedFree(unittest.TestCase):
    def test_recovery_tool_declared(self):
        tree = ast.parse(open(SRC, encoding="utf-8").read())
        declared = [ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "PINNED_FREE" for t in n.targets)]
        self.assertEqual(declared, [{"app_recover"}])
        tools = {n.args[0].value for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "Tool" and n.args and isinstance(n.args[0], ast.Constant)}
        self.assertLessEqual(declared[0], tools, "every pinned tool is one of this family's")


if __name__ == "__main__":
    unittest.main()
