# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's own runner: runner(tool, args) -> (ok, result), the one way its
panels and commands do anything. It calls the same handler the Agent Link
family binds (workshop_make/handlers), in a session of its own for the
document, one undo transaction per changing call, and answers in the shape
Agent Link's panel._call does: the tool's answer as JSON data, or
{"error": {"code", "message"}} with ok False. Under Agent Link the tabs get
panel._call instead; the widgets cannot tell the two apart.
No Agent Link import here."""
import json
import os

from . import handlers

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CHANGES = None


def changes(tool, args=None):
    """Whether this call of the tool changes the document (data/tools.json):
    a changing tool's reads ("reads": setup's action list or of) do not,
    so a panel's refresh opens no undo step and marks nothing changed."""
    global _CHANGES
    if _CHANGES is None:
        with open(os.path.join(_DATA, "tools.json"), encoding="utf-8") as f:
            _CHANGES = {k: (bool(v.get("changes")), v.get("reads") or {},
                            (v.get("inputSchema") or {}).get("properties") or {})
                        for k, v in json.load(f)["entries"].items()}
    ch, reads, props = _CHANGES.get(tool, (False, {}, {}))
    if not ch:
        return False
    a = args or {}
    return not any(a.get(k, props.get(k, {}).get("default")) in vals for k, vals in reads.items())


def _solid(o):
    try:
        return hasattr(o, "Shape") and not o.Shape.isNull() and bool(o.Shape.Solids)
    except Exception:
        return False


PASSIVE = ("App::DocumentObjectGroup", "Spreadsheet::Sheet", "App::Part", "Assembly::AssemblyObject", "Assembly::JointGroup")


def _builds_on(p):
    """Whether p, in a part's InList, is the part built on from it (a
    boolean, a mirror …: then p is the part, not what it uses). A hidden
    user, or an add-on's helper or state object (a ScanRuler reverse-engineer
    object, a Texturizer result, a group) only refers to the part: the part
    stays a part (live on 1.1.3: the Body vanished from the list and Make's
    New made an empty setup)."""
    if getattr(p, "TypeId", "") in PASSIVE or not _solid(p):
        return False
    if str(getattr(p, "TypeId", "")).endswith("FeaturePython"):
        return False  # an add-on's object refers to the part; both are listed
    return getattr(p, "Visibility", True) is not False


def bodies_in(doc):
    """The parts a person would name: shown solids nothing shown is built
    from (a PartDesign Body, not its features)."""
    out = []
    for o in getattr(doc, "Objects", None) or []:
        if not _solid(o):
            continue
        if any(_builds_on(p) for p in getattr(o, "InList", [])):
            continue
        try:
            parent = o.getParentGeoFeatureGroup()
        except Exception:
            parent = None
        if parent is not None and getattr(parent, "TypeId", "") == "PartDesign::Body":
            continue
        if getattr(o, "Visibility", True) is False:
            continue
        out.append(o)
    return out


def _refusal():
    """The refusal the handlers catch: Agent Link's ToolError when it lent
    one, else this add-on's own."""
    from .handlers import make

    return make.ToolError


class Session:
    """What a handler is given alone: the document, its parts, the steps
    and per-body notes kept while the document is open, the folder files
    go to (beside the saved document, else ~/Workshop)."""

    def __init__(self, doc, out_dir=None):
        self.doc = doc
        self.steps = []
        self.meta = {}
        self._out = out_dir

    @property
    def out_dir(self):
        d = self._out
        if not d:
            fn = getattr(self.doc, "FileName", "") or ""
            d = os.path.dirname(fn) if fn else os.path.expanduser("~/Workshop")
        os.makedirs(d, exist_ok=True)
        return d

    def bodies(self):
        return bodies_in(self.doc)

    def body(self, ref):
        if ref is not None:
            for o in getattr(self.doc, "Objects", None) or []:
                if _solid(o) and (o.Label == ref or o.Name == ref or o.Label.lower() == str(ref).lower()):
                    return o
        bs = self.bodies()
        if not bs:
            raise _refusal()("not_found", "No body in the document: make one first.")
        if ref is None:
            if len(bs) == 1:
                return bs[0]
            raise _refusal()("invalid_input", f"body: say which — {', '.join(o.Label for o in bs)}.")
        raise _refusal()("not_found", f"body {ref!r}: not here — the bodies: {', '.join(o.Label for o in bs)}.")

    def snapshot(self, tool):
        from . import geo

        self.steps.append({"step": len(self.steps) + 1, "tool": tool, "bodies": {o.Label: geo.stats(o.Shape) for o in self.bodies()}})


_SESSIONS = {}


def session_for(doc):
    """One session per open document, so its steps and notes last."""
    key = id(doc)
    s = _SESSIONS.get(key)
    if s is None or s.doc is not doc:
        s = _SESSIONS[key] = Session(doc)
    return s


def _active_doc():
    import FreeCAD

    return FreeCAD.ActiveDocument or FreeCAD.newDocument("Workshop")


def answer(fn, args):
    """(ok, result) of fn(args), shaped as Agent Link answers: JSON data,
    a refusal as {"error": {"code", "message"}}."""
    try:
        out = fn(args)
    except Exception as e:  # noqa: BLE001 — every refusal is an answer
        code = getattr(e, "code", None)
        msg = getattr(e, "message", None)
        if not (isinstance(code, str) and isinstance(msg, str)):
            code, msg = "failed", f"{type(e).__name__}: {e}"
        return False, {"error": {"code": code, "message": msg}}
    return True, json.loads(json.dumps(out, default=str))


def local(doc_fn=None, table=None):
    """runner(tool, args) -> (ok, result) over this add-on's handlers in
    the document doc_fn() gives (the active one by default)."""
    table = table or handlers.all_handlers()

    def run(tool, args=None):
        args = dict(args or {})
        fn = table.get(tool)
        if fn is None:
            return False, {"error": {"code": "not_found", "message": f"{tool}: not a tool of Workshop Make."}}
        doc = (doc_fn or _active_doc)()
        s = session_for(doc)
        if not changes(tool, args):
            return answer(lambda a: fn(s, a), args)
        doc.openTransaction(tool)
        ok, out = answer(lambda a: fn(s, a), args)
        if ok:
            doc.commitTransaction()
        else:
            doc.abortTransaction()
        return ok, out

    return run


def run(tool, args=None):
    """The default local runner, in the active document."""
    return local()(tool, args)
