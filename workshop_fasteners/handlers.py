# SPDX-License-Identifier: LGPL-2.1-or-later
"""The fasteners tools' handlers: {tool_name: fn(ctx, args)} over
workshop_fasteners.api. ctx is the session the call runs in (Agent Link's,
or Workshop's own runner's): its doc and snapshot(). No Agent Link import
here; the family layer lends its ToolError."""
from . import api
from .fs import Missing


class Refusal(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


ToolError = Refusal  # lent by fam_fasteners under Agent Link


def _run(fn):
    try:
        return fn()
    except Missing as e:
        raise ToolError(e.code, e.message)


def _thread(a):
    t = a.get("thread")
    if t not in (None, "simple", "real"):
        raise ToolError("invalid_input", "thread: simple (a plain cylinder, fast) or real (a modelled thread).")
    return t


def fastener_types(s, a):
    return _run(lambda: api.types(a.get("query"), a.get("standard"), a.get("kind"), a.get("type"), a.get("size")))


def fastener_add(s, a):
    if not a.get("type"):
        raise ToolError("invalid_input", "type: a Fasteners type, e.g. ISO4762 (socket head cap screw) — fastener_types { query } finds one.")
    at = a.get("at")
    if at is not None and not (isinstance(at, list) and len(at) == 3):
        raise ToolError("invalid_input", "at: [x, y, z], mm — where a loose fastener goes (edges attach it instead).")
    made = _run(lambda: api.add(s.doc, a["type"], a.get("size"), a.get("length"), _thread(a) or "simple", a.get("edges") or (),
                                at, a.get("match", "outer"), a.get("invert", False), a.get("offset", 0.0)))
    s.snapshot("fastener_add")
    return {"made": [api.describe(o) for o in made], "source": api.SOURCE}


def fastener_set(s, a):
    refs = a.get("objects") or ([a["object"]] if a.get("object") else [])
    if a.get("restore"):
        done = _run(lambda: api.restore(s.doc))
        if not refs:
            s.snapshot("fastener_set")
            return {"restored": done}
    if not refs:
        raise ToolError("invalid_input", "objects: the fasteners to change (fastener_list names them).")
    m = a.get("match")
    if m not in (None, "inner", "outer"):
        raise ToolError("invalid_input", "match: inner (tap hole) or outer (pass hole).")
    objs = _run(lambda: api.change(s.doc, refs, a.get("type"), a.get("size"), a.get("length"), _thread(a), a.get("invert"), a.get("offset"), m, a.get("edge"), a.get("label")))
    s.snapshot("fastener_set")
    return {"changed": [api.describe(o) for o in objs]}


def fastener_list(s, a):
    out = _run(lambda: api.listing(s.doc))
    if a.get("sheet"):
        out.update(_run(lambda: api.bom_sheet(s.doc)))
    return out


def fastener_print(s, a):
    if not any(k in a for k in ("mode", "nut", "screw")):
        return _run(api.read_print_settings)
    return _run(lambda: api.print_settings(a.get("mode"), a.get("nut"), a.get("screw")))


HANDLERS = {
    "fastener_types": fastener_types,
    "fastener_add": fastener_add,
    "fastener_set": fastener_set,
    "fastener_list": fastener_list,
    "fastener_print": fastener_print,
}
