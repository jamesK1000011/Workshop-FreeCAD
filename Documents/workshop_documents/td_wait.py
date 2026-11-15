# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's td_wait.py, trimmed to what Documents uses; 14 Nov 2026.
"""TechDraw helpers FreeCAD add-ons share (moved from Agent Link for FreeCAD
on 14 Nov 2026). Needs FreeCAD's TechDraw; Qt only when there is no window."""


def wait_views(views_, timeout=30.0):
    """TechDraw works out a view's lines on another thread and takes them up
    when Qt's event loop says it is done; with no window nothing runs that
    loop, so it is run here until every view has its lines. Seconds waited,
    or None when they were there at once."""
    import time

    def ready():
        try:
            return all(v.getVisibleEdges() for v in views_)
        except Exception:
            return False

    if ready():
        return None
    try:
        from PySide import QtCore
    except ImportError:
        try:
            from PySide2 import QtCore
        except ImportError:
            return None
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if ready():
            break
        time.sleep(0.02)
    for v in views_:
        try:
            v.recompute()
        except Exception:
            pass
    return round(time.time() - t0, 2)
