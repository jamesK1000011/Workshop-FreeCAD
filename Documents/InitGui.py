# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop for FreeCAD · Documents: its own workbench, "Workshop Documents":
# drawings, exploded assembly drawings, library packs and patent figures and
# drafts, each a command over Documents' own runner (the handler the agent's
# tool calls; a drawing's page opens in TechDraw), and its Manual panel.
# Needs no other add-on.
# The workbench is built in workshop_documents/workbench.py; FreeCAD runs this file at start.
import FreeCADGui

from workshop_documents import workbench as _workshop_documents_workbench

_workshop_documents_workbench.add(FreeCADGui)
