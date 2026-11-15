# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Make: its own workbench, "Workshop Make": setups,
# checks, fits, hardware and output, each a command over Make's own runner
# (the handler the agent's tool calls), and its panel (Setups, Materials,
# Fits, Review). Needs no other add-on.
# The workbench is built in workshop_make/workbench.py; FreeCAD runs this file at start.
import FreeCADGui

from workshop_make import workbench as _workshop_make_workbench

_workshop_make_workbench.add(FreeCADGui)
