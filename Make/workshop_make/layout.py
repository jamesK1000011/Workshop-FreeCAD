# SPDX-License-Identifier: LGPL-2.1-or-later
# Where a workbench's panel stands. One setting for every add-on of the
# suite, read by each add-on itself (each carries its own copy of this small
# module, with the same API):
#
#   User parameter:BaseApp/Preferences/Mod/AgentLink, PanelLayout =
#     right       the panel docks on the right (at most 360 px wide); the
#                 left side stays the model tree
#     left-tab    the panel is a tab of the Combo View beside Model and
#                 Tasks while its workbench is active
#     left-slide  the panel slides out over the left edge of the 3D view,
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
DEFAULT = RIGHT
# Logical pixels: the tree side, and the side a task panel stands on.
TREE_MAX, TASK_MAX = 300, 360
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
    """The layout the setting asks for now ("right" when unset or unknown)."""
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
    return TASK_MAX if normalise(layout) in (RIGHT, LEFT_SLIDE) else TREE_MAX


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

    def chose(self, wb, title):
        """The person turned to title in wb (ignored while a task runs:
        FreeCAD turns the tabs itself to Tasks and back to Model)."""
        if self.running or not title or title == TASKS:
            return
        self.last[wb] = title

    def task(self, running, wb):
        """Called as the task state is polled: the tab to hand back to when
        a task has just ended, else None."""
        was, self.running = self.running, bool(running)
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


def combo_tabs(mw):
    """The Combo View's tab widget (Model, Tasks), or None when this
    FreeCAD shows the tree and the tasks apart."""
    _c, QtWidgets = _qt()
    for d in mw.findChildren(QtWidgets.QDockWidget):
        if d.objectName() in ("Combo View", "ComboView"):
            t = d.findChild(QtWidgets.QTabWidget, "combiTab")
            if t is None:
                kids = d.findChildren(QtWidgets.QTabWidget)
                t = kids[0] if kids else None
            if t is not None:
                return t
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

        def __init__(self, area, on_toggle=None):
            super().__init__(area)
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
            w = min(TASK_MAX, max(220, r.width() // 2))
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
        self.combo = None
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
            if e.get("dock") is dock and e.get("where") == RIGHT:
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
        if layout == LEFT_TAB and combo_tabs(mw) is None:
            layout = RIGHT  # no Combo View in this window: the right side
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
        if e["where"] == LEFT_TAB and self.combo is not None:
            self.combo.setCurrentWidget(e["frame"])
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
        if layout == LEFT_TAB and self.combo is not None:
            title = self.memory.opened(wb, ours) if ours else self.memory.last.get(wb)
            if title and not task_running():
                self._turn_to(title)
        elif layout == LEFT_SLIDE and self.slide is not None:
            if ours:
                for e in self.entries.values():
                    if e["title"] == ours and e.get("frame") is not None and e["where"] == LEFT_SLIDE:
                        self.slide.tabs.setCurrentWidget(e["frame"])
            self.slide.set_open(bool(ours) and self.memory.slide_open(wb))

    def _turn_to(self, title):
        t = self.combo
        for i in range(t.count()):
            if t.tabText(i) == title:
                t.setCurrentIndex(i)
                return True
        return False

    def _right(self, e, front):
        QtCore, _w = _qt()
        mw, dock = self._main(), e["dock"]
        if e["where"] != RIGHT:
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
        tabs = self.combo = combo_tabs(mw)
        if e["where"] != LEFT_TAB:
            content = self._content(e)
            e["frame"] = frame(content)
            tabs.addTab(e["frame"], e["title"])
            e["dock"].hide()
            e["where"] = LEFT_TAB
            # A Qt property: FreeCAD's tab widget may come back in a new
            # Python wrapper, which would not keep a Python attribute.
            if not tabs.property("panelLayout"):
                tabs.currentChanged.connect(lambda i: self.memory.chose(active_workbench() or self.active, tabs.tabText(i)))
                tabs.setProperty("panelLayout", True)
            self._poll()
        if front and not task_running():
            tabs.setCurrentWidget(e["frame"])

    def _left_slide(self, e, front):
        mw = self._main()
        if self.slide is None:
            area = mw.centralWidget()
            self.slide = _classes()["Slide"](area, on_toggle=lambda on: self.memory.slid(active_workbench() or self.active, on))
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
        if where in (LEFT_TAB, LEFT_SLIDE) and e.get("frame") is not None:
            holder = self.combo if where == LEFT_TAB else (self.slide.tabs if self.slide else None)
            f = e.pop("frame")
            if holder is not None:
                i = holder.indexOf(f)
                if i >= 0:
                    holder.removeTab(i)
            content = f.takeWidget()
            e["content"] = None
            if content is not None:
                dock.setWidget(content)
            f.deleteLater()
            if where == LEFT_SLIDE and self.slide is not None:
                self.slide.set_open(self.slide.isVisible())
        elif where == RIGHT:
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
            back = self.memory.task(task_running(), active_workbench() or self.active)
            if back and self.combo is not None:
                self._turn_to(back)

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
