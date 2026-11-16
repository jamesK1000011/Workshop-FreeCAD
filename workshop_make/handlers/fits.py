# SPDX-License-Identifier: LGPL-2.1-or-later
# The handlers for fits and hardware holes (fit, hw_hole): a thin layer over
# workshop_make.api.

from workshop_make.refusal import Refused

from .. import api
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal


def fit(s, a):
    act = a.get("action", "size")
    try:
        if act == "calibrate":
            c = api.calibrate(s.doc, a.get("hole", 0.2), a.get("shaft", 0.0))
            return {"calibration": c, "note": "Every hole and fit sized from now on takes it; a print setup's own fit wins for its parts."}
        if act == "stack":
            return api.stack(a.get("items") or [], a.get("target"))
        if act == "size":
            return api.fit_size(a.get("nominal"), a.get("of", "hole"), a.get("kind"), doc=s.doc, body=a.get("body"))
    except Refused as e:
        raise ToolError(e.code, e.message)
    raise ToolError("invalid_input", "action: size, calibrate or stack.")


def hw_hole(s, a):
    o = s.body(a.get("body"))
    try:
        out = api.hole(s.doc, o, a.get("kind"), a.get("size", "M3"), a.get("at"), a.get("dir", "-z"), a.get("depth", "through"), a.get("fit", "normal"),
                       face=a.get("face"), sketch=a.get("sketch"))
    except Refused as e:
        raise ToolError(e.code, e.message)
    s.snapshot("hw_hole")
    out["step"] = len(s.steps)
    return out


HANDLERS = {
    "fit": fit,
    "hw_hole": hw_hole,
}
