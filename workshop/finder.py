# SPDX-License-Identifier: LGPL-2.1-or-later
"""How a tool of Workshop finds the body a person names, shown or hidden.

Found live (FreeCAD 1.1.3, the bicycle): two sprockets were PartDesign
bodies, hidden. cut_export and drawing_make did not find "Chainring" by the
body's label; only the label of its tip feature worked, after it was shown.
The session's own body() (Agent Link's, or the add-on's runner's) looks at
the shown parts. find() also looks at hidden ones: a PartDesign Body by its
Label or Name first, then any other solid. A Body gives its own Shape (the
tip's solid); when that is empty, the tip's Shape.

Looked(session) is the session the handlers get: body(ref) asks the
session first and, when the session does not find ref, find(). Everything
else (doc, bodies(), meta, steps, out_dir, attributes set on it) is the
session's own. Plain Python: no FreeCAD import, no Agent Link import."""

BODY = "PartDesign::Body"


def _solid(shape):
    try:
        return shape is not None and not shape.isNull() and bool(shape.Solids)
    except Exception:  # noqa: BLE001
        return False


class TipShaped:
    """A Body whose own Shape is empty, with its tip's Shape: every other
    attribute is the Body's. __wrapped__ is the Body itself, for FreeCAD
    calls that need the document object (a TechDraw view's Source)."""

    def __init__(self, body, shape):
        object.__setattr__(self, "__wrapped__", body)
        object.__setattr__(self, "Shape", shape)

    def __getattr__(self, k):
        return getattr(object.__getattribute__(self, "__wrapped__"), k)

    def __setattr__(self, k, v):
        setattr(object.__getattribute__(self, "__wrapped__"), k, v)


def real(o):
    """The document object behind o (o itself when it is not a TipShaped)."""
    return getattr(o, "__wrapped__", o) if isinstance(o, TipShaped) else o


def usable(o):
    """o, or for a Body with an empty Shape its tip's Shape on it. None
    when there is no solid at all."""
    if _solid(getattr(o, "Shape", None)):
        return o
    if getattr(o, "TypeId", "") == BODY:
        tip = getattr(o, "Tip", None)
        if tip is not None and _solid(getattr(tip, "Shape", None)):
            return TipShaped(o, tip.Shape)
    return None


def find(doc, ref):
    """The object named ref in doc, shown or hidden, or None: a
    PartDesign Body by its Label or Name, then any solid by its Label or
    Name; an exact name before a match that ignores case."""
    if ref is None:
        return None
    name = str(ref)
    low = name.lower()
    objs = list(getattr(doc, "Objects", None) or [])

    def hit(o, exact):
        label, nm = str(getattr(o, "Label", "")), str(getattr(o, "Name", ""))
        return (label == name or nm == name) if exact else (label.lower() == low or nm.lower() == low)

    for exact in (True, False):
        for o in objs:
            if getattr(o, "TypeId", "") == BODY and hit(o, exact):
                got = usable(o)
                if got is not None:
                    return got
        for o in objs:
            if getattr(o, "TypeId", "") != BODY and hit(o, exact):
                got = usable(o)
                if got is not None:
                    return got
    return None


class Looked:
    """A session whose body(ref) also finds hidden bodies (find)."""

    def __init__(self, session):
        object.__setattr__(self, "_session", session)

    def __getattr__(self, k):
        return getattr(object.__getattribute__(self, "_session"), k)

    def __setattr__(self, k, v):
        setattr(object.__getattribute__(self, "_session"), k, v)

    def body(self, ref=None):
        s = object.__getattribute__(self, "_session")
        try:
            return s.body(ref)
        except Exception as e:  # noqa: BLE001 — the session's refusal, whoever lent it
            if ref is None or getattr(e, "code", None) not in ("not_found", "invalid_input"):
                raise
            got = find(getattr(s, "doc", None), ref)
            if got is None:
                raise
            return got


def looked(session):
    """The session with body() that finds hidden bodies; one wrap only."""
    return session if isinstance(session, Looked) else Looked(session)
