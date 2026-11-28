# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's td_wait.py, trimmed to what Documents uses; 14 Nov 2026.
"""TechDraw helpers FreeCAD add-ons share (moved from Agent Link for FreeCAD
on 14 Nov 2026). Needs FreeCAD's TechDraw; Qt only when there is no window."""

import time

# What a TechDraw view says while its lines are still being worked out on
# another thread; each release names it its own way, so every name found
# is asked (1.1: waitingForHlr / waitingForResult in C++, some exposed).
BUSY_CALLS = ("isWaitingForHlr", "waitingForHlr", "waitingForResult", "isWaitingForResult", "waitingForFaces")


def view_busy(v):
    """Why view v is not ready to place dimensions on or export: "touched"
    (a change not yet recomputed: TechDraw starts its lines afresh when it
    is), "waiting" (its lines are being worked out), "no edges", or None
    when it is ready. Its old lines stay readable while new ones are worked
    out, so having edges alone never meant ready: a page exported then
    held the dimensions with no views under them."""
    try:
        state = list(getattr(v, "State", []) or [])
    except Exception:  # noqa: BLE001
        state = []
    if "Touched" in state:
        return "touched"
    if "Recompute" in state:
        return "waiting"
    for name in BUSY_CALLS:
        fn = getattr(v, name, None)
        if callable(fn):
            try:
                if fn():
                    return "waiting"
            except Exception:  # noqa: BLE001
                continue
    try:
        if not v.getVisibleEdges():
            return "no edges"
    except Exception:  # noqa: BLE001
        return "no edges"
    return None


# Over 0 while a turn of the event loop runs from here: what TechDraw does
# then (a view's lines arriving from their thread, and what it recomputes
# after them) is told apart from what a call does itself (PageExport).
_TURNING = [0]
# Every turn of the event loop run from here, counted and timed: [turns,
# seconds inside them]. A turn runs whatever the window has waiting, not
# only TechDraw's work, so what a wait costs is the turns it ran and how
# long each took; an answer that gives both (turns_since) tells a wait
# that needed many turns from a window that is slow to turn. Found live
# (run 3): drawing_make took 4.6 and 5.7 s where it had taken 0.8 s, with
# 2 to 2.6 s that no field of the answer accounted for.
_TURNS = [0, 0.0]


def turns_now():
    """A mark for turns_since: the turns run so far and their time."""
    return (_TURNS[0], _TURNS[1])


def turns_since(mark):
    """{ turns, turnMs }: the turns of the event loop run from this module
    since mark (turns_now) and the milliseconds spent inside them."""
    return {"turns": _TURNS[0] - mark[0], "turnMs": int(round((_TURNS[1] - mark[1]) * 1000))}


def _counted(fn):
    _TURNING[0] += 1
    t0 = time.perf_counter()
    try:
        return fn()
    finally:
        _TURNING[0] -= 1
        _TURNS[0] += 1
        _TURNS[1] += time.perf_counter() - t0


def _pump():
    """One turn of the event loop: FreeCAD's window when it is up (its
    scene redrawn), else a Qt core loop. False when there is no Qt."""
    return _counted(_pump_once)


def _pump_once():
    try:
        import FreeCAD

        if getattr(FreeCAD, "GuiUp", False):
            import FreeCADGui

            FreeCADGui.updateGui()
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from PySide import QtCore
    except ImportError:
        try:
            from PySide2 import QtCore
        except ImportError:
            return False
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    app.processEvents()
    return True


def _turn(pump):
    """pump() counted as a turn of the event loop (a pump of the caller's
    own, as the tests give one)."""
    if pump is _pump:
        return pump()
    return _counted(pump)


def view_limit(edges, coarse=False):
    """How long one view may take to be drawn, seconds: 30 s, and more for
    a view of many edges (TechDraw's hidden-line removal grows with them),
    240 s at most; a coarse view (TechDraw's faster polygon lines) 120 s at
    most. Found live (the bicycle, FreeCAD 1.1.3): the front view had no
    edges after the 30 s that every view had, so its overall dimensions
    were not placed."""
    try:
        n = max(0, int(edges))
    except (TypeError, ValueError):
        n = 0
    if coarse:
        return round(min(120.0, 30.0 + 0.005 * n), 1)
    return round(min(240.0, 30.0 + 0.015 * n), 1)


