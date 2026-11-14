# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's tools for fits and hardware holes (fit, hw_hole), the names
# they have always had: a thin layer over workshop_make.api. Loaded by Agent
# Link only.

from addonkit import Refused

from . import api, tooldefs

GROUP = "fits"
INFO = "Fits, printer calibration, tolerance stacks and holes for hardware (Workshop for FreeCAD · Make)."
LEAN = True


def tools(session):
    from agentlink.protocol import ToolError

    s = session

    def fit(a):
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

    def hw_hole(a):
        o = s.body(a.get("body"))
        try:
            out = api.hole(s.doc, o, a.get("kind"), a.get("size", "M3"), a.get("at"), a.get("dir", "-z"), a.get("depth", "through"), a.get("fit", "normal"))
        except Refused as e:
            raise ToolError(e.code, e.message)
        s.snapshot("hw_hole")
        out["step"] = len(s.steps)
        return out

    return tooldefs.build("fits", {"fit": fit, "hw_hole": hw_hole})
