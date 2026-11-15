# SPDX-License-Identifier: LGPL-2.1-or-later
"""Documents' tool handlers: {tool_name: fn(ctx, args)} over workshop_documents'
api, one module per family. ctx is the session the call runs in (Agent
Link's, or the add-on's own runner's): its doc, body(), meta, snapshot().
No handler imports Agent Link. The family layer (fam_*.py, loaded by Agent
Link only) binds them with bound() and lends what of Agent Link they use
(its ToolError, measure and picks families) with lend(); alone, a
refusal is _lent.Refusal and those helpers are absent. The handler is the
one place an answer is shaped, for the agent and for the add-on's panels."""
import functools
import importlib

# One module per family, imported when first asked (a family that needs no
# FreeCAD module loads without one).
MODULES = ("drawing", "share")


def all_handlers():
    """{tool_name: fn(ctx, args)} of every family."""
    out = {}
    for m in MODULES:
        out.update(importlib.import_module(f"{__name__}.{m}").HANDLERS)
    return out


def bound(ctx, handlers=None):
    """{tool_name: fn(args)} for one context: handlers (default all) with
    ctx given."""
    return {k: functools.partial(fn, ctx) for k, fn in (all_handlers() if handlers is None else handlers).items()}


def lend(module, **names):
    """Set what the host lends (ToolError=..., M=...) on a handler
    module, in the slots it has for them."""
    for k, v in names.items():
        if not hasattr(module, k):
            raise AttributeError(f"{module.__name__} has no slot {k!r} to lend")
        setattr(module, k, v)
