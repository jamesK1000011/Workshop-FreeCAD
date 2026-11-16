# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet as the FreeCAD window opens (workshop/workbench.py calls later()):
# FreeCAD's own AutoSave kept on (once, the change logged), the documents a
# restart could not save reopened from their copies beside their files, as
# "<label> (recovered HH:MM)", and old recovered copies pruned at start and
# daily. Its commands sit in Tools ▸ SafetyNet in every workbench (Workshop's
# manipulator, workshop/placement.py; qt_tools_menu() below for a FreeCAD
# without one). It has no workbench of its own since it joined Workshop.
# Never imports Agent Link.
import os

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")


def _warn(text):
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(text)
    except Exception:  # noqa: BLE001
        pass


def _log(text):
    try:
        import FreeCAD

        FreeCAD.Console.PrintLog(text)
    except Exception:  # noqa: BLE001
        pass


def _start():
    try:
        from . import recovery

        recovery.autosave_on()
        recovery.reopen_now()
    except Exception as e:  # noqa: BLE001 — never stop FreeCAD opening
        _warn(f"SafetyNet: start-up skipped: {e}\n")
    _prune(force=True)
    _daily()


_timer = []


def _prune(force=False):
    """Old recovered copies pruned, quietly (cleanup.py): at start, then at
    most once a day. Only a line in the log (View ▸ Report view with Log)."""
    try:
        from . import cleanup

        r = cleanup.maybe_prune(force=force)
        if r and r.get("removed"):
            _log(f"SafetyNet: {r['removed']} old recovered copies cleaned up ({r['mb']} MB).\n")
    except Exception as e:  # noqa: BLE001
        _log(f"SafetyNet: clean-up skipped: {e}\n")


def _daily():
    """An hourly look whether a day has gone by since the last clean-up."""
    if _timer:
        return
    try:
        from PySide import QtCore

        t = QtCore.QTimer()
        t.setInterval(3600 * 1000)
        t.timeout.connect(_prune)
        t.start()
        _timer.append(t)
    except Exception:  # noqa: BLE001 — no Qt: at start only
        pass


def qt_tools_menu(Gui):
    """A slot that puts the submenu into the Tools menu by Qt after each
    workbench switch (which rebuilds it): for a FreeCAD without workbench
    manipulators, and as the backstop where the manipulator's entry does not
    land (it is skipped when Tools already has a SafetyNet entry)."""

    def slot(*_):
        try:
            from PySide import QtCore, QtGui

            QtWidgets = QtGui
            try:
                from PySide import QtWidgets  # noqa: F811
            except ImportError:
                pass

            def add():
                from . import commands

                mw = Gui.getMainWindow()
                tools = next((a.menu() for a in mw.menuBar().actions() if a.menu() is not None and a.menu().objectName() == "&Tools"), None)
                if tools is None or tools.findChild(QtWidgets.QMenu, "SafetyNetToolsMenu") is not None:
                    return
                # The manipulator's entry (the SafetyNet_Menu command) already there.
                if any(a.text().replace("&", "") == "SafetyNet" for a in tools.actions()):
                    return
                tools.addSeparator()
                sub = tools.addMenu("SafetyNet")
                sub.setObjectName("SafetyNetToolsMenu")
                for name in commands.NAMES:
                    res = commands.COMMANDS[name]().GetResources()
                    act = sub.addAction(res["MenuText"])
                    act.setToolTip(res["ToolTip"])
                    act.triggered.connect(lambda checked=False, n=name: Gui.runCommand(n))

            QtCore.QTimer.singleShot(0, add)
        except Exception as e:  # noqa: BLE001
            _warn(f"SafetyNet: no Tools ▸ SafetyNet menu ({e})\n")

    return slot


def later():
    """The start-up (AutoSave on, recovered copies reopened, old copies
    pruned) once the window is up and the files it was opened with are
    loaded: what Workshop's add() calls."""
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(2500, _start)
    except Exception:  # noqa: BLE001
        _start()
