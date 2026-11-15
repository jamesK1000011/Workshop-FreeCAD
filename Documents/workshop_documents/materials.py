# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's materials.py, trimmed to what Documents uses; 14 Nov 2026.
"""Printing filaments, read from this add-on's own data/filaments.json
(each add-on that needs them carries its own). The person's own filaments
go in ~/.config/workshop_documents/filaments.json and win over ours.
No FreeCAD here."""

import os

from . import datafiles as data

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def filaments():
    """{key: {name, density, E, nu, yield, uts, k, softens, source, date}}"""
    return data.load(_DATA, "filaments", package="workshop_documents")["entries"]


FILAMENTS = filaments()
DENSITY = {k: v["density"] for k, v in FILAMENTS.items()}
