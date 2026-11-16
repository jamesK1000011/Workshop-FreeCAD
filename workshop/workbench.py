# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop as the FreeCAD window opens; InitGui.py calls add(). Every part's
# icons and commands, the one Make workbench (workshop_make/workbench.py),
# the dropdowns and the manipulator that place the rest in FreeCAD's own
# workbenches (placement.py), and SafetyNet's start-up (safetynet/startup.py).
# Built here, in a real module, because FreeCAD runs InitGui.py with exec()
# and a separate locals dict: a class body or a method body there sees only
# FreeCAD's own globals. Never imports Agent Link.
import importlib
import os

from . import PARTS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _warn(text):
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(text)
    except Exception:  # noqa: BLE001
        pass


def icon_dirs():
    """Each part's icons folder (the commands' Pixmap names are file stems)."""
    return [os.path.join(ROOT, p, "icons") for p in PARTS if os.path.isdir(os.path.join(ROOT, p, "icons"))]


def _commands(Gui):
    """Each part's commands registered, each alone: one that fails to load
    is said and the others still come."""
    for p in PARTS:
        try:
            m = importlib.import_module(p + ".commands")
            if hasattr(m, "register"):  # SafetyNet's: registered once, on call
                m.register()
        except Exception as e:  # noqa: BLE001 — never stop FreeCAD starting
            _warn(f"Workshop: {p}'s commands not loaded ({e}).\n")
    from . import placement

    for name in placement.GROUPS:
        Gui.addCommand(name, placement.Group(name))


def _placed(Gui):
    """The manipulator, or for a FreeCAD without one, Tools ▸ SafetyNet by
    Qt after each workbench switch (the other placements need it)."""
    from . import placement

    if hasattr(Gui, "addWorkbenchManipulator"):
        Gui.addWorkbenchManipulator(placement.Manipulator())
        return "manipulator"
    from safetynet import startup

    slot = startup.qt_tools_menu(Gui)
    Gui.getMainWindow().workbenchActivated.connect(slot)
    slot()
    return "qt"


def add(Gui=None):
    """Icons, commands, the Make workbench and the placements, then
    SafetyNet's start-up once the window is up and the files it was opened
    with are loaded. Returns how the placements were made ("manipulator" or
    "qt"), None if they were not."""
    if Gui is None:
        import FreeCADGui as Gui
    for d in icon_dirs():
        Gui.addIconPath(d)
    _commands(Gui)
    try:
        from workshop_make import workbench as make

        Gui.addWorkbench(make.make_class(Gui)())
    except Exception as e:  # noqa: BLE001
        _warn(f"Workshop: the Make workbench not loaded ({e}).\n")
    how = None
    try:
        how = _placed(Gui)
    except Exception as e:  # noqa: BLE001
        _warn(f"Workshop: commands not placed in FreeCAD's workbenches ({e}).\n")
    try:
        from safetynet import startup

        startup.later()
    except Exception as e:  # noqa: BLE001
        _warn(f"SafetyNet: start-up skipped: {e}\n")
    return how
