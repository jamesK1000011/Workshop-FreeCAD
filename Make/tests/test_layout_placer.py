# SPDX-License-Identifier: LGPL-2.1-or-later
# The Placer driven through a small stand-in Qt and FreeCADGui: each layout
# places a panel, a workbench switch hides another workbench's panel and
# brings it back, the Combo View tab comes forward only the first time, and
# a task hands the tab back when it ends. The same as Agent Link's test of its copy of layout.py.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workshop_make import layout  # noqa: E402


class Sig:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *a):
        for fn in list(self.slots):
            fn(*a)


class W:
    """A widget: parent, shown, title, a property bag, its class name."""

    def __init__(self, parent=None, *a, cls="QWidget"):
        self.parent, self.shown, self.props, self.max_w = parent, False, {}, None
        self._w = None
        self.cls = cls

    def metaObject(self):  # noqa: N802
        return Meta(self.cls)

    def findChildren(self, cls):  # noqa: N802
        return []

    def __getattr__(self, name):
        if name.startswith("set") or name in ("raise_", "installEventFilter", "deleteLater", "move", "place"):
            return lambda *a, **k: None
        raise AttributeError(name)

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    def setVisible(self, on):  # noqa: N802
        self.shown = bool(on)

    def isVisible(self):  # noqa: N802
        return self.shown

    def isFloating(self):  # noqa: N802
        return False

    def setMaximumWidth(self, w):  # noqa: N802
        self.max_w = w

    def setMaximumHeight(self, h):  # noqa: N802
        self.max_h = h

    def setSizePolicy(self, h, v):  # noqa: N802
        self.policy = (h, v)

    def property(self, k):
        return self.props.get(k)

    def setProperty(self, k, v):  # noqa: N802
        self.props[k] = v

    def setWidget(self, w):  # noqa: N802
        self._w = w

    def widget(self):
        return self._w

    def parentWidget(self):  # noqa: N802
        return self.parent

    def takeWidget(self):  # noqa: N802
        w, self._w = self._w, None
        return w

    def rect(self):
        return types.SimpleNamespace(width=lambda: 1000, height=lambda: 700)


class Tabs(W):
    def __init__(self, *a):
        super().__init__()
        self.pages, self.cur = [], -1
        self.currentChanged = Sig()

    def addTab(self, w, title):  # noqa: N802
        self.pages.append((w, title))
        if self.cur < 0:
            self.cur = 0
        return len(self.pages) - 1

    def count(self):
        return len(self.pages)

    def widget(self, i):
        return self.pages[i][0] if 0 <= i < len(self.pages) else None

    def tabText(self, i):  # noqa: N802
        return self.pages[i][1] if 0 <= i < len(self.pages) else ""

    def indexOf(self, w):  # noqa: N802
        return next((i for i, (x, _t) in enumerate(self.pages) if x is w), -1)

    def removeTab(self, i):  # noqa: N802
        self.pages.pop(i)
        self.cur = min(self.cur, len(self.pages) - 1)

    def setCurrentIndex(self, i):  # noqa: N802
        if i != self.cur:
            self.cur = i
            self.currentChanged.emit(i)

    def setCurrentWidget(self, w):  # noqa: N802
        self.setCurrentIndex(self.indexOf(w))

    def current(self):
        return self.tabText(self.cur)

    def currentIndex(self):  # noqa: N802
        return self.cur


class Meta:
    def __init__(self, name):
        self.name = name

    def className(self):  # noqa: N802
        return self.name


class Dock(W):
    def __init__(self, title="", parent=None, name=None, cls="QDockWidget"):
        super().__init__(parent)
        self.title = title
        self.name = title if name is None else name
        self.cls = cls
        self.w = 270

    def width(self):
        return self.w

    def raise_(self):
        # Of a tab group only the dock in front is visible.
        for d in getattr(self, "group", None) or [self]:
            d.shown = d is self

    def windowTitle(self):  # noqa: N802
        return self.title

    def objectName(self):  # noqa: N802
        return self.name

    def findChild(self, cls, name=None):
        return getattr(self, "tabs", None)

    def findChildren(self, cls):
        return [self.tabs] if getattr(self, "tabs", None) else []


