# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's colours, read from the theme the person chose: accents from
# FreeCAD's theme parameters (ThemeAccentColor1..3, set by FreeCAD's own
# themes and the Studio packs), else the palette's highlight; text and
# surfaces from the widget's palette. Styles go only on SafetyNet's own
# widgets, by object name, and follow a palette change. Never a global
# stylesheet. SafetyNet's own copy: no shared library.
import xml.etree.ElementTree as ET

PARAM = "User parameter:BaseApp/Preferences/Themes"
ACCENTS = ("ThemeAccentColor1", "ThemeAccentColor2", "ThemeAccentColor3")
# Fixed hues that read on light and dark surfaces alike.
FIXED = {"ok": "#2e9e5b", "warn": "#c98a12", "bad": "#d0453a"}


def hex_of(u):
    """FreeCAD's packed colour (0xRRGGBBAA) as #rrggbb; None for 0 or junk."""
    try:
        u = int(u)
    except (TypeError, ValueError):
        return None
    if u <= 0 or u > 0xFFFFFFFF:
        return None
    return "#%06x" % (u >> 8)


def _from_cfg(path):
    """The accents in a parameter file (user.cfg or a pack's .cfg)."""
    out = {}
    for el in ET.parse(path).getroot().iter("FCUInt"):
        if el.get("Name") in ACCENTS:
            out[el.get("Name")] = el.get("Value")
    return out


def accents(params=None):
    """[accent1, accent2, accent3], each #rrggbb or None. params: a
    parameter group (anything with GetUnsigned) or a .cfg path; FreeCAD's
    own by default."""
    if isinstance(params, str):
        raw = _from_cfg(params)
        return [hex_of(raw.get(n)) for n in ACCENTS]
    if params is None:
        try:
            import FreeCAD

            params = FreeCAD.ParamGet(PARAM)
        except Exception:
            return [None, None, None]
    out = []
    for n in ACCENTS:
        try:
            out.append(hex_of(params.GetUnsigned(n, 0)))
        except Exception:
            out.append(None)
    return out


def muted(widget):
    """Text blended towards the background: quiet, readable in light and dark."""
    from PySide import QtGui

    pal = widget.palette()
    t, b = pal.color(QtGui.QPalette.WindowText), pal.color(QtGui.QPalette.Window)
    return "#%02x%02x%02x" % (int(t.red() * 0.6 + b.red() * 0.4), int(t.green() * 0.6 + b.green() * 0.4), int(t.blue() * 0.6 + b.blue() * 0.4))


def roles(widget=None, params=None):
    """{accent, accent2, accent3, muted, ok, warn, bad} as #rrggbb."""
    a = accents(params)
    hl = None
    if widget is not None:
        try:
            from PySide import QtGui

            hl = widget.palette().color(QtGui.QPalette.Highlight).name()
        except Exception:
            hl = None
    first = a[0] or hl or "#3f93e0"
    r = {"accent": first, "accent2": a[1] or first, "accent3": a[2] or first, **FIXED}
    try:
        r["muted"] = muted(widget) if widget is not None else "#808080"
    except Exception:
        r["muted"] = "#808080"
    return r


def follow(widget, qss):
    """widget.setStyleSheet(qss(roles)) now and on each palette change (a
    pack applied restyles open panels). qss builds rules scoped to the
    widget's object name."""
    from PySide import QtCore

    def apply():
        css = qss(roles(widget))
        if css != widget.styleSheet():  # no loop: the same sheet is not set again
            widget.setStyleSheet(css)

    class _Watch(QtCore.QObject):
        busy = False

        def eventFilter(self, obj, ev):
            if ev.type() == QtCore.QEvent.PaletteChange and not self.busy:
                self.busy = True
                try:
                    apply()
                finally:
                    self.busy = False
            return False

    w = _Watch(widget)
    widget.installEventFilter(w)
    widget._safetynet_theme = w  # kept alive with the widget
    apply()
    return apply
