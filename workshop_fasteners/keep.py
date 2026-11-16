# SPDX-License-Identifier: LGPL-2.1-or-later
"""Keeps the fasteners Workshop puts in (fastener_add, hw_hole's screw) on
their holes and under readable, stable labels. Fasteners Workbench itself
is not changed: this watches the document from outside.

Why. Fasteners attaches a screw to an edge by its name (BaseObject,
"Body.Edge7"). A later PartDesign feature can renumber the Body's edges
(FreeCAD's topological naming): Edge7 is then another edge or none, and
the screw jumps or stays behind without a word. And Fasteners' execute()
sets the label to "M8x25-Screw" on every recompute, unconditionally; with
two M8x25 screws FreeCAD makes the second unique by a suffix one past the
highest in use, so its label counted up at every recompute
(M8x25-Screw218, 219, 222).

What is kept, in the fastener's own property WorkshopKeep (JSON, saved
with the file, read-only in the property editor):
- anchor: the object, the edge's name, and its geometry: the circle's
  centre, axis and radius, in the object's shape frame (as getSubObject
  gives it);
- label: the label it keeps — "M8x25-Screw", the next of that size
  "M8x25-Screw 2", and so on, numbered per size once and kept; a label
  given with fastener_set { label } is kept as given;
- lost: why it could not be put back on its hole, when it could not.

After each recompute (an App document observer, Init.py) and after each
Workshop fasteners call (sweep): a fastener whose edge no longer is the
circle in its anchor is put on the round edge with the same radius and a
parallel axis nearest the stored centre, within reach() mm, and redone;
none there: it is left where it is and said loudly — a warning in the
Report view, `lost` in fastener_list's answer and its warnings. Labels go
back to the kept one. With a window, a reattach's recompute runs just
after the document's recompute (a zero timer), never inside it."""
import json
import re

PROP = "WorkshopKeep"
_busy = False
_pending = set()


def _fc():
    import FreeCAD

    return FreeCAD


# ---- the kept record ----------------------------------------------------------------------

def read(o):
    if PROP not in getattr(o, "PropertiesList", ()):
        return None
    try:
        v = json.loads(getattr(o, PROP) or "{}")
        return v if isinstance(v, dict) else {}
    except (TypeError, ValueError):
        return {}


def write(o, rec):
    """Stored only when it changed; the property is NoRecompute, so keeping
    it never leaves the fastener touched (needing a recompute)."""
    if PROP not in getattr(o, "PropertiesList", ()):
        o.addProperty("App::PropertyString", PROP, "Workshop",
                      "Kept by Workshop: the hole's edge by its geometry (re-found when FreeCAD renumbers edges) and the label this fastener keeps.")
        for how in (lambda: o.setEditorMode(PROP, 1), lambda: o.setPropertyStatus(PROP, "NoRecompute")):
            try:
                how()
            except Exception:  # noqa: BLE001 — an older FreeCAD: still kept
                pass
    v = json.dumps(rec, sort_keys=True)
    if getattr(o, PROP, None) != v:
        setattr(o, PROP, v)


def kept(doc):
    return [o for o in getattr(doc, "Objects", []) if PROP in getattr(o, "PropertiesList", ())]


# ---- geometry -----------------------------------------------------------------------------

def _xyz(v):
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _circle(sh):
    c = getattr(sh, "Curve", None)
    if c is None or not all(hasattr(c, k) for k in ("Radius", "Center", "Axis")):
        return None
    return c