def views_ready(views_, timeout=30.0, pump=None, sleep=0.02, draw=True, limits=None, on_ready=None):
    """Waits until every view's lines are worked out: a view with a change
    not yet recomputed is recomputed once (never one that is ready: that
    starts its lines afresh), and the event loop is run until none is
    waiting and each has edges, or timeout seconds. Then a few more turns
    so the window's scene draws them — left out with draw: False, for a
    caller that only asks whether the views are ready and either needs no
    scene (a dimension is placed on a view's geometry, not on its picture)
    or readies the scene itself straight after (the export does:
    drawing.page_scene_ready). {"seconds": waited, "notReady": [{"view",
    "why", "limit"?}]} (notReady empty when all are ready).

    limits: each view's own time limit, seconds (a list beside views_;
    view_limit gives one), in place of timeout for all: the wait goes on
    while a view not ready is within its own limit. on_ready(v): called
    once for each view as soon as it is ready, while the others are still
    waited for (a view's dimensions go on it then, not after the last
    view)."""
    pump = pump or _pump
    views_ = list(views_)
    lim = list(limits) if limits is not None else []
    lim = [float(lim[i]) if i < len(lim) and lim[i] is not None else float(timeout) for i in range(len(views_))]
    t0 = time.time()
    redone = set()
    told = set()

    def tell(v):
        if on_ready is not None and id(v) not in told:
            told.add(id(v))
            on_ready(v)

    while True:
        states = [(i, v, view_busy(v)) for i, v in enumerate(views_)]
        for _i, v, why in states:
            if not why:
                tell(v)
        busy = [(i, v, why) for i, v, why in states if why]
        if not busy:
            break
        if all(why == "touched" and id(v) in redone for _i, v, why in busy):
            # Recomputed once and still changed: it will not settle.
            break
        for _i, v, why in busy:
            if why == "touched" and id(v) not in redone:
                redone.add(id(v))
                try:
                    v.recompute()
                except Exception:  # noqa: BLE001
                    pass
        took = time.time() - t0
        if all(took >= lim[i] for i, _v, _w in busy):
            break
        if not _turn(pump):
            # No event loop to run: nothing more will arrive.
            break
        time.sleep(sleep)
    for _ in range(3 if draw else 0):
        if not _turn(pump):
            break
    left = []
    for i, v in enumerate(views_):
        why = view_busy(v)
        if why:
            left.append({"view": getattr(v, "Label", getattr(v, "Name", "?")), "why": why, **({"limit": lim[i]} if limits is not None else {})})
        else:
            tell(v)
    return {"seconds": round(time.time() - t0, 2), "notReady": left}


def wait_views(views_, timeout=30.0):
    """views_ready's seconds, or None when every view was ready at once
    (as before, for callers that only wait)."""
    got = views_ready(views_, timeout)
    return got["seconds"] if got["seconds"] >= 0.05 or got["notReady"] else None