class Main(W):
    def __init__(self, combo=True, name="Std_ComboView", cls="QDockWidget", docks=False):
        """combo: FreeCAD 1.0's Combo View, a Model | Tasks tab widget.
        docks: FreeCAD 1.1's Model and Tasks docks tabbed together, the
        only tab widget in Model the property editor's View | Data."""
        super().__init__()
        self.workbenchActivated = Sig()
        self.tabifiedDockWidgetActivated = Sig()
        self.docks = [Dock("Report view", name="Std_ReportView")]
        self.right, self.left, self.removed = [], [], []
        self.resized = []
        self.group = []
        if docks:
            model = Dock("Model", name="Std_ComboView")
            model.tabs = Tabs()
            model.tabs.addTab(W(), "View")
            model.tabs.addTab(W(), "Data")
            tasks = Dock("Tasks", name="Std_TaskView")
            tasks.setWidget(W(cls="Gui::TaskView::TaskView"))
            self.group[:] = [model, tasks]
            for d in self.group:
                d.group = self.group
            model.shown = True
            self.combo_dock, self.model, self.tasks = model, model, tasks
            self.docks += [model, tasks]
            self.combo = None
        elif combo:
            c = Dock("Combo View", name=name, cls=cls)
            c.shown = True
            self.combo_dock = c
            c.tabs = Tabs()
            c.tabs.addTab(W(), "Model")
            c.tabs.addTab(W(cls="Gui::TaskView::TaskView"), "Tasks")
            self.docks.append(c)
            self.combo = c.tabs
        self.area = W()

    def width(self):
        return 900

    def height(self):
        return 700

    def isMaximized(self):  # noqa: N802
        return False

    isFullScreen = isMaximized

    def findChildren(self, cls):
        return list(self.docks)

    def addDockWidget(self, area, dock):  # noqa: N802
        (self.left if area == 1 else self.right).append(dock)

    def tabifyDockWidget(self, a, b):  # noqa: N802
        if a in self.group and b not in self.group:
            self.group.append(b)
            b.group = self.group

    def tabifiedDockWidgets(self, d):  # noqa: N802
        return [x for x in self.group if x is not d] if d in self.group else []

    def removeDockWidget(self, d):  # noqa: N802
        self.removed.append(d)
        if d in self.group:
            self.group.remove(d)
        d.group = None
        d.shown = False

    def resizeDocks(self, docks, sizes, orientation):  # noqa: N802
        self.resized.append(sizes[0])
        docks[0].w = sizes[0]

    def centralWidget(self):  # noqa: N802
        return self.area


class Slide(W):
    def __init__(self, area, on_toggle=None, on_open=None):
        super().__init__(area)
        self.tabs = Tabs()
        self.on_toggle, self.on_open = on_toggle, on_open

    def set_open(self, on):
        self.shown = bool(on) and self.tabs.count() > 0
        self.on_open(self.shown)

    def toggle(self):
        self.set_open(not self.shown)
        self.on_toggle(self.shown)


class Params:
    def __init__(self):
        self.v = {}

    def GetString(self, k, d=""):  # noqa: N802
        return self.v.get(k, d)


