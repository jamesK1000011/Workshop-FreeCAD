# SPDX-License-Identifier: LGPL-2.1-or-later
# Where a workbench's panel stands. One setting for every add-on of the
# suite, read by each add-on itself (each carries its own copy of this small
# module, with the same API):
#
#   User parameter:BaseApp/Preferences/Mod/AgentLink, PanelLayout =
#     left-tab    (the default) the panel is a tab of the Combo View beside
#                 Model and Tasks while its workbench is active; a window
#                 without a Combo View gets right
#     right       the panel docks on the right (at most 360 px wide); the
#                 left side stays the model tree
#     left-slide  the panel slides out over the left edge of the 3D view
#                 (at most 300 px; the Combo View narrows while it is open),
#                 opened and closed from its workbench's toolbar or the
#                 handle on the view's edge; the tree is never covered
#
# The setting is read each time a panel is placed, so a change takes effect
# at the next workbench switch, with no restart. Only the active
# workbench's panel shows: switching workbench hides the other add-ons'
# panels, and they come back with their workbench. When Agent Link is
# installed it offers its placer as the service "panel_layout" and every
# add-on places its panel through it, so panels of different add-ons share
# one place; alone, an add-on places its own.
#
# This file is the same in every add-on but for its first line (the
# licence of the add-on that carries it).
#
# The rules (which panels show, which tab comes forward) are plain Python
# and tested without a window; the Qt part is the Placer.

PARAMS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
PARAM = "PanelLayout"
RIGHT, LEFT_TAB, LEFT_SLIDE = "right", "left-tab", "left-slide"
LAYOUTS = (RIGHT, LEFT_TAB, LEFT_SLIDE)
DEFAULT = LEFT_TAB
# Logical pixels: the tree side, and the side a task panel stands on; the
# slide-out (it covers the 3D view, so narrower), the Combo View while the
# slide-out is open, and the most a panel's content may ask as its minimum
# width (wider rows wrap or stack).
TREE_MAX, TASK_MAX = 300, 360
SLIDE_MAX, COMBO_SQUEEZE = 300, 220
CONTENT_MIN = 240
# The Combo View dock: its object name in FreeCAD 1.x is Std_ComboView.
COMBO_NAMES = ("Std_ComboView", "Combo View", "ComboView", "Std_TreeView", "Model", "Tree view")
TASKS = "Tasks"
SERVICE = "panel_layout"
EVERYWHERE = "*"


# ---- plain rules (no Qt) ----------------------------------------------------

def normalise(value):
    """A PanelLayout value as one of LAYOUTS; anything else is the default."""
    v = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
    return v if v in LAYOUTS else DEFAULT


def _params(params=None):
    if params is not None:
        return params
    import FreeCAD

    return FreeCAD.ParamGet(PARAMS)


def read(params=None):
    """The layout the setting asks for now ("left-tab" when unset or unknown)."""
    try:
        return normalise(_params(params).GetString(PARAM, DEFAULT))
    except Exception:  # noqa: BLE001 — no FreeCAD (tests, FreeCADCmd)
        return DEFAULT


def is_set(params=None):
    """Whether PanelLayout has been set at all (by the person or by us)."""
    try:
        return bool(_params(params).GetString(PARAM, "").strip())
    except Exception:  # noqa: BLE001
        return False


def width_cap(layout):
    """The widest a panel may make its side in this layout."""
    return {RIGHT: TASK_MAX, LEFT_SLIDE: SLIDE_MAX}.get(normalise(layout), TREE_MAX)


