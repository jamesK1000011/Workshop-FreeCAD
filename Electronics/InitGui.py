# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Electronics: its own workbench, "Workshop
# Electronics", with its commands in a toolbar and menu. Needs no other
# add-on.
# The workbench is built in workshop_electronics/workbench.py; FreeCAD runs this file at start.
import FreeCADGui

from workshop_electronics import workbench as _workshop_electronics_workbench

_workshop_electronics_workbench.add(FreeCADGui)