def _unit(v):
    n = (v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5 or 1.0
    return [v[0] / n, v[1] / n, v[2] / n]


def geometry(obj, sub):
    """{c, a, r} of obj's round edge sub, or None."""
    try:
        c = _circle(obj.getSubObject(sub))
    except Exception:  # noqa: BLE001
        c = None
    if c is None:
        return None
    return {"c": _xyz(c.Center), "a": [round(x, 6) for x in _unit(_xyz(c.Axis))], "r": round(float(c.Radius), 6)}


def _same(g, h, tol=1e-3):
    if g is None or h is None:
        return False
    d = sum((g["c"][i] - h["c"][i]) ** 2 for i in range(3)) ** 0.5
    dot = sum(g["a"][i] * h["a"][i] for i in range(3))
    return d <= tol and abs(g["r"] - h["r"]) <= tol and dot >= 1 - 1e-6


def reach(r):
    """How far (mm) the hole's circle may have moved and still be its own:
    its radius, at least 1 mm. Farther is another hole, never taken."""
    return max(1.0, float(r))


def refind(obj, g):
    """"EdgeN" of obj: the round edge with g's radius (0.01 mm) and a
    parallel axis nearest g's centre within reach; the same axis direction
    first. None when there is none."""
    best = None
    edges = getattr(getattr(obj, "Shape", None), "Edges", None) or []
    for i, e in enumerate(edges, start=1):
        c = _circle(e)
        if c is None or abs(float(c.Radius) - g["r"]) > 0.01:
            continue
        a = _unit(_xyz(c.Axis))
        dot = sum(a[k] * g["a"][k] for k in range(3))
        if abs(dot) < 0.999:
            continue
        p = _xyz(c.Center)
        d = sum((p[k] - g["c"][k]) ** 2 for k in range(3)) ** 0.5
        if d > reach(g["r"]):
            continue
        key = (0 if dot > 0 else 1, round(d, 6), i)
        if best is None or key < best[0]:
            best = (key, i)
    return f"Edge{best[1]}" if best else None


# ---- labels -------------------------------------------------------------------------------

def base_of(label):
    """"M8x25-Screw" from what Fasteners set and FreeCAD made unique
    ("M8x25-Screw219") or a kept "M8x25-Screw 2"."""
    return re.sub(r"\s*\d+$", "", str(label or "")) or str(label or "")


def _taken(doc, o):
    out = set()
    for x in getattr(doc, "Objects", []):
        if x is o:
            continue
        out.add(x.Label)
        r = read(x)
        if r and r.get("label"):
            out.add(r["label"])
    return out


def stable_label(doc, o, base):
    """base, else "base 2", "base 3" … the first no other object holds."""
    taken = _taken(doc, o)
    n = 1
    while True:
        cand = base if n == 1 else f"{base} {n}"
        if cand not in taken:
            return cand
        n += 1


def _relabel(doc, o, rec):
    if rec.get("auto", True):
        base = base_of(o.Label)
        if not rec.get("label") or base_of(rec["label"]) != base:
            rec["label"] = stable_label(doc, o, base)
    want = rec.get("label")
    if want and o.Label != want:
        o.Label = want
    return rec


# ---- taking a fastener in -----------------------------------------------------------------

def adopt(doc, o, label=None):
    """Keep o: its anchor from its BaseObject now, its label stable (or
    label as given)."""
    rec = read(o) or {}
    rec.pop("lost", None)
    try:
        b = o.BaseObject
    except Exception:  # noqa: BLE001
        b = None
    if b and b[0] is not None and b[1]:
        g = geometry(b[0], b[1][0])
        if g is not None:
            rec["anchor"] = {"object": b[0].Name, "edge": b[1][0], **g}
    elif b is None or (b and b[0] is None):
        rec.pop("anchor", None)
    if label:
        rec["label"], rec["auto"] = str(label), False
    else:
        rec.setdefault("auto", True)
    rec = _relabel(doc, o, rec)
    write(o, rec)
    return rec


def on_edge(doc, obj, sub):
    """The kept fasteners anchored on obj's round edge sub (same circle)."""
    g = geometry(obj, sub)
    out = []
    for o in kept(doc):
        a = (read(o) or {}).get("anchor")
        if a and a.get("object") == obj.Name and _same(a, g):
            out.append(o)
    return out


# ---- after a recompute ----------------------------------------------------------------------

REATTACHED = {}  # {(doc, name): sentence} said once in describe()


def _warn(msg):
    try:
        _fc().Console.PrintWarning("Workshop: " + msg + "\n")
    except Exception:  # noqa: BLE001
        pass


def check(doc, o, fix=True):
    """One kept fastener: label back; anchor checked. Returns "ok",
    "reattached", "pending" (fix=False and it needs a reattach), "lost"."""
    rec = read(o)
    if rec is None:
        return "ok"
    a = rec.get("anchor")
    state = "ok"
    if a:
        obj = doc.getObject(a["object"]) if hasattr(doc, "getObject") else next((x for x in doc.Objects if x.Name == a["object"]), None)
        try:
            b = o.BaseObject
            cur = (b[0], b[1][0]) if b and b[0] is not None and b[1] else (None, None)
        except Exception:  # noqa: BLE001
            cur = (None, None)
        if obj is None:
            state, why = "lost", f"{a['object']}, the object it was on, is gone"
        elif cur[0] is obj and _same(geometry(obj, cur[1]), a):
            if cur[1] != a.get("edge"):
                a["edge"] = cur[1]
        else:
            new = refind(obj, a)
            if new is None:
                at = [round(x, 2) for x in a["c"]]
                state, why = "lost", (f"{obj.Label}.{a['edge']} is no longer its hole's edge (⌀{round(2 * a['r'], 3)} at {at}) and no round edge "
                                      f"of that size is within {reach(a['r'])} mm — the hole was moved or removed")
            elif not fix:
                state = "pending"
            else:
                was = a.get("edge")
                o.BaseObject = (obj, [new])
                g = geometry(obj, new)
                rec["anchor"] = {"object": obj.Name, "edge": new, **g}
                try:
                    o.recompute()
                except Exception:  # noqa: BLE001
                    pass
                state = "reattached"
                REATTACHED[(getattr(doc, "Name", ""), o.Name)] = (
                    f"FreeCAD renumbered {obj.Label}'s edges after an edit: put back on its hole, {obj.Label}.{new} (was {was}).")
        if state == "lost":
            msg = f"{rec.get('label') or o.Label} lost its hole: {why}. It is not attached to its hole — fastener_set {{ objects: [\"{rec.get('label') or o.Label}\"], edge }} puts it on one."
            if rec.get("lost") != msg:
                _warn(msg)
            rec["lost"] = msg
        elif state in ("ok", "reattached"):
            rec.pop("lost", None)
            # Follow a hole that moved a little (within reach) next time too.
            if state == "ok" and obj is not None:
                g = geometry(obj, a["edge"])
                if g:
                    rec["anchor"] = {"object": obj.Name, "edge": a["edge"], **g}
    rec = _relabel(doc, o, rec)
    write(o, rec)
    return state


def sweep(doc, fix=True):
    """Every kept fastener of doc checked (check()). {name: state} for
    those not ok."""
    global _busy
    if _busy:
        return {}
    _busy = True
    try:
        out = {}
        for o in kept(doc):
            try:
                s = check(doc, o, fix)
            except Exception as e:  # noqa: BLE001 — never break a recompute
                _warn(f"could not check {getattr(o, 'Label', '?')}: {e}")
                continue
            if s != "ok":
                out[o.Name] = s
        return out
    finally:
        _busy = False


def lost_note(o):
    return (read(o) or {}).get("lost")


# ---- the observer ---------------------------------------------------------------------------

def _later(doc):
    name = getattr(doc, "Name", "")
    if name in _pending:
        return
    _pending.add(name)

    def run():
        _pending.discard(name)
        try:
            d = _fc().getDocument(name)
        except Exception:  # noqa: BLE001 — closed meanwhile
            return
        sweep(d, fix=True)

    try:
        from PySide import QtCore  # FreeCAD's shim

        QtCore.QTimer.singleShot(0, run)
    except Exception:  # noqa: BLE001
        _pending.discard(name)


class Observer:
    """After a document's recompute: labels back and anchors checked at
    once; a reattach (it recomputes the fastener) just after, with a
    window, or at once without one."""

    def slotRecomputedDocument(self, doc):
        if _busy or not kept(doc):
            return
        try:
            gui = bool(getattr(_fc(), "GuiUp", False))
        except Exception:  # noqa: BLE001
            gui = False
        states = sweep(doc, fix=not gui)
        if gui and "pending" in states.values():
            _later(doc)


_observer = None


def watch():
    """Register the observer once (Init.py, when Fasteners is installed)."""
    global _observer
    if _observer is not None:
        return _observer
    _observer = Observer()
    _fc().addDocumentObserver(_observer)
    return _observer
