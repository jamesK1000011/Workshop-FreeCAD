# SPDX-License-Identifier: LGPL-2.1-or-later
# Checkpoints as saved copies of a document, under ~/AgentLink/checkpoints/
# <document>: what to keep (the cap, the last 10 unnamed and every named
# one), finding one by id or name, and going back to one — by undo while
# FreeCAD's undo stack still reaches it, else by reopening its copy. The
# person's own file is never touched.
#
# Plain FreeCAD (imported where it is used, so the rules are tested without
# it). A "session" is any object with doc, steps, tx, meta, calls,
# family_state, switch(doc) and snapshot(why): Agent Link's, or one's own.

import os
import shutil
import tempfile
import time

from .files import MB, _load, _save, _size, free_bytes, path, safe
from .refusal import Refused

KEEP_UNNAMED = 10


def cap_bytes(free, setting_mb=0):
    """A document's checkpoint cap: the person's setting (MB) when set, else
    the larger of 500 MB and 2% of the free disk."""
    if setting_mb and setting_mb > 0:
        return int(setting_mb * MB)
    return max(500 * MB, int(0.02 * max(0, free)))


def cp_dir(doc):
    return path("checkpoints", safe(doc))


def cp_index(doc):
    return _load(os.path.join(cp_dir(doc), "index.json"), [])


def cp_save_index(doc, entries):
    _save(os.path.join(cp_dir(doc), "index.json"), entries)


# Who took a checkpoint, written with it: the person (SafetyNet's own
# commands and dock, local.LocalSession) or an agent's call (any other
# session). Checkpoints from before carry neither.
PERSON, AGENT = "person", "agent"


def who(session):
    """Who a session's checkpoints are taken by: its "by", else an agent."""
    by = getattr(session, "by", None)
    return by if by in (PERSON, AGENT) else AGENT


def cp_new(doc, name=None, step=0, undo=0, tx=0, auto=False, by=None):
    """A new checkpoint's entry and the file it is to be written to (the
    caller saves the copy there, then cp_add)."""
    entries = cp_index(doc)
    n = max([e.get("n", 0) for e in entries] or [0]) + 1
    tag = safe(name) if name else ("auto" if auto else "cp")
    f = os.path.join(cp_dir(doc), f"{n}-{tag}.FCStd")
    return {"id": f"cp{n}", "n": n, "name": name, "auto": bool(auto), "file": f, "step": step, "undo": undo, "tx": tx, "t": time.time(),
            **({"by": by} if by else {})}


def cp_add(doc, entry, cap):
    """Record a written checkpoint and keep within the cap: the last 10
    unnamed and every named one, the oldest unnamed going first. Answers
    the entries dropped."""
    entry["bytes"] = _size(entry["file"])
    entries = cp_index(doc) + [entry]
    kept, dropped = cp_prune(entries, cap)
    for e in dropped:
        try:
            os.remove(e["file"])
        except OSError:
            pass
    cp_save_index(doc, kept)
    return dropped


def cp_prune(entries, cap, keep=KEEP_UNNAMED):
    """(kept, dropped): unnamed ones past the newest `keep`, then the oldest
    unnamed while the total is over cap. Named ones stay — the person's or
    the agent's own; the automatic ones ("before restore …") go like
    unnamed ones."""
    entries = sorted(entries, key=lambda e: e.get("n", 0))
    unnamed = [e for e in entries if not e.get("name") or e.get("auto")]
    drop = {id(e) for e in unnamed[:-keep]} if len(unnamed) > keep else set()
    total = sum(e.get("bytes", 0) for e in entries if id(e) not in drop)
    for e in unnamed:
        if total <= cap:
            break
        if id(e) in drop or e is unnamed[-1]:
            continue
        drop.add(id(e))
        total -= e.get("bytes", 0)
    return [e for e in entries if id(e) not in drop], [e for e in entries if id(e) in drop]


def cp_find(doc, ref):
    """A checkpoint by id (cp3), number, or name; the newest of a name."""
    entries = cp_index(doc)
    for e in reversed(entries):
        if ref in (e.get("id"), e.get("name"), str(e.get("n"))) or (isinstance(ref, int) and e.get("n") == ref):
            return e
    return None


def can_undo_back(entry, tx_now, undo_now, undo_limit=20):
    """Whether the undo stack still reaches a checkpoint: as many steps on it
    as transactions since, none of them fallen off the bottom."""
    since = tx_now - int(entry.get("tx", 0))
    if since < 0:
        return False
    if since == 0:
        return True
    expect = int(entry.get("undo", 0)) + since
    return expect <= undo_limit and undo_now == expect


