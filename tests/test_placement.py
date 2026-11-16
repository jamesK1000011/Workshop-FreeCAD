# SPDX-License-Identifier: LGPL-2.1-or-later
# Where each command lands (docs/combine-design.md, section 2): the
# manipulator's instructions applied, the way FreeCAD 1.1.3's
# WorkbenchManipulator was seen to apply them on the Mac, to stand-ins of its
# own menus and toolbars (PartDesign, Part, TechDraw, File, Tools). A menu
# "insert" puts the command before the item named among a top-level menu's
# own items only (an item inside a submenu is not found: Subtractive
# Features ▸ Hole); a toolbar "insert" before the item in any toolbar; an
# "append" into &Tools did not land, so none is used. An anchor a workbench
# lacks adds nothing there.
# Fold check: Hole for hardware is not folded into PartDesign Hole's task
# panel (C++, no Python API for it); it is an icon right after
# PartDesign_Hole instead, checked here.
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from workshop import placement  # noqa: E402

# FreeCAD 1.1's own layout, as far as the placements need it (a live check
# confirms these names on the Mac).
FILE = ["Std_New", "Std_Open", "Std_RecentFiles", "Separator", "Std_Save", "Std_SaveAs", "Std_Revert", "Separator",
        "Std_Import", "Std_Export", "Std_MergeProjects", "Std_ProjectInfo", "Separator", "Std_Quit"]
TOOLS = ["Std_AddonMgr", "Separator", "Std_Measure", "Std_QuickMeasure", "Std_UnitsCalculator", "Separator", "Std_DlgCustomize"]
BENCHES = {
    "PartDesignWorkbench": {
        "toolbars": {
            "Part Design Helper Features": ["PartDesign_Body", "PartDesign_NewSketch", "Sketcher_ValidateSketch", "Part_CheckGeometry",
                                            "PartDesign_SubShapeBinder", "PartDesign_Clone", "PartDesign_CompDatums"],
            "Part Design Modeling Features": ["PartDesign_Pad", "PartDesign_Revolution", "PartDesign_AdditiveLoft", "PartDesign_AdditivePipe",
                                              "PartDesign_AdditiveHelix", "PartDesign_CompPrimitiveAdditive", "Separator", "PartDesign_Pocket",
                                              "PartDesign_Hole", "PartDesign_Groove", "PartDesign_SubtractiveLoft"],
        },
        "menus": {"&File": list(FILE), "&Tools": list(TOOLS),
                  "&Part Design": ["PartDesign_Body", "PartDesign_NewSketch", "Separator",
                                   ("Subtractive Features", ["PartDesign_Pocket", "PartDesign_Hole", "PartDesign_Groove"]),
                                   "Separator", "PartDesign_Boolean"]},
    },
    "PartWorkbench": {
        "toolbars": {"Solids": ["Part_Box", "Part_Cylinder", "Part_Sphere", "Part_Cone", "Part_Torus", "Part_Tube", "Part_Primitives", "Part_Builder"],
                     "Boolean": ["Part_Boolean", "Part_Cut", "Part_Fuse", "Part_Common", "Part_CheckGeometry"]},
        "menus": {"&File": list(FILE), "&Tools": list(TOOLS),
                  "&Part": [("Primitives", ["Part_Box", "Part_Cylinder"]), "Part_Primitives", "Part_Builder"]},
    },
    "TechDrawWorkbench": {
        "toolbars": {"TechDraw Pages": ["TechDraw_PageDefault", "TechDraw_PageTemplate", "TechDraw_RedrawPage", "TechDraw_PrintAll"]},
        "menus": {"&File": list(FILE), "&Tools": list(TOOLS),
                  "&TechDraw": ["TechDraw_PageDefault", "TechDraw_PageTemplate", "TechDraw_RedrawPage", "TechDraw_PrintAll"]},
    },
    "WorkshopMakeWorkbench": {
        "toolbars": {"Setup": ["Workshop_Make_NewSetup"]},
        "menus": {"&File": list(FILE), "&Tools": list(TOOLS), "&Make": ["Workshop_Make_NewSetup"]},
    },
}


def _lists(tree):
    """Every list in a nested dict/list tree."""
    if isinstance(tree, list):
        yield tree
    elif isinstance(tree, dict):
        for v in tree.values():
            yield from _lists(v)


def apply(bench, menus, toolbars):
    b = copy.deepcopy(bench)
    for e in toolbars:
        for lst in _lists(b["toolbars"]):
            if e["toolItem"] in lst:
                lst.insert(lst.index(e["toolItem"]), e["insert"])
                break
    for e in menus:
        if "insert" not in e:
            continue  # an append into a menu: did not land on 1.1.3
        for lst in b["menus"].values():  # a top-level menu's own items only
            if isinstance(lst, list) and e["menuItem"] in lst:
                lst.insert(lst.index(e["menuItem"]), e["insert"])
                break
    return b


