# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD · the Fasteners bridge: Fasteners Workbench (Shai
Seger's add-on, shaise/FreeCAD_FastenersWB; its screw_maker by Ulrich
Brammer; LGPL-2.1-or-later), driven from Workshop and by agents through
Agent Link, when the person has it installed. Nothing of Fasteners is
copied or bundled: its modules are loaded at run time (fs.py) from where
FreeCAD installed it (detect.py).

Without Fasteners this package is dormant: no tools, no tool group, no
menu items, no guide, no errors — one debug line in FreeCAD's log.
workshop_fasteners.api is the Python way in."""

VERSION = "1.0.0"
