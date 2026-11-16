# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet with no agent: the session its commands and its own dock run the
# handlers in, and the local runner the Session panel uses when Agent Link
# is not loaded. Same handlers, same answers, same refusals as the agent's
# tools; each call is one undo step of the document in front.
from . import handlers
from .refusal import Refused

# Every LocalSession made stays referenced, so no two ever share an id():
# a checkpoint taken by one is never mistaken for another's undo history,
# and a restore always goes through the checkpoint's saved copy.
_made = []


class LocalSession:
    """What the handlers need of a session, over the document in front. No
    agent steps or calls: those exist only under Agent Link."""

    in_place = True  # settings roll back into the running FreeCAD (no restart tool here)
    by = "person"  # its checkpoints are the person's own (checkpoints.who)
    server = None

    def __init__(self):
        self.steps, self.calls, self.meta, self.family_state = [], [], {}, {}
        self.tx = 0
        self._doc = None
        _made.append(self)

    @property
    def doc(self):
        if self._doc is not None:
            return self._doc
        import FreeCAD

        d = FreeCAD.ActiveDocument
        if d is None:
            raise Refused("invalid_state", "No document open: open or make one first.")
        return d

    @doc.setter
    def doc(self, d):
        self._doc = d

    def switch(self, d):
        self._doc = d
        try:
            import FreeCAD

            FreeCAD.setActiveDocument(d.Name)
            import FreeCADGui

            FreeCADGui.setActiveDocument(d.Name)
        except Exception:
            pass

    def snapshot(self, *_a, **_k):
        pass

    def bodies(self):
        try:
            return [o for o in self.doc.Objects if o.TypeId == "PartDesign::Body"]
        except Exception:
            return []


def _open_docs():
    try:
        import FreeCAD

        return list(FreeCAD.listDocuments().values())
    except Exception:
        return []


def run(tool, args=None, session=None):
    """runner(tool, args) -> (ok, result): the handler for tool, in one undo
    transaction of the document in front; a refusal comes back as
    {"error": {code, message}}, the shape Agent Link's panel gets."""
    fn = handlers.HANDLERS.get(tool)
    if fn is None:
        return False, {"error": {"code": "not_found", "message": f"{tool}: needs Agent Link for FreeCAD (not loaded here)."}}
    s = session or LocalSession()
    doc = None
    try:
        import FreeCAD

        doc = FreeCAD.ActiveDocument
    except Exception:
        pass
    if doc is not None:
        s._doc = s._doc or doc
        try:
            doc.openTransaction(f"SafetyNet: {tool}")
        except Exception:
            doc = None

    def end(commit):
        # The document may have been closed and reopened (a restore from a
        # saved copy): only a document still open has a transaction to end.
        if doc is None or not any(d is doc for d in _open_docs()):
            return
        try:
            doc.commitTransaction() if commit else doc.abortTransaction()
        except Exception:
            pass

    try:
        out = fn(s, dict(args or {}))
    except Refused as e:
        end(False)
        return False, {"error": {"code": e.code, "message": e.message}}
    except Exception as e:  # noqa: BLE001 — a panel button never raises into Qt
        end(False)
        return False, {"error": {"code": "failed", "message": f"{tool}: {e}"}}
    end(True)
    return True, out


def runner():
    """The runner a panel gets when Agent Link is not the host."""
    return run