# ---- what an export leaves marked ----------------------------------------------------------
# Found live (run 2): the call after a drawing_make read "6 objects not
# recomputed yet" — the page's template and its five dimensions — though
# nothing on the page was out of date. What marks them, from FreeCAD 1.1's
# source (tag 1.1.0; the Mac runs 1.1.3):
#
# The template. Every time TechDraw's window draws a page's template it
#   re-reads the SVG and writes its size back into the template object:
#   QGISVGTemplate::draw and createClickHandles (src/Mod/TechDraw/Gui/
#   QGISVGTemplate.cpp) call DrawSVGTemplate::processTemplate, which ends in
#   extractTemplateAttributes: Width.setValue, Height.setValue,
#   Orientation.setValue (src/Mod/TechDraw/App/DrawSVGTemplate.cpp). They
#   are input properties, and a property set, even to the value it has,
#   marks its object changed (src/App/DocumentObject.cpp, onChanged). The
#   template is drawn when the page's tab is first shown
#   (ViewProviderPage::showMDIViewPage) and by both exports
#   (QGSPage::saveSvg and PagePrinter::renderPage call
#   ViewProviderPage::setTemplateMarkers(false), which draws it).
#
# The dimensions. PagePrinter::printPdf ends with DrawPage::redrawCommand
#   (src/Mod/TechDraw/Gui/PagePrinter.cpp): DrawPage::updateAllViews
#   recomputes every part view by itself — its lines start afresh on
#   another thread — and then every other view by itself. A dimension that
#   executes checks its references against the geometry it saved
#   (DrawViewDimension::execute, autocorrectReferences). The saved geometry
#   is unscaled (ReferenceEntry::asCanonicalTopoShape) and the check reads
#   the view's geometry as drawn, scaled and rotated
#   (DimensionAutoCorrect::isMatchingGeometry, ReferenceEntry::getGeometry),
#   so on a view at any scale but 1:1 they never match: the "repair" finds
#   the very same vertex or edge and writes References2D again
#   (setReferences2d), with SavedGeometry and BoxCorners after it. Inside a
#   document recompute the mark is taken off when the object is done
#   (Document::recompute, purgeTouched); an object recomputed by itself
#   keeps it (Document::recomputeFeature). And when a restarted view's
#   lines and faces are done — a turn of the event loop later, so often
#   after the call has answered — TechDraw recomputes that view's
#   dimensions by themselves once more (DrawViewPart::postHlrTasks,
#   postFaceExtractionTasks): marked again.
#
# So nothing here is out of date, and recomputing each object by itself
# (what this module did first) cannot take the mark off: that is the very
# call that leaves it. PageExport watches the export, waits for the
# dimensions TechDraw will recompute once more, and takes the mark off
# (purgeTouched: no execute) only where everything written to the object
# since the export began is one of TechDraw's own writes named above.
# Anything else — a mark from before, a position or a text changed — stays
# for the health check to say.

OWN_WRITES = (
    ("Template", frozenset({"Width", "Height", "Orientation"})),
    ("DrawViewDimension", frozenset({"References2D", "References3D", "SavedGeometry", "BoxCorners"})),
)
SETTLE_TIMEOUT = 30.0
QUIET_TURNS = 3


def own_writes(o):
    """The properties TechDraw itself writes on o when it draws or
    re-reads it (OWN_WRITES), by its type; empty for any other object."""
    kind = str(getattr(o, "TypeId", "") or "")
    for word, props in OWN_WRITES:
        if word in kind:
            return props
    return frozenset()


def _marked(o):
    try:
        return "Touched" in list(getattr(o, "State", []) or [])
    except Exception:  # noqa: BLE001 — an object already gone
        return False


def _is_part_view(o):
    return hasattr(o, "getVisibleEdges")


class _Watch:
    """A FreeCAD document observer that keeps, in order, what was written
    to and what was recomputed in one document: ("changed", name, property,
    in a turn) and ("recomputed", name, None, in a turn) — in a turn: it
    happened while the event loop ran from this module (_TURNING), which is
    when a view's lines arrive and TechDraw recomputes what hangs on it."""

    def __init__(self, doc_name):
        self.doc_name = doc_name
        self.log = []

    def _mine(self, obj):
        try:
            return obj.Document.Name == self.doc_name
        except Exception:  # noqa: BLE001
            return False

    def slotChangedObject(self, obj, prop):
        if self._mine(obj):
            self.log.append(("changed", obj.Name, str(prop), _TURNING[0] > 0))

    def slotRecomputedObject(self, obj):
        if self._mine(obj):
            self.log.append(("recomputed", obj.Name, None, _TURNING[0] > 0))


