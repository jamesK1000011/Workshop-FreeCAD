# SPDX-License-Identifier: LGPL-2.1-or-later
# The panel layout setting (layout.py, the same in every add-on of the
# suite), without a window: read with its default, and which panels show
# per workbench.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from workshop_documents import layout  # noqa: E402


class Params:
    def __init__(self, **kw):
        self.v = dict(kw)

    def GetString(self, k, d=""):  # noqa: N802
        return self.v.get(k, d)


class Setting(unittest.TestCase):
    def test_default_and_values(self):
        self.assertEqual(layout.read(Params()), "left-tab")
        self.assertEqual(layout.read(Params(PanelLayout="sideways")), "left-tab")
        for v in ("right", "left-tab", "left-slide"):
            self.assertEqual(layout.read(Params(PanelLayout=v)), v)
        self.assertEqual(layout.PARAMS, "User parameter:BaseApp/Preferences/Mod/AgentLink")

    def test_caps(self):
        self.assertEqual(layout.TREE_MAX, 300)
        self.assertEqual(layout.TASK_MAX, 360)
        self.assertEqual(layout.SLIDE_MAX, 300)
        self.assertTrue(layout.is_combo("Std_ComboView"))  # FreeCAD 1.x's Combo View

    def test_only_the_active_workbenchs_panel(self):
        panels = {"own": "WorkshopDocumentsWorkbench", "other": "SomeOtherWorkbench", "hub": layout.EVERYWHERE}
        self.assertEqual(layout.shown("WorkshopDocumentsWorkbench", panels), ["own", "hub"])
        self.assertEqual(layout.shown("SomeOtherWorkbench", panels), ["other", "hub"])

    def test_alone_its_own_placer(self):
        self.assertIs(layout.placer(), layout.own())


if __name__ == "__main__":
    unittest.main()
