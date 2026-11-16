# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD as the window opens: every command and its icon, the
# one "Make" workbench, each other feature placed in FreeCAD's own
# workbenches and menus by a workbench manipulator (workshop/placement.py),
# Tools ▸ SafetyNet in every workbench, and SafetyNet's start-up (AutoSave
# kept on, documents a crash left reopened from their copies). Never imports
# Agent Link.
# It is built in workshop/workbench.py: FreeCAD runs this file with exec()
# and a separate locals dict, which a class or method body cannot see.
import FreeCADGui

from workshop import workbench as _workshop_workbench

_WORKSHOP_MENUS = _workshop_workbench.add(FreeCADGui)
