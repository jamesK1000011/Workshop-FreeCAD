# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' colours for its own widgets, its own copy (no shared library).
Text and surfaces come from the widget's palette, so they follow whatever
stylesheet is on. The accent is FreeCAD's theme accent
(Preferences/Themes ThemeAccentColor1..3, set by FreeCAD's themes and the
Studio packs), else the palette's highlight. ok, warn and bad are fixed hues
that read on light and dark. Styles go only on our own widgets, by object
name, never on the application."""

PARAMS = "User parameter:BaseApp/Preferences/Themes"
FIXED = {"ok": "#3fae5a", "warn": "#e0a020", "bad": "#d94a4a"}


def hex_of(packed):
    """FreeCAD's packed 0xRRGGBBAA colour as '#rrggbb', or None for 0/unset."""
    try:
        v = int(packed)
    except (TypeError, ValueError):
        return None
    return "#%06x" % ((v >> 8) & 0xFFFFFF) if v else None


def accents(get=None):
    """[accent1, accent2, accent3] as '#rrggbb' or None. get(name) -> the
    packed value (FreeCAD's parameters by default)."""
    if get is None:
        try:
            import FreeCAD

            g = FreeCAD.ParamGet(PARAMS)
            get = lambda n: g.GetUnsigned(n, 0)  # noqa: E731
        except Exception:
            return [None, None, None]
    return [hex_of(get(f"ThemeAccentColor{k}")) for k in (1, 2, 3)]


def _mix(a, b, t):
    return "#%02x%02x%02x" % tuple(int(x * (1 - t) + y * t) for x, y in zip(a, b))


def roles(widget=None, get=None):
    """{accent, accent2, accent3, muted, ok, warn, bad} for a widget."""
    out = dict(FIXED)
    a = accents(get)
    hi, muted = None, "#808080"
    if widget is not None:
        try:
            from PySide import QtGui

            pal = widget.palette()
            hi = pal.color(QtGui.QPalette.Highlight).name()
            t, b = pal.color(QtGui.QPalette.WindowText), pal.color(QtGui.QPalette.Window)
            muted = _mix((t.red(), t.green(), t.blue()), (b.red(), b.green(), b.blue()), 0.4)
        except Exception:
            pass
    out["accent"] = a[0] or hi or "#3a7bd5"
    out["accent2"] = a[1] or out["accent"]
    out["accent3"] = a[2] or out["accent"]
    out["muted"] = muted
    return out


def fill(css, r):
    """css with each @role replaced by its colour (longest names first)."""
    for k in sorted(r, key=len, reverse=True):
        css = css.replace("@" + k, r[k])
    return css


def style(widget, name, css):
    """css (with @accent, @muted, @ok … for the roles and #SELF for the
    widget) on our own widget, selected by its object name; restyled when
    the palette changes (a pack applied)."""
    widget.setObjectName(name)

    busy = []

    def apply():
        # setStyleSheet sends a PaletteChange of its own: a change met while
        # applying is ignored, so a sheet whose colours move the palette
        # cannot recurse (it did in Texturizer's copy, crashing FreeCAD).
        if busy:
            return
        text = fill(css, roles(widget)).replace("#SELF", "#" + name)
        if widget.styleSheet() != text:
            busy.append(1)
            try:
                widget.setStyleSheet(text)
            finally:
                busy.clear()

    apply()
    try:
        from PySide import QtCore

        class _Follow(QtCore.QObject):
            def eventFilter(self, obj, ev):
                if ev.type() == QtCore.QEvent.PaletteChange:
                    apply()
                return False

        widget._theme_follow = _Follow(widget)
        widget.installEventFilter(widget._theme_follow)
    except Exception:
        pass