class PageExport:
    """Round a page's export:

        with PageExport(page) as px:
            ... TechDrawGui.exportPageAsSvg / exportPageAsPdf ...
        px.settled  # { cleared, waited, exportMs, turns, turnMs, seen, late?, left? }

    On leaving, the page is settled (settle, below). With no FreeCAD
    observer to watch with (a stand-in), nothing is waited for and nothing
    cleared: settled is { cleared: [], waited: 0.0, unwatched: true,
    exportMs }. An export that raises is not settled (settled stays None)
    and the exception goes on.

    Where the time went is in the answer: exportMs, what ran inside the
    with (the export itself, whatever it waited for before); waited, the
    seconds after it; turns and turnMs, the turns of the event loop that
    wait ran and the milliseconds inside them (the rest of waited is the
    pause between turns, `sleep` each); seen { changed, recomputed }, how
    many property writes and recomputes of the page's document were
    watched — each one a call into Python while the watch is on."""

    def __init__(self, page, timeout=SETTLE_TIMEOUT, pump=None, sleep=0.02):
        self.page, self.timeout, self.pump, self.sleep = page, timeout, pump, sleep
        self.watch = None
        self.before = set()
        self.settled = None
        self.entered = None

    def _objects(self):
        """(part views, everything else of the page: template, dimensions,
        balloons, notes, the page itself)."""
        page = self.page
        try:
            views = list(getattr(page, "Views", None) or [])
            tpl = getattr(page, "Template", None)
        except Exception:  # noqa: BLE001
            return [], []
        parts = [v for v in views if _is_part_view(v)]
        rest = [o for o in [tpl] + [v for v in views if not _is_part_view(v)] + [page] if o is not None]
        return parts, rest

    def __enter__(self):
        _parts, rest = self._objects()
        self.before = {getattr(o, "Name", "?") for o in rest if _marked(o)}
        try:
            import FreeCAD

            w = _Watch(self.page.Document.Name)
            FreeCAD.addDocumentObserver(w)
            self.watch = w
        except Exception:  # noqa: BLE001 — nothing to watch with: nothing is cleared
            self.watch = None
        self.entered = time.perf_counter()
        return self

    def __exit__(self, kind, _value, _tb):
        try:
            if kind is None:
                export_ms = int(round((time.perf_counter() - self.entered) * 1000)) if self.entered is not None else None
                self.settled = self.settle()
                if export_ms is not None:
                    self.settled["exportMs"] = export_ms
        finally:
            if self.watch is not None:
                try:
                    import FreeCAD

                    FreeCAD.removeDocumentObserver(self.watch)
                except Exception:  # noqa: BLE001
                    pass
        return False

    def settle(self):
        """After the export: waits for the dimensions TechDraw recomputes
        once more when a view the export restarted has its lines again,
        then takes the changed mark off what only TechDraw's own writes
        marked. { cleared: [names], waited: seconds, late: [dimensions not
        seen recomputed again within the timeout: a mark may still arrive
        after the call], left: [{ object, why }] (marked, and not
        cleared) }; late and left only when there are any. Also turns and
        turnMs (the event loop's turns during the wait and the time inside
        them) and seen { changed, recomputed } (what the watch was told of
        since the export began)."""
        if self.watch is None:
            return {"cleared": [], "waited": 0.0, "unwatched": True}
        pump = self.pump or _pump
        log = self.watch.log
        parts, rest = self._objects()
        t0 = time.time()
        mark = turns_now()
        # The part views recomputed while the export was watched (by the
        # PDF export's redraw, or by the wait for the views before it):
        # each works its lines out afresh on another thread (a coarse view
        # does it at once), and when they are there — in a turn of the
        # event loop — TechDraw recomputes its dimensions once more.
        restarted = {}
        for v in parts:
            try:
                coarse = bool(getattr(v, "CoarseView", False))
            except Exception:  # noqa: BLE001
                coarse = False
            last = max((i for i, (what, name, _p, _t) in enumerate(log) if what == "recomputed" and name == v.Name), default=None)
            if last is not None and not coarse:
                restarted[v.Name] = last
        waiting = {}
        for o in rest:
            if "DrawViewDimension" not in str(getattr(o, "TypeId", "") or ""):
                continue
            try:
                on = [x.Name for x in (getattr(o, "OutList", None) or [])]
            except Exception:  # noqa: BLE001
                on = []
            since = [restarted[n] for n in on if n in restarted]
            if since:
                waiting[o.Name] = max(since)

        def unseen():
            return [n for n, since in waiting.items()
                    if not any(what == "recomputed" and name == n and turn for what, name, _p, turn in log[since + 1:])]

        while unseen() and time.time() - t0 < self.timeout:
            if not _turn(pump):
                break  # no event loop: nothing more will arrive
            time.sleep(self.sleep)
        late = unseen()
        if restarted:
            for _ in range(QUIET_TURNS):  # what the last view's end still has queued
                if not _turn(pump):
                    break
        cleared, left = [], []
        for o in rest:
            if not _marked(o):
                continue
            name = getattr(o, "Name", "?")
            if name in self.before:
                left.append({"object": name, "why": "changedBefore"})
                continue
            written = {p for what, n, p, _t in log if what == "changed" and n == name}
            other = sorted(written - own_writes(o))
            if not written:
                left.append({"object": name, "why": "nothingWritten"})
            elif other:
                left.append({"object": name, "why": "changedDuring", "props": other})
            elif not callable(getattr(o, "purgeTouched", None)):
                left.append({"object": name, "why": "noPurge"})
            else:
                try:
                    o.purgeTouched()
                    cleared.append(name)
                except Exception as e:  # noqa: BLE001
                    left.append({"object": name, "why": "purgeFailed", "error": str(e)})
        out = {"cleared": cleared, "waited": round(time.time() - t0, 2), **turns_since(mark),
               "seen": {"changed": sum(1 for e in log if e[0] == "changed"), "recomputed": sum(1 for e in log if e[0] == "recomputed")}}
        if late:
            out["late"] = late
        if left:
            out["left"] = left
        return out