class Placer(unittest.TestCase):
    def setUp(self):
        self.params = Params()
        self.mw = Main()
        self.wb = ["PartDesignWorkbench"]
        self.task = [False]
        gui = types.SimpleNamespace(getMainWindow=lambda: self.mw,
                                    activeWorkbench=lambda: types.SimpleNamespace(name=lambda: self.wb[0]),
                                    Control=types.SimpleNamespace(activeDialog=lambda: self.task[0]))
        core = types.SimpleNamespace(Qt=types.SimpleNamespace(LeftDockWidgetArea=1, RightDockWidgetArea=2, ScrollBarAlwaysOff=1, Horizontal=1),
                                     QTimer=lambda *a: types.SimpleNamespace(setInterval=lambda *a: None, timeout=Sig(), start=lambda: None),
                                     QObject=object, QEvent=types.SimpleNamespace(Close=19, Resize=14))
        core.QTimer.singleShot = lambda ms, fn: fn()
        widgets = types.SimpleNamespace(QDockWidget=Dock, QTabWidget=Tabs, QScrollArea=W, QFrame=types.SimpleNamespace(NoFrame=0),
                                        QSizePolicy=types.SimpleNamespace(Expanding=7, Ignored=13, Preferred=5))
        self.saved = (layout._qt, layout._gui, layout.read, dict(layout._CLASSES))
        self.core = core
        layout._qt = lambda: (core, widgets)
        layout._gui = lambda: gui
        layout.read = lambda params=None: layout.normalise(self.params.GetString(layout.PARAM, layout.DEFAULT))
        layout._CLASSES.clear()
        layout._CLASSES.update(Watch=lambda **k: W(), Slide=Slide)
        self.p = layout.Placer()

    def tearDown(self):
        layout._qt, layout._gui, layout.read, classes = self.saved
        layout._CLASSES.clear()
        layout._CLASSES.update(classes)

    def dock(self, title):
        d = Dock(title)
        d.setWidget(W())
        return d

    def switch(self, wb):
        self.wb[0] = wb
        self.mw.workbenchActivated.emit(wb)

    def test_right_capped_and_only_in_its_workbench(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("ScanRuler")
        content = d.widget()
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "right")
        self.assertTrue(d.shown)
        self.assertEqual(d.max_w, 360)
        self.assertIsNot(d.widget(), content)  # in a frame that follows the dock's width
        self.assertIs(d.widget().widget(), content)
        self.switch("PartDesignWorkbench")
        self.assertFalse(d.shown)
        self.switch("ScanRulerWorkbench")
        self.assertTrue(d.shown)

    def test_closed_stays_closed_until_asked(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("Make")
        self.switch("WorkshopMakeWorkbench")
        self.p.show("make", d, "WorkshopMakeWorkbench")
        self.p._closed(d)
        d.hide()
        self.switch("PartDesignWorkbench")
        self.switch("WorkshopMakeWorkbench")
        self.assertFalse(d.shown)
        self.p.show("make", d, "WorkshopMakeWorkbench")
        self.assertTrue(d.shown)

    def test_left_tab_forward_first_time_then_remembered(self):
        self.params.v["PanelLayout"] = "left-tab"
        d = self.dock("ScanRuler")
        content = d.widget()
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "left-tab")
        self.p.reveal("sr")  # as the workbench opens: Memory's choice stands
        c = self.mw.combo
        self.assertEqual([c.tabText(i) for i in range(c.count())], ["Model", "Tasks", "ScanRuler"])
        self.assertEqual(c.current(), "ScanRuler")
        self.assertFalse(d.shown)
        c.setCurrentIndex(0)  # the person turns to Model
        self.switch("PartDesignWorkbench")
        self.assertEqual([c.tabText(i) for i in range(c.count())], ["Model", "Tasks"])
        self.assertIs(d.widget(), content)  # back in its dock
        self.switch("ScanRulerWorkbench")
        self.assertIn("ScanRuler", [c.tabText(i) for i in range(c.count())])
        self.assertEqual(c.current(), "Model")

    def test_task_wins_then_hands_back(self):
        self.params.v["PanelLayout"] = "left-tab"
        d = self.dock("Texturizer")
        self.switch("TexturizerWorkbench")
        self.p.show("tx", d, "TexturizerWorkbench")
        c = self.mw.combo
        self.assertEqual(c.current(), "Texturizer")
        self.task[0] = True
        self.p.memory.task(True, "TexturizerWorkbench")
        c.setCurrentIndex(1)  # FreeCAD: Tasks
        c.setCurrentIndex(0)  # FreeCAD: Model as the task closes
        self.task[0] = False
        self.assertEqual(self.p.memory.task(False, "TexturizerWorkbench"), "Texturizer")

    def test_default_is_left_tab_and_finds_std_combo_view(self):
        d = self.dock("ScanRuler")
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "left-tab")

    def test_combo_view_found_by_its_class(self):
        self.mw = Main(name="SomethingElse", cls="Gui::DockWnd::ComboView")
        self.assertIs(layout.combo_tabs(self.mw), self.mw.combo)

    def test_outer_tabs_chosen_over_the_property_editors(self):
        # FreeCAD 1.1: no "combiTab" by name, and the property editor's
        # View/Data tabs (inside the Model tab) can come first.
        c = self.mw.combo_dock
        outer = c.tabs
        inner = Tabs()
        inner.parent = W(parent=outer)
        c.findChild = lambda cls, name=None: None
        c.findChildren = lambda cls: [inner, outer]
        self.assertIs(layout.combo_tabs(self.mw), outer)

    def test_empty_tasks_gives_way(self):
        self.params.v["PanelLayout"] = "right"
        self.mw.combo.setCurrentIndex(1)  # Tasks, no task running
        self.p.show("sr", self.dock("ScanRuler"), "ScanRulerWorkbench")
        self.assertEqual(self.mw.combo.current(), "Model")
        self.task[0] = True
        self.mw.combo.setCurrentIndex(1)
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.mw.combo.current(), "Tasks")  # a task runs: left to FreeCAD

    def test_slide_out_narrows_the_combo_view(self):
        self.params.v["PanelLayout"] = "left-slide"
        self.mw.combo_dock.w = 270
        self.switch("SafetyNetWorkbench")
        self.p.show("sn", self.dock("SafetyNet"), "SafetyNetWorkbench")
        self.assertEqual(self.mw.combo_dock.w, 220)
        self.p.toggle()
        self.assertEqual(self.mw.combo_dock.w, 270)

    def test_left_slide_toggles(self):
        self.params.v["PanelLayout"] = "left-slide"
        d = self.dock("SafetyNet")
        self.switch("SafetyNetWorkbench")
        self.assertEqual(self.p.show("sn", d, "SafetyNetWorkbench"), "left-slide")
        self.assertTrue(self.p.slide.shown)
        self.assertFalse(self.p.toggle())
        self.switch("PartDesignWorkbench")
        self.assertEqual(self.p.slide.tabs.count(), 0)
        self.switch("SafetyNetWorkbench")
        self.assertFalse(self.p.slide.shown)  # left closed there

    def test_setting_changed_takes_effect_at_the_next_switch(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("ScanRuler")
        self.switch("ScanRulerWorkbench")
        self.p.show("sr", d, "ScanRulerWorkbench")
        self.params.v["PanelLayout"] = "left-tab"
        self.switch("PartDesignWorkbench")
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.entries["sr"]["where"], "left-tab")
        self.assertNotEqual(d.max_w, 360)  # off the right side's cap

    def test_no_combo_view_falls_back_to_the_right(self):
        self.mw = Main(combo=False)
        self.params.v["PanelLayout"] = "left-tab"
        self.assertEqual(self.p.show("x", self.dock("X"), "XWorkbench"), "right")



