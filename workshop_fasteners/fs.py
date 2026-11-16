# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fasteners Workbench's own modules, loaded at run time (never copied):
FastenerBase, ScrewMaker, FastenersCmd and PEMInserts, from the folder
detect.find() gives. Loaded on the first call that needs them, never at
Workshop's start.

Without a window. FastenerBase imports FreeCADGui at its top, though it
uses it only behind FSutils.isGuiLoaded(). In FreeCAD's own command line
FreeCADGui imports; in a plain Python with FreeCAD on its path it may not.
Then a stand-in module is put in sys.modules for the length of the import
only, and taken out again: Fasteners itself is not changed."""
import contextlib
import importlib
import sys
import types

from . import detect


class Missing(Exception):
    """Fasteners Workbench is not installed, or it would not load here."""

    def __init__(self, message, code="unavailable"):
        super().__init__(message)
        self.code = code
        self.message = message


NOT_INSTALLED = "Fasteners Workbench is not installed: the Addon Manager has it (Fasteners)."
MODULES = ("FSutils", "FastenerBase", "ScrewMaker", "FastenersCmd")
# Loaded where it can be: at its top it fills FastenerBase.FSClassIcons,
# which Fasteners defines only with a window, so without one it cannot
# load (its classes only restore PEM parts saved in old files).
OPTIONAL = ("PEMInserts",)


@contextlib.contextmanager
def _gui_guard():
    """FreeCADGui importable for the length of the block; a stand-in only
    where the real one cannot load (no window), removed afterwards."""
    stand_in = None
    if "FreeCADGui" not in sys.modules:
        try:
            importlib.import_module("FreeCADGui")
        except Exception:  # noqa: BLE001 — no window here
            stand_in = types.ModuleType("FreeCADGui")
            stand_in.__doc__ = "Workshop's stand-in while Fasteners loads without a window."
            sys.modules["FreeCADGui"] = stand_in
    try:
        yield
    finally:
        if stand_in is not None and sys.modules.get("FreeCADGui") is stand_in:
            del sys.modules["FreeCADGui"]


_mods = None


def load():
    """A namespace of Fasteners' modules (FastenerBase, ScrewMaker,
    FastenersCmd, FSutils; PEMInserts where it loads), or Missing."""
    global _mods
    if _mods is not None:
        return _mods
    info = detect.find()
    if info is None:
        raise Missing(NOT_INSTALLED)
    if info["path"] not in sys.path:
        sys.path.append(info["path"])
    ns = types.SimpleNamespace(path=info["path"], version=info.get("version"))
    try:
        with _gui_guard():
            for m in MODULES:
                setattr(ns, m, importlib.import_module(m))
            for m in OPTIONAL:
                try:
                    setattr(ns, m, importlib.import_module(m))
                except Exception:  # noqa: BLE001 — no window: see OPTIONAL
                    setattr(ns, m, None)
    except Exception as e:  # noqa: BLE001
        raise Missing(f"Fasteners Workbench is installed ({info['path']}) but would not load here: {type(e).__name__}: {e}") from e
    ns.screwMaker = ns.ScrewMaker.Instance
    _mods = ns
    return ns


def loaded():
    """Fasteners' modules if loaded already (by us or by its workbench),
    else None; never loads them."""
    if _mods is not None:
        return _mods
    if all(m in sys.modules for m in MODULES[:4]):
        try:
            return load()
        except Missing:
            return None
    return None


def reset():
    global _mods
    _mods = None
