# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD · Electronics: KiCad boards read without KiCad, the
board as a FreeCAD solid with its tall parts, PCB order packages.

    from workshop_electronics import api
    b = api.read_board("/path/to/board.kicad_pcb")
    api.add_board(doc, b)

Plain values in millimetres; a request it cannot carry out is refused
(its refusal.Refused) with what to do instead."""

VERSION = "0.2.0"
