# SPDX-License-Identifier: LGPL-2.1-or-later
# Tools ▸ SafetyNet by Qt (safetynet/startup.py), the backstop that shows it
# on 1.1.3: the Tools menu is found afresh each time, and one FreeCAD deleted
# meanwhile (the menu bar rebuilt at a workbench switch) is skipped quietly,
# with no traceback in the Report view. Seen live: "RuntimeError: Internal
# C++ object (PySide6.QtWidgets.QMenu) already deleted" at
# tools.findChild(...), twice on each workbench switch.
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

GONE = "Internal C++ object (PySide6.QtWidgets.QMenu) already deleted."


class QObj:
    deleted = False

    def _alive(self):
        if self.deleted:
            raise RuntimeError(GONE)


class Action(QObj):
    def __init__(self, text="", menu=None):
        self._text, self._menu, self.tip = text, menu, None
        self.connected = []

    def text(self):
        self._alive()
        return self._text

    def menu(self):
        self._alive()
        return self._menu

    def setToolTip(self, t):
        self.tip = t

    @property
    def triggered(self):
        return types.SimpleNamespace(connect=self.connected.append)


class Menu(QObj):
    def __init__(self, name, title=""):
        self.name, self.title, self.items, self.subs = name, title, [], []

    def objectName(self):
        self._alive()
        return self.name

    def setObjectName(self, n):
        self.name = n

    def findChild(self, _cls, name):
        self._alive()
        return next((m for m in self.subs if m.name == name), None)

    def actions(self):
        self._alive()
        return list(self.items)

    def addSeparator(self):
        self._alive()
        self.items.append(Action("-"))

    def addMenu(self, title):
        self._alive()
        m = Menu("", title)
        self.subs.append(m)
        self.items.append(Action(title, m))
        return m

    def addAction(self, text):
        a = Action(text)
        self.items.append(a)
        return a


class Bar:
    def __init__(self, menus):
        self.menus = menus

    def actions(self):
        return [Action(m.title, m) for m in self.menus]


def window(*menus):
    mw = types.SimpleNamespace(menuBar=lambda: Bar(list(menus)))
    return types.SimpleNamespace(getMainWindow=lambda: mw, runCommand=lambda n: None)


def shiboken():
    m = types.ModuleType("shiboken6")
    m.isValid = lambda o: not getattr(o, "deleted", False)
    return m


class ToolsMenu(unittest.TestCase):
    def setUp(self):
        fc = types.ModuleType("FreeCAD")
        fc.Console = types.SimpleNamespace(PrintWarning=lambda *_: None, PrintLog=lambda *_: None, PrintMessage=lambda *_: None)
        fc.ParamGet = lambda *_: types.SimpleNamespace(GetString=lambda *a: "", GetBool=lambda *a: False, GetInt=lambda *a: 0)
        self.mods = mock.patch.dict(sys.modules, {"FreeCAD": fc, "FreeCADGui": types.ModuleType("FreeCADGui"), "shiboken6": shiboken()})
        self.mods.start()
        from safetynet import startup

        self.startup = startup
        self.qtw = types.SimpleNamespace(QMenu=Menu)

    def tearDown(self):
        self.mods.stop()

    def test_adds_it_once(self):
        tools = Menu("&Tools", "Tools")
        gui = window(Menu("&File", "File"), tools)
        self.assertTrue(self.startup.add_tools_menu(gui, self.qtw))
        self.assertFalse(self.startup.add_tools_menu(gui, self.qtw), "never twice")
        self.assertEqual([a._text for a in tools.items], ["-", "SafetyNet"])
        self.assertGreater(len(tools.subs[0].items), 3)

    def test_the_manipulators_entry_is_enough(self):
        tools = Menu("&Tools", "Tools")
        tools.items.append(Action("&SafetyNet"))
        self.assertFalse(self.startup.add_tools_menu(window(tools), self.qtw))
        self.assertEqual(len(tools.items), 1)

    def test_a_deleted_tools_menu_is_skipped_quietly(self):
        # Deleted before it is found: not valid, so not used.
        old = Menu("&Tools", "Tools")
        old.deleted = True
        self.assertFalse(self.startup.add_tools_menu(window(old), self.qtw))
        # Deleted between being found and used (the live traceback's line):
        # no RuntimeError out of it.
        tools = Menu("&Tools", "Tools")
        real = tools.objectName

        def found_then_gone():
            n = real()
            tools.deleted = True
            return n

        tools.objectName = found_then_gone
        self.assertFalse(self.startup.add_tools_menu(window(tools), self.qtw))

    def test_a_fresh_menu_each_call(self):
        first, second = Menu("&Tools", "Tools"), Menu("&Tools", "Tools")
        bars = [Bar([first]), Bar([second])]
        mw = types.SimpleNamespace(menuBar=lambda: bars.pop(0))
        gui = types.SimpleNamespace(getMainWindow=lambda: mw, runCommand=lambda n: None)
        self.assertTrue(self.startup.add_tools_menu(gui, self.qtw))
        first.deleted = True  # FreeCAD rebuilt the menu bar at a switch
        self.assertTrue(self.startup.add_tools_menu(gui, self.qtw), "the new Tools menu gets it too")
        self.assertEqual([a._text for a in second.items], ["-", "SafetyNet"])

    def test_no_module_keeps_a_menu(self):
        with open(os.path.join(ROOT, "safetynet", "startup.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("tools = next(", src)


if __name__ == "__main__":
    unittest.main()
