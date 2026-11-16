# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where each command of the add-on sits in FreeCAD (docs/combine-design.md,
section 2): in the FreeCAD workbench it belongs to, through one workbench
manipulator, and only what has no home there in the small Make workbench.

A manipulator can only insert an item *before* another, or append it to a
menu; "right after X" is written as "before the item FreeCAD 1.1 puts after
X". An anchor a workbench does not have adds nothing there, which keeps each
entry in its own workbench. Pure Python: tested without FreeCAD."""

TOOLBAR, MENU = "toolbar", "menu"
BEFORE, INTO = "before", "into"

# Commands FreeCAD's own workbenches gain, grouped as one dropdown each so
# the injected icons stay few: name -> (menu text, tooltip, icon, members).
GROUPS = {
    "Workshop_Parts_Group": (
        "Standard Parts",
        "Gridfinity bins and baseplates, project boxes and board boxes, made to size.",
        "Workshop_Parts_GridfinityBin",
        ("Workshop_Parts_GridfinityBin", "Workshop_Parts_GridfinityBaseplate", "Workshop_Parts_ProjectBox", "Workshop_Parts_BoardBox"),
    ),
    "Workshop_Make_Checks": (
        "Make Checks",
        "DFM check, part review and mass properties of the selected part.",
        "Workshop_Make_PartReview",
        ("Workshop_Make_DfmCheck", "Workshop_Make_PartReview", "Workshop_Make_MassProperties"),
    ),
}

# (command, toolbar or menu, before or into, anchor, the workbench it lands
# in (None: every workbench), what it is beside). Anchors are FreeCAD 1.1
# command names (menus by their object name, "&Tools"); in order: several
# items before one anchor keep this order.
PLACES = (
    # Parts → Part and Part Design: one dropdown, beside the primitives.
    ("Workshop_Parts_Group", TOOLBAR, BEFORE, "Part_Primitives", "PartWorkbench", "the Part primitives"),
    ("Workshop_Parts_Group", TOOLBAR, BEFORE, "PartDesign_CompPrimitiveAdditive", "PartDesignWorkbench", "the additive primitives"),
    ("Workshop_Parts_GridfinityBin", MENU, BEFORE, "Part_Primitives", "PartWorkbench", "Part ▸ Primitives"),
    ("Workshop_Parts_GridfinityBaseplate", MENU, BEFORE, "Part_Primitives", "PartWorkbench", "Part ▸ Primitives"),
    ("Workshop_Parts_ProjectBox", MENU, BEFORE, "Part_Primitives", "PartWorkbench", "Part ▸ Primitives"),
    ("Workshop_Parts_BoardBox", MENU, BEFORE, "Part_Primitives", "PartWorkbench", "Part ▸ Primitives"),
    # Hole for hardware: its own icon right after PartDesign_Hole (its
    # controls cannot fold into Hole's C++ task panel from Python); Thread
    # lookup in the menu after it.
    ("Workshop_Make_Hole", TOOLBAR, BEFORE, "PartDesign_Groove", "PartDesignWorkbench", "after PartDesign_Hole"),
    ("Workshop_Make_Hole", MENU, BEFORE, "PartDesign_Groove", "PartDesignWorkbench", "after PartDesign_Hole"),
    ("Workshop_Make_ThreadLookup", MENU, BEFORE, "PartDesign_Groove", "PartDesignWorkbench", "after Hole for hardware"),
    # The checks: one dropdown beside Check Geometry; mass beside Measure.
    ("Workshop_Make_Checks", TOOLBAR, BEFORE, "Part_CheckGeometry", "PartDesignWorkbench", "Check Geometry"),
    ("Workshop_Make_MassProperties", MENU, BEFORE, "Std_Measure", None, "Measure"),
    # KiCad board: File ▸ Import area, every workbench.
    ("Workshop_Electronics_ImportBoard", MENU, BEFORE, "Std_Export", None, "after File ▸ Import"),
    # Documents → TechDraw: Drawing an icon after the page commands, the
    # rest in the TechDraw menu after it; library packs after File ▸ Export.
    ("Workshop_Documents_Drawing", TOOLBAR, BEFORE, "TechDraw_RedrawPage", "TechDrawWorkbench", "after the page commands"),
    ("Workshop_Documents_Drawing", MENU, BEFORE, "TechDraw_RedrawPage", "TechDrawWorkbench", "after the page commands"),
    ("Workshop_Documents_Exploded", MENU, BEFORE, "TechDraw_RedrawPage", "TechDrawWorkbench", "after Drawing"),
    ("Workshop_Documents_PatentFigures", MENU, BEFORE, "TechDraw_RedrawPage", "TechDrawWorkbench", "after Drawing"),
    ("Workshop_Documents_PatentDraft", MENU, BEFORE, "TechDraw_RedrawPage", "TechDrawWorkbench", "after Drawing"),
    ("Workshop_Documents_LibraryPack", MENU, BEFORE, "Std_MergeProjects", None, "after File ▸ Export"),
    # SafetyNet: Tools ▸ SafetyNet in every workbench, Recovered Copies in
    # File too.
    ("Separator", MENU, INTO, "&Tools", None, "Tools"),
    ("SafetyNet_Menu", MENU, INTO, "&Tools", None, "Tools"),
    ("SafetyNet_Recover", MENU, BEFORE, "Std_Import", None, "File ▸ Import"),
)

# The Make workbench's panels: Make's (Setups, Materials, Fits, Review) and
# Documents' Manual.
MAKE_PANELS = ("Workshop_Make_Panel", "Workshop_Documents_Panel")

# Commands on the Make workbench's own toolbars and menu (workshop_make's
# commands.TOOLBARS) and in Tools ▸ SafetyNet (safetynet's commands.NAMES),
# for the "every command has a home" check.
ELSEWHERE = {"make": "the Make workbench", "safetynet": "Tools ▸ SafetyNet"}

# The icons this add-on puts into FreeCAD's own toolbars: few, on purpose.
INJECTED_ICONS = tuple(dict.fromkeys(c for c, kind, *_ in PLACES if kind == TOOLBAR))


def entry(cmd, kind, how, anchor):
    """One manipulator instruction, in the dict format FreeCAD's
    WorkbenchManipulator reads."""
    key = "toolItem" if kind == TOOLBAR else "menuItem"
    return {("insert" if how == BEFORE else "append"): cmd, key: anchor}


def toolbars():
    return [entry(c, k, h, a) for c, k, h, a, *_ in PLACES if k == TOOLBAR]


def menus():
    return [entry(c, k, h, a) for c, k, h, a, *_ in PLACES if k == MENU]


class Manipulator:
    """Every workbench's menus and toolbars as FreeCAD builds them, with
    this add-on's commands put in their places (Gui.addWorkbenchManipulator)."""

    def modifyMenuBar(self):
        return menus()

    def modifyToolBars(self):
        return toolbars()

    def modifyContextMenu(self, recipient):
        return []

    def modifyDockWindows(self):
        return []


class Group:
    """A dropdown of commands: one toolbar icon for several."""

    def __init__(self, name):
        self.name = name
        self.text, self.tip, self.pixmap, self.members = GROUPS[name]

    def GetCommands(self):
        return tuple(self.members)

    def GetDefaultCommand(self):
        return 0

    def GetResources(self):
        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": self.pixmap, "DropDownMenu": True, "Exclusive": False}

    def IsActive(self):
        return True


def homes(make_names, safetynet_names):
    """Every command -> where it sits (for the docs and the tests)."""
    out = {}
    for c, _k, _h, _a, wb, beside in PLACES:
        if c in GROUPS:
            for m in GROUPS[c][3]:
                out.setdefault(m, f"{wb}: in {c}, beside {beside}")
        out.setdefault(c, f"{wb or 'every workbench'}: beside {beside}")
    for c in make_names:
        out.setdefault(c, ELSEWHERE["make"])
    for c in MAKE_PANELS:
        out.setdefault(c, ELSEWHERE["make"])
    for c in safetynet_names:
        out.setdefault(c, ELSEWHERE["safetynet"])
    return out