# ---- Documents' reading for the shared health check --------------------------------------

HEALTH_OWNER = "workshop_documents"
HEALTH_PAGES = 8   # pages looked at per call
HEALTH_VIEWS = 12  # views asked whether they are drawn (the check has a time budget)
PAGE_TYPE = "TechDraw::DrawPage"


def page_reading(session, tool, changed):
    """The drawing pages' state after a changing call, for Agent Link's
    shared health check (health.register(owner, fn): fn(session, tool,
    changed) -> [{ line, red, todo }]). Only reads:

    - a page with no template (its exports have no frame or title block);
    - a view whose source is gone (the body it drew was deleted): red, it
      draws nothing and its dimensions hang on nothing;
    - a view the call recomputed, or whose source it recomputed, that
      TechDraw has not drawn yet (its lines are worked out on another
      thread): an export now would hold the dimensions with no views
      under them.

    No Agent Link import here: families.py registers it."""
    doc = getattr(session, "doc", None)
    if doc is None:
        return []
    try:
        pages = [o for o in doc.Objects if getattr(o, "TypeId", "") == PAGE_TYPE][:HEALTH_PAGES]
    except Exception:  # noqa: BLE001
        return []
    touched = {id(o) for o in changed or []}
    out, asked = [], 0
    for p in pages:
        try:
            if p.Template is None:
                out.append({"line": f"drawing page {p.Label} has no template", "red": False})
            vs = list(p.Views or [])
        except Exception:  # noqa: BLE001
            continue
        for v in vs:
            if not hasattr(v, "Source") or not hasattr(v, "getVisibleEdges"):
                continue  # a dimension, a balloon, an annotation
            try:
                src = list(v.Source or []) + list(getattr(v, "XSource", None) or [])
            except Exception:  # noqa: BLE001
                continue
            if not src:
                out.append({"line": f"view {v.Label} on page {p.Label} has no source in the document", "red": True})
                continue
            if asked >= HEALTH_VIEWS or not (id(v) in touched or any(id(x) in touched for x in src)):
                continue
            asked += 1
            busy = view_busy(v)
            if busy:
                out.append({"line": f"view {v.Label} on page {p.Label} is not drawn yet ({busy})", "red": False})
    return out

