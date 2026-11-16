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


def _pump():
    """One turn of the event loop: FreeCAD's window when it is up (its
    scene redrawn), else a Qt core loop. False when there is no Qt."""
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


def views_ready(views_, timeout=30.0, pump=None, sleep=0.02):
    """Waits until every view's lines are worked out: a view with a change
    not yet recomputed is recomputed once (never one that is ready: that
    starts its lines afresh), and the event loop is run until none is
    waiting and each has edges, or timeout seconds. Then a few more turns
    so the window's scene draws them. {"seconds": waited, "notReady":
    [{"view", "why"}]} (notReady empty when all are ready)."""
    pump = pump or _pump
    views_ = list(views_)
    t0 = time.time()
    redone = set()
    while True:
        busy = [(v, view_busy(v)) for v in views_]
        busy = [(v, why) for v, why in busy if why]
        if not busy:
            break
        if all(why == "touched" and id(v) in redone for v, why in busy):
            # Recomputed once and still changed: it will not settle.
            break
        for v, why in busy:
            if why == "touched" and id(v) not in redone:
                redone.add(id(v))
                try:
                    v.recompute()
                except Exception:  # noqa: BLE001
                    pass
        if time.time() - t0 >= timeout:
            break
        if not pump():
            # No event loop to run: nothing more will arrive.
            break
        time.sleep(sleep)
    for _ in range(3):
        if not pump():
            break
    left = [{"view": getattr(v, "Label", getattr(v, "Name", "?")), "why": view_busy(v)} for v in views_]
    return {"seconds": round(time.time() - t0, 2), "notReady": [x for x in left if x["why"]]}


def wait_views(views_, timeout=30.0):
    """views_ready's seconds, or None when every view was ready at once
    (as before, for callers that only wait)."""
    got = views_ready(views_, timeout)
    return got["seconds"] if got["seconds"] >= 0.05 or got["notReady"] else None
