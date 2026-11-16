# SPDX-License-Identifier: LGPL-2.1-or-later
# Auto-save: a copy of the document under ~/AgentLink/autosave/<document>
# 5 minutes or 10 changes after the last, the newest 5 kept. The person's
# own file is never written. While a copy is being written a flag file says
# so (~/AgentLink/.saving): Agent Link's watchdog waits for it rather than
# call a long save a hang.
#
# Plain FreeCAD, imported where it is used.

import os
import time

from .files import _save, path, safe, stamp

AUTOSAVE_SECONDS = 300
AUTOSAVE_STEPS = 10
AUTOSAVE_KEEP = 5


def autosave_due(last_t, last_tx, now, tx):
    """A copy is due 5 minutes or 10 changes after the last one."""
    if tx <= last_tx:
        return False
    return (now - last_t) >= AUTOSAVE_SECONDS or (tx - last_tx) >= AUTOSAVE_STEPS


def autosave_dir(doc):
    return path("autosave", safe(doc))


def autosave_file(doc, t=None):
    return os.path.join(autosave_dir(doc), f"{stamp(t)}.FCStd")


def autosave_prune(doc, keep=AUTOSAVE_KEEP):
    d = autosave_dir(doc)
    try:
        files = sorted(f for f in os.listdir(d) if f.endswith(".FCStd"))
    except OSError:
        return []
    gone = files[:-keep] if len(files) > keep else []
    for f in gone:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass
    return gone


def saving_flag():
    return path(".saving")


def set_saving(on):
    p = saving_flag()
    if on:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(str(time.time()))
    else:
        try:
            os.remove(p)
        except OSError:
            pass


def saving(limit=120.0):
    """A save in progress; a stale flag is not."""
    try:
        return time.time() - os.path.getmtime(saving_flag()) < limit
    except OSError:
        return False


def copy_now(d):
    """A copy of document d in its auto-save folder now: the file written."""
    set_saving(True)
    try:
        f = autosave_file(d.Name)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        d.saveCopy(f)
        _save(os.path.join(autosave_dir(d.Name), "about.json"), {"label": d.Label, "fileName": d.FileName or "", "t": time.time()})
        autosave_prune(d.Name)
    finally:
        set_saving(False)
    return f



def now(session):
    """The session's document copied now; the next one counts from here."""
    d = session.doc
    f = copy_now(d)
    # Kept on the session itself too: family_state starts again with each
    # document, the time of the last copy should not.
    session.__dict__.setdefault("_safetynet_autosaved", {})[d.Name] = (time.time(), session.tx)
    return f


def after_change(session, tool=None):
    """After a change: a copy when one is due. Never fails the call."""
    try:
        d = session.doc
        seen = session.__dict__.setdefault("_safetynet_autosaved", {})
        last_t, last_tx = seen.get(d.Name, (getattr(session, "t0", time.time()), 0))
        if autosave_due(last_t, last_tx, time.time(), session.tx):
            now(session)
    except Exception as e:  # noqa: BLE001
        try:
            import FreeCAD

            FreeCAD.Console.PrintWarning(f"SafetyNet: auto-save skipped: {e}\n")
        except Exception:
            pass