class Placed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m = placement.Manipulator()
        cls.menus, cls.toolbars = m.modifyMenuBar(), m.modifyToolBars()
        cls.b = {k: apply(v, cls.menus, cls.toolbars) for k, v in BENCHES.items()}

    def after(self, lst, anchor):
        return lst[lst.index(anchor) + 1]

    def test_format(self):
        for e in self.menus:
            self.assertEqual(len(e), 2, e)
            self.assertTrue(("insert" in e or "append" in e) and "menuItem" in e, e)
        for e in self.toolbars:
            self.assertEqual(set(e), {"insert", "toolItem"}, e)
        self.assertEqual(placement.Manipulator().modifyContextMenu("View"), [])

    def test_hole_for_hardware_right_after_partdesign_hole(self):
        tb = self.b["PartDesignWorkbench"]["toolbars"]["Part Design Modeling Features"]
        self.assertEqual(self.after(tb, "PartDesign_Hole"), "Workshop_Make_Hole")
        self.assertEqual(self.after(tb, "Workshop_Make_Hole"), "PartDesign_Groove")
        # The menu: at the Part Design menu's own level, before Boolean (an
        # anchor inside Subtractive Features would add nothing on 1.1.3).
        menu = self.b["PartDesignWorkbench"]["menus"]["&Part Design"]
        self.assertEqual(menu[-3:], ["Workshop_Make_Hole", "Workshop_Make_ThreadLookup", "PartDesign_Boolean"])

    def test_menu_anchors_are_top_level_items(self):
        # Every menu anchor is an item of a top-level menu, never of a
        # submenu, in the stand-ins (what 1.1.3 can find).
        top = {i for b in BENCHES.values() for lst in b["menus"].values() if isinstance(lst, list) for i in lst if isinstance(i, str)}
        nested = {i for b in BENCHES.values() for lst in b["menus"].values() if isinstance(lst, list)
                  for sub in lst if isinstance(sub, tuple) for i in sub[1]}
        for e in self.menus:
            self.assertIn("insert", e, e)
            self.assertIn(e["menuItem"], top, e)
            self.assertNotIn(e["menuItem"], nested - top, e)

    def test_standard_parts_beside_the_primitives(self):
        pd = self.b["PartDesignWorkbench"]["toolbars"]["Part Design Modeling Features"]
        self.assertEqual(self.after(pd, "PartDesign_AdditiveHelix"), "Workshop_Parts_Group")
        part = self.b["PartWorkbench"]["toolbars"]["Solids"]
        self.assertEqual(self.after(part, "Part_Tube"), "Workshop_Parts_Group")
        part_menu = self.b["PartWorkbench"]["menus"]["&Part"]
        i = part_menu.index("Part_Primitives")
        self.assertEqual(part_menu[i - 4:i], list(placement.GROUPS["Workshop_Parts_Group"][3]))

    def test_checks_beside_check_geometry(self):
        h = self.b["PartDesignWorkbench"]["toolbars"]["Part Design Helper Features"]
        self.assertEqual(self.after(h, "Workshop_Make_Checks"), "Part_CheckGeometry")
        tools = self.b["PartDesignWorkbench"]["menus"]["&Tools"]
        self.assertEqual(self.after(tools, "Workshop_Make_MassProperties"), "Std_Measure")

    def test_techdraw(self):
        tb = self.b["TechDrawWorkbench"]["toolbars"]["TechDraw Pages"]
        self.assertEqual(self.after(tb, "TechDraw_PageTemplate"), "Workshop_Documents_Drawing")
        menu = self.b["TechDrawWorkbench"]["menus"]["&TechDraw"]
        self.assertEqual(menu[2:6], ["Workshop_Documents_Drawing", "Workshop_Documents_Exploded", "Workshop_Documents_PatentFigures",
                                     "Workshop_Documents_PatentDraft"])

    def test_file_and_tools_in_every_workbench(self):
        for name, b in self.b.items():
            f = b["menus"]["&File"]
            self.assertEqual(self.after(f, "SafetyNet_Recover"), "Std_Import", name)
            self.assertEqual(self.after(f, "Std_Import"), "Workshop_Electronics_ImportBoard", name)
            self.assertEqual(self.after(f, "Std_Export"), "Workshop_Documents_LibraryPack", name)
            self.assertEqual(b["menus"]["&Tools"][-3:], ["Separator", "SafetyNet_Menu", "Std_DlgCustomize"], name)

    def test_each_stays_in_its_workbench(self):
        make = self.b["WorkshopMakeWorkbench"]
        self.assertEqual(make["toolbars"], BENCHES["WorkshopMakeWorkbench"]["toolbars"])
        td = self.b["TechDrawWorkbench"]
        self.assertNotIn("Workshop_Make_Hole", [c for lst in _lists(td) for c in lst])

    def test_few_injected_icons(self):
        self.assertEqual(set(placement.INJECTED_ICONS), {"Workshop_Parts_Group", "Workshop_Make_Hole", "Workshop_Make_Checks", "Workshop_Documents_Drawing"})

    def test_every_command_has_a_home(self):
        from test_loads import load

        out = load()
        [bench] = out["benches"]
        on_make = [c for cmds in bench["toolbars"].values() for c in cmds]
        sn = list(out["groups"]["SafetyNet_Menu"])
        homes = placement.homes(on_make, sn)
        for name in out["commands"]:
            if name in placement.GROUPS or name == "SafetyNet_Menu":
                continue
            self.assertIn(name, homes, f"{name} has no place")


if __name__ == "__main__":
    unittest.main()
