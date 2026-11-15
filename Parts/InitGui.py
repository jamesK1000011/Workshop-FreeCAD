# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Parts: its own workbench, "Workshop Parts", with one
# command per generator in its toolbar and menu. Needs no other add-on.
# The workbench is built in workshop_parts/workbench.py; FreeCAD runs this file at start.
import FreeCADGui

from workshop_parts import workbench as _workshop_parts_workbench

_workshop_parts_workbench.add(FreeCADGui)
