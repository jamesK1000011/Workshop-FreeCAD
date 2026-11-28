# SPDX-License-Identifier: LGPL-2.1-or-later
# Parts' tool handlers: {tool_name: fn(ctx, args)} for gen_make (Gridfinity
# bins) and gen_part (baseplates, project boxes, board enclosures), over
# workshop_parts.api. ctx is the session the call runs in (Agent Link's, or
# the add-on's own runner's): its doc, meta, snapshot() and steps. No Agent
# Link import here: the family layer (fam_parts.py, loaded by Agent Link
# only) binds them with bound() and lends Agent Link's ToolError with lend();
# alone a refusal is Refusal below. This is the one place an answer is
# shaped.
import functools

from workshop_parts.refusal import Refused

from . import api


class Refusal(Exception):
    """A request refused, in the shape of Agent Link's ToolError (code,
    message), used when no host lends one."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


ToolError = Refusal  # lent by the family layer


def run(s, generator, a, step):
    try:
        out = api.make(s.doc, generator, a.get("params") or {}, a.get("name"), bool(a.get("measure")))
    except Refused as e:
        raise ToolError(e.code, e.message)
    if out.get("made") is False:
        return out
    for label in out["bodies"]:
        s.meta[label] = {"generator": generator, "values": out["values"]}
    if out.get("encased"):
        s.meta[out["bodies"][0]]["encased"] = out["encased"]
    if out.get("magnets"):
        s.meta[out["bodies"][0]]["fitted"] = out["magnets"]
    s.snapshot(step)
    out["step"] = len(s.steps)
    mags = out.pop("encased", None)
    if mags:
        out["encased"] = {"what": mags["what"], "count": mags["count"], "pauseAt": mags["top"]}
    return out


def gen_make(s, a):
    gen = a.get("generator", "gridfinity_bin")
    if gen != "gridfinity_bin":
        raise ToolError("invalid_input", "generator: gridfinity_bin (gen_part makes baseplates and boxes).")
    return run(s, gen, a, "gen_make")


def gen_part(s, a):
    gen = a.get("generator")
    if gen not in api.GENERATORS or gen == "gridfinity_bin":
        raise ToolError("invalid_input", f"generator: one of {', '.join(g for g in api.GENERATORS if g != 'gridfinity_bin')} (gridfinity_bin is gen_make's).")
    return run(s, gen, a, "gen_part")


HANDLERS = {
    "gen_make": gen_make,
    "gen_part": gen_part,
}


def bound(ctx, handlers=None):
    """{tool_name: fn(args)} for one context: handlers (default all) with
    ctx given."""
    return {k: functools.partial(fn, ctx) for k, fn in (HANDLERS if handlers is None else handlers).items()}


def lend(**names):
    """Set what the host lends (ToolError=...) in the slots this module has."""
    g = globals()
    for k, v in names.items():
        if k not in g:
            raise AttributeError(f"{__name__} has no slot {k!r} to lend")
        g[k] = v
