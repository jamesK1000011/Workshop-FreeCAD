# SPDX-License-Identifier: LGPL-2.1-or-later
# The sheet-cutting machines and the materials they cut, read from data
# (data/cut-machines.json, data/shop-materials.json), and the one place a
# name for a machine is made into the machine's key. setup (a cut setup's
# settings) and cut_check / cut_export use these same lists, so a value
# that setup keeps is a value that cut_check takes. Found live (FreeCAD
# 1.1.3, the bicycle): setup kept machine "fiber laser", then cut_check
# refused it. Plain Python: no FreeCAD here.

import os
import re

from . import datafiles as _data

_D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _entries(name):
    return _data.load(_D, name, package="workshop_make")["entries"]


def _key(text):
    return re.sub(r"[\s_\-]+", " ", str(text or "").strip().lower())


def machines():
    """{key: entry} of every machine (ours and the person's own)."""
    return _entries("cut-machines")


def keys():
    return tuple(machines())


def kerf(machine, default=0.2):
    e = machines().get(machine)
    return float(e["kerf"]) if e else default


def aliases():
    """{name said: machine key}: each key, and the names in its entry's
    names (fiber laser, CO2 laser -> laser)."""
    out = {}
    for k, e in machines().items():
        out[_key(k)] = k
        for n in e.get("names") or []:
            out.setdefault(_key(n), k)
    return out


def machine(name):
    """The machine's key for a name said ("Fiber laser" -> "laser"), or
    None when no machine has that name."""
    return aliases().get(_key(name))


def machine_refusal(name):
    """The words that refuse a machine name: the keys, and the other names
    each takes."""
    by = {}
    for n, k in aliases().items():
        if n != k:
            by.setdefault(k, []).append(n)
    said = "; ".join(f"{k}" + (f" (or {', '.join(by[k])})" if by.get(k) else "") for k in keys())
    return f"machine {name!r}: not a machine here. Use one of: {said}."


def cut_materials():
    """(metals, others): the materials a sheet is cut from."""
    shop = _entries("shop-materials")
    return (tuple(k for k, v in shop.items() if v["cut"] and v["metal"]),
            tuple(k for k, v in shop.items() if v["cut"] and not v["metal"]))


def material(name):
    """The material's key ("Aluminium" -> "aluminium"), or None when no
    sheet material has that name."""
    m = _key(name)
    metals, others = cut_materials()
    return m if m in metals + others else None


def material_refusal(name):
    metals, others = cut_materials()
    return f"material {name!r}: not a sheet material here. Use one of: {', '.join(metals + others)}."