def slide_width(area_width):
    """The slide-out's width over a 3D view area this wide."""
    return int(min(SLIDE_MAX, max(200, area_width // 2)))


def is_combo(name, class_name=""):
    """Whether a dock (its object name, its class name) is the Combo View."""
    return name in COMBO_NAMES or "ComboView" in (class_name or "")


def unstick(titles, current, running, tasks=TASKS, model="Model"):
    """The tab to turn the Combo View to when it sits on an empty Tasks with
    no task running: Model (or the first tab that is not Tasks); None to
    leave it."""
    if running or current != tasks:
        return None
    if model in titles:
        return model
    return next((t for t in titles if t != tasks), None)


def belongs(workbench, active):
    """Whether a panel placed for workbench shows while active is up:
    EVERYWHERE (Agent Link's own panel) shows in every workbench."""
    if workbench == EVERYWHERE:
        return True
    wbs = (workbench,) if isinstance(workbench, str) else tuple(workbench or ())
    return active in wbs


def shown(active, panels):
    """The keys of panels ({key: workbench}) that show while the workbench
    active is up, in the order given."""
    return [k for k, wb in panels.items() if belongs(wb, active)]


def size_to_restore(before, after, maximized):
    """The (width, height) to put the main window back to after a panel was
    placed, or None: none when it is maximised or full screen (the screen
    sets its size) or unchanged. A dock added beside others could widen the
    whole window (live on the Mac: 856 to 1414 px)."""
    if maximized or before is None or tuple(before) == tuple(after):
        return None
    return tuple(before)


KEEP_SIZE_MS = (0, 150, 400)


class Memory:
    """What comes forward, per workbench. In the Combo View (left-tab): the
    panel's tab the first time its workbench opens; after that the tab the
    person last chose there. Tasks while a task runs (FreeCAD brings it
    forward itself); when the task ends, the tab chosen before it. For the
    slide-out (left-slide): open the first time, then as the person left
    it in that workbench."""

    def __init__(self):
        self.last = {}
        self.slide = {}
        self.running = False

    def opened(self, wb, ours):
        """The tab to bring forward as wb opens: ours the first time, else
        the one last chosen there (None: leave the tabs as they are)."""
        if wb not in self.last:
            self.last[wb] = ours
            return ours
        return self.last[wb]

    def chose(self, wb, title, tasks=TASKS):
        """The person turned to title in wb (ignored while a task runs:
        FreeCAD turns the tabs itself to Tasks and back to Model)."""
        if self.running or not title or title == tasks:
            return
        self.last[wb] = title

    def task(self, running, wb, tasks=TASKS):
        """Called as the task state is polled: tasks when a task has just
        started (it comes forward), the tab chosen before it when the task
        has just ended, else None."""
        was, self.running = self.running, bool(running)
        if running and not was:
            return tasks
        if was and not running:
            return self.last.get(wb)
        return None

    def slide_open(self, wb):
        """Whether the slide-out opens as wb opens."""
        return self.slide.setdefault(wb, True)

    def slid(self, wb, on):
        self.slide[wb] = bool(on)


# ---- the window (Qt) --------------------------------------------------------

def _qt():
    from PySide import QtCore, QtGui

    QtWidgets = QtGui
    try:
        from PySide import QtWidgets  # noqa: F811  (Qt 6 builds)
    except ImportError:
        pass
    return QtCore, QtWidgets


def _gui():
    import FreeCADGui

    return FreeCADGui


def active_workbench():
    try:
        return _gui().activeWorkbench().name()
    except Exception:  # noqa: BLE001
        return None


def task_running():
    try:
        return bool(_gui().Control.activeDialog())
    except Exception:  # noqa: BLE001
        return False


TASK_NAMES = ("Std_TaskView", "Tasks", "Task view", "TaskView")


def is_tasks(name, class_name=""):
    """Whether a dock (its object name, its widget's class) is the task
    view's own dock (FreeCAD 1.x: Std_TaskView, "Tasks")."""
    return name in TASK_NAMES or "TaskView" in (class_name or "")


def _classes_in(w, QtWidgets):
    """The class names of w and everything under it."""
    out = []
    try:
        out.append(w.metaObject().className())
        out += [c.metaObject().className() for c in w.findChildren(QtWidgets.QWidget)]
    except Exception:  # noqa: BLE001
        pass
    return out


def is_task_tabs(tabs, QtWidgets=None):
    """Whether a QTabWidget is a real Model | Tasks tab widget (FreeCAD
    1.0's Combo View): one of its pages holds the task view. The property
    editor's View | Data tabs do not."""
    if QtWidgets is None:
        _c, QtWidgets = _qt()
    for i in range(tabs.count()):
        page = tabs.widget(i)
        if page is not None and any("TaskView" in n for n in _classes_in(page, QtWidgets)):
            return True
    return False


def combo_tabs(mw):
    """The Combo View's Model | Tasks tab widget when this FreeCAD has one
    (1.0); None when Model and Tasks are docks of their own, tabbed
    together by the main window (1.1)."""
    d = combo_dock(mw)
    if d is None:
        return None
    _c, QtWidgets = _qt()
    for t in [d.findChild(QtWidgets.QTabWidget, "combiTab")] + list(d.findChildren(QtWidgets.QTabWidget)):
        if t is not None and is_task_tabs(t, QtWidgets):
            return t
    return None


def tasks_dock(mw):
    """The task view's own dock (Std_TaskView), or None."""
    _c, QtWidgets = _qt()
    docks = mw.findChildren(QtWidgets.QDockWidget)
    for d in docks:
        if is_tasks(d.objectName()):
            return d
    for d in docks:
        w = d.widget()
        if w is not None and any(is_tasks("", n) for n in _classes_in(w, QtWidgets)[:1]):
            return d
    return None


class TabBar:
    """Model | Tasks as a QTabWidget (FreeCAD 1.0's Combo View): panels are
    tabs of it."""

    kind = "tabs"

    def __init__(self, tabs):
        self.tabs = tabs
        self.tasks, self.model = TASKS, "Model"

    def titles(self):
        return [self.tabs.tabText(i) for i in range(self.tabs.count())]

    def current(self):
        return self.tabs.tabText(self.tabs.currentIndex())

    def turn_to(self, title):
        for i, t in enumerate(self.titles()):
            if t == title:
                self.tabs.setCurrentIndex(i)
                return True
        return False

    def add(self, e, mw):
        self.tabs.addTab(e["frame"], e["title"])
        e["dock"].hide()

    def remove(self, e, mw):
        i = self.tabs.indexOf(e["frame"])
        if i >= 0:
            self.tabs.removeTab(i)

    def front(self, e):
        self.tabs.setCurrentWidget(e["frame"])

    def watch(self, fn):
        t = self.tabs
        # A Qt property: FreeCAD's tab widget may come back in a new Python
        # wrapper, which would not keep a Python attribute.
        if not t.property("panelLayout"):
            t.currentChanged.connect(lambda i: fn(t.tabText(i)))
            t.setProperty("panelLayout", True)


class DockBar:
    """Model and Tasks as docks of their own, tabbed together by the main
    window (FreeCAD 1.1): a panel is a third dock tabbed with them."""

    kind = "docks"

    def __init__(self, mw, model, tasks=None):
        self.mw, self.model_dock, self.tasks_dock = mw, model, tasks
        self.tasks = tasks.windowTitle() if tasks is not None else TASKS
        self.model = model.windowTitle()

    def group(self):
        try:
            mates = list(self.mw.tabifiedDockWidgets(self.model_dock))
        except Exception:  # noqa: BLE001
            mates = []
        return [self.model_dock] + [d for d in mates if d is not self.model_dock]

    def titles(self):
        return [d.windowTitle() for d in self.group()]

    def current(self):
        """The title of the dock in front: of a tab group only the dock in
        front is visible."""
        for d in self.group():
            if d.isVisible():
                return d.windowTitle()
        return ""

    def turn_to(self, title):
        for d in self.group():
            if d.windowTitle() == title:
                d.raise_()
                return True
        return False

    def add(self, e, mw):
        QtCore, _w = _qt()
        dock = e["dock"]
        dock.setWidget(e["frame"])
        dock.setMaximumWidth(16777215)
        # The whole height of the left side, as Model and Tasks have: no cap.
        dock.setMaximumHeight(16777215)
        mw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        mw.tabifyDockWidget(self.model_dock, dock)
        dock.show()

    def remove(self, e, mw):
        # Out of the window, the widget kept (it goes back in its dock).
        mw.removeDockWidget(e["dock"])

    def front(self, e):
        e["dock"].raise_()

    def watch(self, fn):
        mw = self.mw
        if mw.property("panelLayoutDocks"):
            return
        try:
            mw.tabifiedDockWidgetActivated.connect(lambda d: fn(d.windowTitle()))
            mw.setProperty("panelLayoutDocks", True)
        except Exception:  # noqa: BLE001 — Qt before 5.8: the poll's view of what is in front
            pass


def left_bar(mw):
    """Where left-tab puts a panel: the Combo View's Model | Tasks tab
    widget (FreeCAD 1.0), else the Model dock's tab group (1.1); None in
    a window with neither."""
    t = combo_tabs(mw)
    if t is not None:
        return TabBar(t)
    model = combo_dock(mw)
    if model is None:
        return None
    return DockBar(mw, model, tasks_dock(mw))


def combo_dock(mw):
    """The Combo View's dock (Std_ComboView in FreeCAD 1.x), by its object
    name, else by its widget's class (Gui::DockWnd::ComboView)."""
    _c, QtWidgets = _qt()
    docks = mw.findChildren(QtWidgets.QDockWidget)
    for d in docks:
        if is_combo(d.objectName()):
            return d
    for d in docks:
        try:
            names = [d.metaObject().className()]
            w = d.widget()
            if w is not None:
                names.append(w.metaObject().className())
        except Exception:  # noqa: BLE001
            continue
        if any(is_combo("", n) or "TreeWidget" in n or "TreeView" in n or "TreePanel" in n for n in names):
            return d
    return None


def frame(content):
    """content in a scroll area that scrolls up and down only: its side
    never widens past the cap; long content scrolls."""
    QtCore, QtWidgets = _qt()
    sa = QtWidgets.QScrollArea()
    sa.setObjectName("PanelLayoutFrame")
    sa.setWidgetResizable(True)
    sa.setFrameShape(QtWidgets.QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    sa.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
    sa.setMinimumWidth(0)
    # The content follows the viewport's width (never wider: no clipping at
    # the right edge); its rows wrap or stack to fit.
    content.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
    content.setMinimumWidth(0)
    content.setMaximumHeight(16777215)  # nothing caps its height
    sa.setWidget(content)
    return sa


_CLASSES = {}


def _classes():
    """The Qt classes, made on first use (no Qt at import)."""
    if _CLASSES:
        return _CLASSES
    QtCore, QtWidgets = _qt()

    class Watch(QtCore.QObject):
        """Calls back on a dock's close (its X), and on the 3D view area's
        resize (the slide-out follows it)."""

        def __init__(self, on_close=None, on_resize=None, parent=None):
            super().__init__(parent)
            self.on_close, self.on_resize = on_close, on_resize

        def eventFilter(self, obj, ev):  # noqa: N802 (Qt)
            t = ev.type()
            if t == QtCore.QEvent.Close and self.on_close:
                self.on_close(obj)
            elif t == QtCore.QEvent.Resize and self.on_resize:
                self.on_resize()
            return False

    class Slide(QtWidgets.QFrame):
        """The slide-out over the left edge of the 3D view: the panels'
        tabs (the tab bar hides itself with one), and a handle on the edge
        that opens and closes it."""

        def __init__(self, area, on_toggle=None, on_open=None):
            super().__init__(area)
            self.on_open = on_open
            self.setObjectName("PanelLayoutSlide")
            self.area = area
            self.on_toggle = on_toggle
            self.setFrameShape(QtWidgets.QFrame.StyledPanel)
            self.setAutoFillBackground(True)
            lay = QtWidgets.QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.tabs = QtWidgets.QTabWidget()
            self.tabs.setTabBarAutoHide(True)
            self.tabs.setUsesScrollButtons(True)
            self.tabs.setElideMode(QtCore.Qt.ElideNone)
            lay.addWidget(self.tabs)
            self.handle = QtWidgets.QToolButton(area)
            self.handle.setObjectName("PanelLayoutHandle")
            self.handle.setAutoRaise(False)
            self.handle.setToolTip("Show or hide the workbench's panel")
            self.handle.clicked.connect(lambda *_: self.toggle())
            self.watch = Watch(on_resize=self.place, parent=self)
            area.installEventFilter(self.watch)
            self.hide()
            self.place()

        def place(self):
            r = self.area.rect()
            w = slide_width(r.width())
            self.setGeometry(0, 0, w, r.height())
            on = self.isVisible()
            self.handle.setText("‹" if on else "›")
            self.handle.setFixedSize(16, 48)
            self.handle.move(w if on else 0, max(0, r.height() // 2 - 24))
            self.handle.setVisible(self.tabs.count() > 0)
            self.handle.raise_()

        def set_open(self, on):
            on = bool(on) and self.tabs.count() > 0
            self.setVisible(on)
            if on:
                self.raise_()
            self.place()
            if self.on_open:
                self.on_open(on)

        def toggle(self):
            self.set_open(not self.isVisible())
            if self.on_toggle:
                self.on_toggle(self.isVisible())

    _CLASSES.update(Watch=Watch, Slide=Slide)
    return _CLASSES


class Placer:
    """Places panels (each a QDockWidget holding the panel) by the setting.
    show() places one for a workbench, hide() takes it away, and a
    workbench switch hides the panels of other workbenches and brings back
    the new one's. A panel closed with its X stays closed until shown
    again by its command."""

    def __init__(self):
        self.entries = {}
        self.memory = Memory()
        self.slide = None
        self.bar = None
        self.timer = None
        self.mw = None
        self.active = None
        self.arrived_in = None
        self._watch = None

    # -- the window ------------------------------------------------------------

    def _main(self):
        if self.mw is None:
            self.mw = _gui().getMainWindow()
            try:
                self.mw.workbenchActivated.connect(self.switched)
            except Exception:  # noqa: BLE001 — a window without the signal: show() alone places
                pass
        return self.mw

    def _watcher(self):
        if self._watch is None:
            self._watch = _classes()["Watch"](on_close=self._closed, parent=self._main())
        return self._watch

    def _closed(self, dock):
        for e in self.entries.values():
            # Closed with its X: on the right, or a dock tabbed with Model.
            if e.get("dock") is dock and (e.get("where") == RIGHT or (e.get("where") == LEFT_TAB and getattr(e.get("bar"), "kind", "") == "docks")):
                e["wanted"] = False

    # -- the API (the same in every add-on's copy) -----------------------------

    def show(self, key, dock, workbench=None, title=None, force=True, front=True, fronts=()):
        """Place dock as key's panel for workbench (None: the active one;
        EVERYWHERE: every workbench). force: shown even if the person closed
        it (a command asked); front: brought forward. fronts: workbenches
        in which an EVERYWHERE panel holds that workbench's own content
        (it comes forward there the first time). Returns where it went."""
        mw = self._main()
        if workbench is None:
            workbench = active_workbench()
        e = self.entries.setdefault(key, {"wanted": True, "where": None})
        e.update(dock=dock, workbench=workbench, title=title or dock.windowTitle(), fronts=set(fronts or ()))
        if force:
            e["wanted"] = True
        if not e["wanted"]:
            return None
        try:
            dock.installEventFilter(self._watcher())
        except Exception:  # noqa: BLE001
            pass
        layout = read()
        before, maxed = (mw.width(), mw.height()), mw.isMaximized() or mw.isFullScreen()
        if e["where"] and e["where"] != layout:
            self._take_back(e)
        if layout == LEFT_TAB:
            self.bar = left_bar(mw)
            if self.bar is None:
                layout = RIGHT  # no Model or Combo View in this window: the right side
        fresh = e["where"] != layout
        # Shown as its workbench opens (the workbench's Activated runs before
        # the switch signal): what comes forward is Memory's choice, and a
        # reveal() that follows is left out.
        now = active_workbench()
        e["arrived"] = fresh and now != self.arrived_in
        self.arrived_in = now
        getattr(self, "_" + layout.replace("-", "_"))(e, front and not fresh)
        if fresh and layout != RIGHT:
            # Newly in the Combo View or the slide-out: forward the first
            # time its workbench opens, after that as the person left it.
            self._front(active_workbench() or self.active)
        elif fresh and front:
            self._right(e, True)
        self._unstick()
        self._keep_size(before, maxed)
        return e["where"]

    def _keep_size(self, before, maxed):
        """The main window kept at its size once the docks settle."""
        QtCore, _w = _qt()
        mw = self._main()

        def back():
            try:
                want = size_to_restore(before, (mw.width(), mw.height()), maxed)
                if want is not None:
                    mw.resize(*want)
            except RuntimeError:  # the window is going away
                pass

        for ms in KEEP_SIZE_MS:
            QtCore.QTimer.singleShot(ms, back)

    def hide(self, key):
        e = self.entries.get(key)
        if not e:
            return
        if e["where"] in (LEFT_TAB, LEFT_SLIDE):
            self._take_back(e)
        try:
            e["dock"].hide()
        except RuntimeError:  # deleted by Qt
            self.entries.pop(key, None)

    def forget(self, key):
        self.hide(key)
        self.entries.pop(key, None)

    def toggle(self, workbench=None):
        """The workbench toolbar's panel button: the slide-out opened or
        closed (left-slide); else the workbench's panels shown and raised."""
        wb = workbench or active_workbench()
        if read() == LEFT_SLIDE and self.slide is not None and self.slide.tabs.count():
            self.slide.toggle()
            return self.slide.isVisible()
        for key in shown(wb, {k: e["workbench"] for k, e in self.entries.items()}):
            e = self.entries[key]
            self.show(key, e["dock"], e["workbench"], e["title"], force=True)
        return True

    def reveal(self, key):
        """key's panel brought into view where it stands."""
        e = self.entries.get(key)
        if not e or not e["where"]:
            return False
        if e.pop("arrived", False) and e["where"] != RIGHT:
            return True
        if e["where"] == LEFT_TAB and self.bar is not None:
            self.bar.front(e)
        elif e["where"] == LEFT_SLIDE and self.slide is not None:
            self.slide.tabs.setCurrentWidget(e["frame"])
            self.slide.set_open(True)
        else:
            e["dock"].show()
            e["dock"].raise_()
        return True

    def switched(self, name=None):
        """A workbench switch: the other workbenches' panels hidden, this
        one's back (if the person had not closed it), and what comes
        forward chosen by Memory."""
        name = str(name) if name else active_workbench()
        self.active = self.arrived_in = name
        for key, e in list(self.entries.items()):
            if not belongs(e["workbench"], name):
                self.hide(key)
        for key, e in list(self.entries.items()):
            if belongs(e["workbench"], name) and e["wanted"]:
                try:
                    self.show(key, e["dock"], e["workbench"], e["title"], force=False, front=False, fronts=e["fronts"])
                except RuntimeError:  # deleted by Qt
                    self.entries.pop(key, None)
        for e in self.entries.values():
            e.pop("arrived", None)
        self._front(name)
        self._unstick()

    def _unstick(self):
        """Model and Tasks left on an empty Tasks (no task running): Model
        in front (in left-tab, Memory's choice first)."""
        bar = self.bar or left_bar(self._main())
        if bar is None:
            return
        titles = bar.titles()
        to = unstick(titles, bar.current(), task_running(), bar.tasks, bar.model)
        if to is None:
            return
        wb = active_workbench() or self.active
        mine = self.memory.last.get(wb) if read() == LEFT_TAB else None
        bar.turn_to(mine if mine in titles and mine != bar.tasks else to)

    def _squeeze(self, on):
        """While the slide-out is open, the Combo View at most
        COMBO_SQUEEZE px wide (the 3D view keeps some width); its width
        back after."""
        QtCore, _w = _qt()
        mw = self._main()
        d = combo_dock(mw)
        if d is None or d.isFloating() or not d.isVisible():
            return
        try:
            if on and d.width() > COMBO_SQUEEZE:
                self._combo_width = d.width()
                mw.resizeDocks([d], [COMBO_SQUEEZE], QtCore.Qt.Horizontal)
            elif not on and getattr(self, "_combo_width", None):
                mw.resizeDocks([d], [self._combo_width], QtCore.Qt.Horizontal)
                self._combo_width = None
        except Exception:  # noqa: BLE001 — an older Qt without resizeDocks
            pass

    # -- placing ---------------------------------------------------------------

    def _ours(self, wb):
        """The title of wb's own panel: an add-on's placed for wb, else an
        EVERYWHERE panel that holds wb's content (fronts)."""
        for e in self.entries.values():
            if e["workbench"] == wb and e["where"]:
                return e["title"]
        for e in self.entries.values():
            if e["where"] and wb in e.get("fronts", ()):
                return e["title"]
        return None

    def _front(self, wb):
        layout = read()
        ours = self._ours(wb)
        if layout == LEFT_TAB and self.bar is not None:
            title = self.memory.opened(wb, ours) if ours else self.memory.last.get(wb)
            if title and not task_running():
                self.bar.turn_to(title)
        elif layout == LEFT_SLIDE and self.slide is not None:
            if ours:
                for e in self.entries.values():
                    if e["title"] == ours and e.get("frame") is not None and e["where"] == LEFT_SLIDE:
                        self.slide.tabs.setCurrentWidget(e["frame"])
            self.slide.set_open(bool(ours) and self.memory.slide_open(wb))

    def _right(self, e, front):
        QtCore, _w = _qt()
        mw, dock = self._main(), e["dock"]
        if e["where"] != RIGHT:
            # In a scroll area that follows the dock's width, as on the left.
            e["frame"] = frame(self._content(e))
            dock.setWidget(e["frame"])
            mw.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
            mates = [x["dock"] for x in self.entries.values() if x is not e and x["where"] == RIGHT
                     and x["dock"].isVisible() and not x["dock"].isFloating()]
            if mates:
                mw.tabifyDockWidget(mates[0], dock)
            e["where"] = RIGHT
        dock.setMaximumWidth(TASK_MAX)
        dock.show()
        if front:
            dock.raise_()

    def _content(self, e):
        """The panel's content taken out of its dock (kept for _take_back)."""
        if e.get("content") is None:
            e["content"] = e["dock"].widget()
        return e["content"]

    def _left_tab(self, e, front):
        mw = self._main()
        bar = self.bar = self.bar or left_bar(mw)
        if e["where"] != LEFT_TAB:
            content = self._content(e)
            e["frame"] = frame(content)
            # A workbench's own panel right after Tasks, Agent Link's
            # (EVERYWHERE) after it: Model | Tasks | Texturizer | Agent Link.
            hub = [] if e["workbench"] == EVERYWHERE else [
                x for x in self.entries.values()
                if x is not e and x["where"] == LEFT_TAB and x["workbench"] == EVERYWHERE
                and getattr(x.get("bar"), "kind", None) == bar.kind]
            was = bar.current() if hub else None
            for x in hub:
                x["bar"].remove(x, mw)
            bar.add(e, mw)
            for x in hub:
                bar.add(x, mw)
                x["bar"] = bar
            if was:
                bar.turn_to(was)
            e["where"], e["bar"] = LEFT_TAB, bar
            bar.watch(lambda title: self.memory.chose(active_workbench() or self.active, title, bar.tasks))
            self._poll()
        if front and not task_running():
            bar.front(e)

    def _left_slide(self, e, front):
        mw = self._main()
        if self.slide is None:
            area = mw.centralWidget()
            self.slide = _classes()["Slide"](area, on_toggle=lambda on: self.memory.slid(active_workbench() or self.active, on),
                                             on_open=self._squeeze)
        if e["where"] != LEFT_SLIDE:
            content = self._content(e)
            e["frame"] = frame(content)
            self.slide.tabs.addTab(e["frame"], e["title"])
            e["dock"].hide()
            e["where"] = LEFT_SLIDE
        if front:
            self.slide.tabs.setCurrentWidget(e["frame"])
            self.slide.set_open(True)
        else:
            self.slide.place()

    def _take_back(self, e):
        """Out of the Combo View or the slide-out, back into its own dock
        (hidden); or off the right side's width cap."""
        where, dock = e["where"], e["dock"]
        if e.get("frame") is not None:
            if where == LEFT_TAB and e.get("bar") is not None:
                e.pop("bar").remove(e, self._main())
            f = e.pop("frame")
            if where == LEFT_SLIDE and self.slide is not None:
                i = self.slide.tabs.indexOf(f)
                if i >= 0:
                    self.slide.tabs.removeTab(i)
            content = f.takeWidget()
            e["content"] = None
            if content is not None:
                dock.setWidget(content)
            f.deleteLater()
            if where == LEFT_SLIDE and self.slide is not None:
                self.slide.set_open(self.slide.isVisible())
        if where == RIGHT:
            dock.setMaximumWidth(16777215)  # QWIDGETSIZE_MAX
        e["where"] = None

    def _poll(self):
        """While a panel is a Combo View tab: when a task ends, the tab
        chosen before it comes back (FreeCAD turns to Model)."""
        if self.timer is not None:
            return
        QtCore, _w = _qt()
        self.timer = QtCore.QTimer(self._main())
        self.timer.setInterval(400)

        def tick():
            if not any(e["where"] == LEFT_TAB for e in self.entries.values()):
                return
            bar = self.bar
            if bar is None:
                return
            # Tasks forward while a task runs; when it ends, what was in
            # front before.
            to = self.memory.task(task_running(), active_workbench() or self.active, bar.tasks)
            if to:
                bar.turn_to(to)

        self.timer.timeout.connect(tick)
        self.timer.start()


_PLACER = []


def own():
    """This module's own placer (one per add-on)."""
    if not _PLACER:
        _PLACER.append(Placer())
    return _PLACER[0]


def placer():
    """Agent Link's placer when it is installed (one place for every
    add-on's panel), else this add-on's own."""
    try:
        import importlib

        got = importlib.import_module("agentlink.hooks").service(SERVICE)
        if got is not None:
            return got
    except Exception:  # noqa: BLE001 — Agent Link not installed
        pass
    return own()


def toggle_or(open_panel, workbench=None):
    """A workbench's Panel button: in left-slide, with the slide-out holding
    a panel, open or close it; else open_panel() (show it where it stands)."""
    p = placer()
    slide = getattr(p, "slide", None)
    if read() == LEFT_SLIDE and slide is not None and slide.tabs.count():
        return p.toggle(workbench)
    return open_panel()


# ---- an add-on's panel beside Agent Link's ----------------------------------

def _hooks():
    import importlib

    return importlib.import_module("agentlink.hooks")


def hosted_tabs(hooks):
    """Whether an add-on's page goes in Agent Link's panel as a tab: only
    for an Agent Link that cannot place the add-on's own dock (no
    "panel_layout" service: headless, or before panel layouts). Otherwise
    the page is the add-on's own dock, beside Model and Tasks."""
    service = getattr(hooks, "service", None)
    return service is None or service(SERVICE) is None


def in_agentlink_panel(title):
    """Whether Agent Link's panel has a tab title (an older Agent Link
    hosting the add-on's page)."""
    try:
        return any(t.get("title") == title for t in _hooks().TABS)
    except Exception:  # noqa: BLE001 — Agent Link not installed
        return False


def caller():
    """Agent Link's "panel_caller": an add-on's own dock runs its tools
    through it (shown and logged as the agent's are) with _call(tool,
    args), and reads its session (_own). None without Agent Link."""
    try:
        return _hooks().service("panel_caller")
    except Exception:  # noqa: BLE001
        return None
