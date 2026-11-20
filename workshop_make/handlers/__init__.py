# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's tool handlers: {tool_name: fn(ctx, args)} over workshop_make's
api, one module per family. ctx is the session the call runs in (Agent
Link's, or the add-on's own runner's): its doc, body(), meta, snapshot().
No handler imports Agent Link. The family layer (fam_*.py, loaded by Agent
Link only) binds them with bound() and lends what of Agent Link they use
(its ToolError, material family, face picks, hooks) with lend(); alone, a
refusal is _lent.Refusal and those helpers are absent. The handler is the
one place an answer is shaped, for the agent and for the add-on's panels."""
import functools
import importlib

# One module per family, imported when first asked (a family that needs no
# FreeCAD module loads without one).
MODULES = ("make", "fits", "mass", "thread", "embed", "slicing", "printer", "cut", "mill", "frame")


def all_handlers():
    """{tool_name: fn(ctx, args)} of every family."""
    out = {}
    for m in MODULES:
        out.update(importlib.import_module(f"{__name__}.{m}").HANDLERS)
    return out


def bound(ctx, handlers=None):
    """{tool_name: fn(args)} for one context: handlers (default all) with
    ctx given. ctx's body() also finds a hidden body by its Label or Name
    (workshop.finder: found live, a hidden PartDesign Body was not found)."""
    from workshop import finder

    ctx = finder.looked(ctx)
    return {k: functools.partial(fn, ctx) for k, fn in (all_handlers() if handlers is None else handlers).items()}


def lend(module, **names):
    """Set what the host lends (ToolError=..., matfam=...) on a handler
    module, in the slots it has for them."""
    for k, v in names.items():
        if not hasattr(module, k):
            raise AttributeError(f"{module.__name__} has no slot {k!r} to lend")
        setattr(module, k, v)


def review(session, body):
    """The verdict on a body for a Review tab (Agent Link's
    hooks.register_reviewer: fn(session, body)): part_review's answer, or
    {"error": {code, message}} when it is refused, as a panel's failed call
    reads. session: the host's (Agent Link's), or None for Make's own in
    the active document."""
    from .. import runner
    from . import make

    from workshop import finder

    if session is not None and hasattr(session, "body"):
        ctx = finder.looked(session)  # the host's: hidden bodies found too
    else:
        ctx = runner.session_for(getattr(session, "doc", None) or runner._active_doc())
    return runner.answer(lambda a: make.part_review(ctx, a), {"body": body})[1]