# ---- with FreeCAD: a session's checkpoints ----------------------------------------------

def _mine(session):
    """This session's checkpoints by document, kept in its family state."""
    st = session.family_state.setdefault("safetynet", {})
    return st.setdefault("checkpoints", {}).setdefault(session.doc.Name, {})


def undo_limit():
    import FreeCAD

    try:
        return int(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document").GetInt("MaxUndoSize", 20)) or 20
    except Exception:
        return 20


def take(session, name=None, auto=False, doc=None):
    """A copy of the document as it is now: (entry, dropped)."""
    import FreeCAD

    d = doc or session.doc
    mine = d is session.doc
    e = cp_new(d.Name, name, step=len(session.steps) if mine else 0, undo=d.UndoCount, tx=session.tx if mine else -1, auto=auto,
               by=who(session))
    e.update({"label": d.Label, "fileName": d.FileName or "", "session": id(session)})
    os.makedirs(os.path.dirname(e["file"]), exist_ok=True)
    d.saveCopy(e["file"])
    cap_mb = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/AgentLink").GetInt("CheckpointCapMB", 0)
    dropped = cp_add(d.Name, e, cap_bytes(free_bytes(cp_dir(d.Name)), cap_mb))
    if mine:
        _mine(session)[e["id"]] = e
    return e, dropped


def find(session, ref):
    if ref is None or ref == "":
        return None
    return _mine(session).get(ref) or cp_find(session.doc.Name, ref)


def index(doc_name):
    return cp_index(doc_name)


def reopen_copy(session, src):
    """Put a saved copy in place of the document, under its own name, label
    and file: the session goes on with its steps and checkpoints."""
    import FreeCAD

    d = session.doc
    name, label, fname = d.Name, d.Label, d.FileName or ""
    tmpd = tempfile.mkdtemp(prefix="agentlink-restore-")
    tmp = os.path.join(tmpd, name + ".FCStd")
    shutil.copy2(src, tmp)
    kept = (session.steps, session.meta, session.calls, session.family_state)
    FreeCAD.closeDocument(name)
    nd = FreeCAD.openDocument(tmp)
    nd.Label = label
    restored_file = True
    if fname:
        try:
            nd.FileName = fname
            restored_file = nd.FileName == fname
        except Exception:
            restored_file = False
    session.switch(nd)
    session.steps, session.meta, session.calls, session.family_state = kept
    session.tx = 0  # a fresh undo stack
    session.saved_as = getattr(session, "saved_as", {})
    if fname and not restored_file:
        session.saved_as[nd.Name] = fname
    try:
        nd.recompute()
    except Exception:
        pass
    return {"document": nd.Name, "label": nd.Label, "file": fname or None, "savedAs": None if restored_file else fname}


def restore(session, ref):
    """Back to a checkpoint: by undo while the stack reaches it, else from its
    saved copy (the state before checkpointed first)."""
    cp = find(session, ref)
    if not cp:
        known = [e["id"] + (f" ({e['name']})" if e.get("name") else "") for e in cp_index(session.doc.Name)]
        raise Refused("not_found", f"checkpoint {ref!r}: {'the checkpoints: ' + ', '.join(known) if known else 'none for this document'} — history_checkpoint takes one.")
    d = session.doc
    if cp.get("session") == id(session) and can_undo_back(cp, session.tx, d.UndoCount, undo_limit()):
        names = []
        while session.tx > int(cp.get("tx", 0)) and d.UndoCount > 0:
            names.append(d.UndoNames[0])
            d.undo()
            session.tx -= 1
        d.recompute()
        session.snapshot("history_restore")
        return {"done": "restore", "checkpoint": cp["id"], "how": "undo", "steps": names}
    if not os.path.isfile(cp.get("file", "")):
        raise Refused("not_found", f"{cp['id']}'s saved copy is gone ({cp.get('file')}).")
    before, _ = take(session, f"before restore {cp['id']}", auto=True)
    old = _mine(session)
    out = reopen_copy(session, cp["file"])
    # The document may come back under another name: its checkpoints go with it.
    st = session.family_state.setdefault("safetynet", {}).setdefault("checkpoints", {})
    st.setdefault(session.doc.Name, {}).update(old)
    session.snapshot("history_restore")
    return {"done": "restore", "checkpoint": cp["id"], "how": "file", **out, "before": before["id"]}


class Service:
    """What SafetyNet offers Agent Link as its "checkpoints" service."""

    take = staticmethod(take)
    find = staticmethod(find)
    index = staticmethod(index)
    restore = staticmethod(restore)
