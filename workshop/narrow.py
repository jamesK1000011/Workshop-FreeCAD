# SPDX-License-Identifier: LGPL-2.1-or-later
"""Forms that fit FreeCAD's Tasks dock and the panels beside the model tree.

The dock is about 330-360 logical px wide on a Mac; a form wider than that
runs off its right edge and clips the task dialog's OK button (live on
FreeCAD 1.1.3: Hole for Hardware). Every Workshop form fits
WIDTH: long labels wrap, a combo asks for a few characters rather than its
longest entry (the rest elided, the full entry in its list), a form puts a
long row's label above its field, and nothing sets a fixed width.

No FreeCAD import; Qt only inside the calls, so the module loads anywhere.
Each call quietly does nothing on a Qt (or a stand-in) without the setting."""

WIDTH = 320  # the narrowest Tasks dock a form must fit, logical px
CHARS = 8    # what a combo asks room for, in characters (Qt's "X" widths)


def _qt():
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets
    return QtWidgets


def _enum(owner, group, name):
    """owner.group.name (Qt 6 scoped enums), else owner.name (Qt 5)."""
    g = getattr(owner, group, None)
    v = getattr(g, name, None) if g is not None else None
    return v if v is not None else getattr(owner, name)


def combo(w, chars=CHARS):
    """A combo that asks for chars characters of room, not its longest
    entry, and takes the width the form gives it."""
    Q = _qt()
    try:
        w.setSizeAdjustPolicy(_enum(Q.QComboBox, "SizeAdjustPolicy", "AdjustToMinimumContentsLengthWithIcon"))
        w.setMinimumContentsLength(chars)
    except Exception:  # noqa: BLE001 — a Qt without it
        pass
    grow(w)
    return w


def grow(w):
    """Expanding across, fixed in height (spin boxes, line edits, combos)."""
    Q = _qt()
    try:
        P = Q.QSizePolicy
        w.setSizePolicy(_enum(P, "Policy", "Expanding"), _enum(P, "Policy", "Fixed"))
    except Exception:  # noqa: BLE001
        pass
    return w


def label(w):
    """A label that wraps at the dock's width."""
    try:
        w.setWordWrap(True)
    except Exception:  # noqa: BLE001
        pass
    return w


def form(lay):
    """A form for a narrow dock: a long row puts its label above its field;
    fields take the width there is."""
    Q = _qt()
    try:
        F = Q.QFormLayout
        lay.setRowWrapPolicy(_enum(F, "RowWrapPolicy", "WrapLongRows"))
        lay.setFieldGrowthPolicy(_enum(F, "FieldGrowthPolicy", "AllNonFixedFieldsGrow"))
    except Exception:  # noqa: BLE001
        pass
    return lay
