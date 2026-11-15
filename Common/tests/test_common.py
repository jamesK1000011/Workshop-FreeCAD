# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Common is the workbench only: its menu registry, and nothing any
# add-on imports for its own work.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


class Common(unittest.TestCase):
    def test_menus_collect_once(self):
        from workshop_common import workbench

        workbench.add("Test", ["A", "B"])
        workbench.add("Test", ["B", "C"])
        self.assertEqual(workbench.MENUS["Test"], ["A", "B", "C"])
        del workbench.MENUS["Test"]

    def test_holds_only_the_workbench(self):
        names = sorted(n for n in os.listdir(os.path.join(HERE, "..", "workshop_common")) if n.endswith(".py"))
        self.assertEqual(names, ["__init__.py", "workbench.py"])


if __name__ == "__main__":
    unittest.main()
