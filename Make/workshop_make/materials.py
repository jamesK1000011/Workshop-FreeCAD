# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make's own copy of Agent Link for FreeCAD's materials.py, trimmed to what Make uses; 14 Nov 2026.
"""Printing filaments, read from this add-on's own data/filaments.json
(each add-on that needs them carries its own). The person's own filaments
go in ~/.config/workshop_make/filaments.json and win over ours.
No FreeCAD here."""

import os

from . import datafiles as data

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SOURCE = "Typical FDM filament figures, along the layers"


def filaments():
    """{key: {name, density, E, nu, yield, uts, k, softens, source, date}}"""
    return data.load(_DATA, "filaments", package="workshop_make")["entries"]


FILAMENTS = filaments()
DENSITY = {k: v["density"] for k, v in FILAMENTS.items()}


def card(key):
    """A filament as a material card (the shape FreeCAD's library cards are
    read into), or None."""
    f = FILAMENTS.get(str(key).lower())
    if f is None:
        return None
    k = str(key).lower()
    return {"id": k, "name": f["name"], "category": "Printing filament", "density": f["density"], "E": f.get("E"), "nu": f.get("nu"),
            "yield": f.get("yield"), "uts": f.get("uts"), "k": f.get("k"), "softens": f.get("softens"), "source": SOURCE}