class Docks(unittest.TestCase):
    """FreeCAD 1.1: Model and Tasks are docks of their own, tabbed together
    by the main window; the only tab widget in Model is the property
    editor's View | Data. The panel becomes a third dock in that group."""

    setUp_base, tearDown, dock, switch = Placer.setUp, Placer.tearDown, Placer.dock, Placer.switch

    def setUp(self):
        self.setUp_base()
        self.mw = Main(docks=True)

    def test_no_task_tab_widget_here(self):
        self.assertIsNone(layout.combo_tabs(self.mw))
        bar = layout.left_bar(self.mw)
        self.assertEqual(bar.kind, "docks")
        self.assertEqual(bar.titles(), ["Model", "Tasks"])

    def test_tabbed_with_model_and_taken_out_on_switch(self):
        d = self.dock("ScanRuler")
        content = d.widget()
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "left-tab")
        self.p.reveal("sr")
        self.assertIn(d, self.mw.left)
        self.assertEqual([x.windowTitle() for x in self.mw.group], ["Model", "Tasks", "ScanRuler"])
        # Not beside the property editor's View | Data.
        self.assertEqual([self.mw.model.tabs.tabText(i) for i in range(self.mw.model.tabs.count())], ["View", "Data"])
        self.assertTrue(d.shown)  # in front the first time
        self.assertIs(d.widget().widget(), content)
        # The full height of the left side: no cap, the content grows.
        self.assertEqual(getattr(d, "max_h", 16777215), 16777215)
        self.assertEqual(getattr(content, "max_h", 16777215), 16777215)
        self.assertEqual(content.policy[1], 7)  # Expanding
        self.mw.model.raise_()  # the person turns to Model
        self.mw.tabifiedDockWidgetActivated.emit(self.mw.model)
        self.switch("PartDesignWorkbench")
        self.assertIn(d, self.mw.removed)
        self.assertNotIn(d, self.mw.group)
        self.assertIs(d.widget(), content)  # back in its own dock, kept
        self.switch("ScanRulerWorkbench")
        self.assertIn(d, self.mw.group)
        self.assertTrue(self.mw.model.shown)  # as the person left it
        self.assertFalse(d.shown)

    def test_tasks_win_then_hand_back(self):
        d = self.dock("Texturizer")
        self.switch("TexturizerWorkbench")
        self.p.show("tx", d, "TexturizerWorkbench")
        bar = self.p.bar
        self.task[0] = True
        to = self.p.memory.task(True, "TexturizerWorkbench", bar.tasks)
        bar.turn_to(to)
        self.assertTrue(self.mw.tasks.shown)
        self.task[0] = False
        bar.turn_to(self.p.memory.task(False, "TexturizerWorkbench", bar.tasks))
        self.assertTrue(d.shown)

    def test_workbench_tab_before_agent_link(self):
        """Model | Tasks | Texturizer | Agent Link: the workbench's own dock
        right after Tasks, Agent Link's after it, the workbench's in front
        the first time; Agent Link's stays at a switch."""
        hub = self.dock("Agent Link")
        self.p.show("al", hub, layout.EVERYWHERE, "Agent Link")
        self.assertEqual([x.windowTitle() for x in self.mw.group], ["Model", "Tasks", "Agent Link"])
        tx = self.dock("Texturizer")
        self.switch("TexturizerWorkbench")
        self.p.show("tx", tx, "TexturizerWorkbench")
        self.assertEqual([x.windowTitle() for x in self.mw.group], ["Model", "Tasks", "Texturizer", "Agent Link"])
        self.assertTrue(tx.shown)
        self.switch("PartDesignWorkbench")
        self.assertEqual([x.windowTitle() for x in self.mw.group], ["Model", "Tasks", "Agent Link"])
        self.switch("TexturizerWorkbench")
        self.assertEqual([x.windowTitle() for x in self.mw.group], ["Model", "Tasks", "Texturizer", "Agent Link"])

    def test_empty_tasks_dock_gives_way(self):
        self.mw.tasks.raise_()
        self.p.show("sr", self.dock("ScanRuler"), "ScanRulerWorkbench")
        self.assertFalse(self.mw.tasks.shown)


if __name__ == "__main__":
    unittest.main()
