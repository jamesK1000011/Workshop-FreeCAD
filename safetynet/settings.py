# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's settings kept safe: user.cfg copied before each change (the last
# 20 kept, under ~/AgentLink/settings), every change logged
# (~/AgentLink/settings-log.jsonl), and the snapshot to roll back to found by
# a change's number or a time.
#
# Plain FreeCAD, imported where it is used.

import json
import os
import shutil
import time

from .files import path, stamp

SETTINGS_KEEP = 20


def settings_snapshot(cfg):
    """Copy user.cfg before a change; the last 20 kept. The copy's path."""
    d = path("settings")
    os.makedirs(d, exist_ok=True)
    t = time.time()
    base = f"{stamp(t)}-{int((t % 1) * 1000):03d}"
    dest, k = os.path.join(d, base + ".cfg"), 1
    while os.path.exists(dest):
        dest, k = os.path.join(d, f"{base}-{k:02d}.cfg"), k + 1
    shutil.copy2(cfg, dest)
    fs = sorted(f for f in os.listdir(d) if f.endswith(".cfg"))
    for f in fs[:-SETTINGS_KEEP] if len(fs) > SETTINGS_KEEP else []:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass
    return dest


def settings_log(entry):
    p = path("settings-log.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.time(), **entry}, default=str) + "\n")


def settings_history(limit=20):
    out = []
    try:
        with open(path("settings-log.jsonl"), encoding="utf-8") as f:
            for i, line in enumerate(f):
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                e["change"] = i + 1
                out.append(e)
    except OSError:
        pass
    return out[-limit:][::-1] if limit else out[::-1]


def settings_snapshot_for(ref):
    """The snapshot taken before a change (its number) or at a time stamp:
    the newest whose name is at or before it."""
    d = path("settings")
    try:
        fs = sorted(f for f in os.listdir(d) if f.endswith(".cfg"))
    except OSError:
        return None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit() and len(ref) < 8):
        e = next((x for x in settings_history(0) if x["change"] == int(ref)), None)
        if not e or not e.get("snapshot"):
            return None
        return e["snapshot"] if os.path.isfile(e["snapshot"]) else None
    ref = str(ref)
    pick = [f for f in fs if f[: len(ref)] <= ref or f.startswith(ref)]
    return os.path.join(d, pick[-1]) if pick else None


def history_rows(limit=20):
    """The changes for an agent or the panel, newest first."""
    out = []
    for r in settings_history(limit):
        row = {"change": r["change"], "time": stamp(r.get("t")), "tool": r.get("tool")}
        for k in ("path", "name", "from", "to", "applies"):
            if r.get(k) is not None:
                row[k] = r[k]
        if r.get("restart"):
            row["restart"] = True
        out.append(row)
    return out


# ---- with FreeCAD: a snapshot before each change, the change logged after ----------------

def user_cfg():
    import FreeCAD

    return os.path.join(FreeCAD.getUserConfigDir(), "user.cfg")


def snapshot_now():
    """user.cfg as it is now (written out first), copied; None when FreeCAD
    keeps no settings file here."""
    try:
        import FreeCAD

        FreeCAD.saveParameter()
        if os.path.isfile(user_cfg()):
            return settings_snapshot(user_cfg())
    except Exception:
        pass
    return None


# The snapshot taken as a change began, for the log entries that follow it.
_pending = {"snapshot": None, "tool": None, "t": 0.0}


def changing(tool=None, where=None):
    """Before a change (Agent Link's setting_changing event)."""
    _pending.update({"snapshot": snapshot_now(), "tool": tool, "t": time.time()})


def changed(where, name, old, new, tool=None, restart=False, applies=None, **_):
    """After a change (Agent Link's setting_changed event): logged with the
    snapshot taken as it began (within a minute)."""
    snap = _pending["snapshot"] if time.time() - _pending["t"] < 60 else None
    entry = {"tool": tool or _pending.get("tool"), "path": where, "name": name, "from": old, "to": new, "restart": bool(restart), "snapshot": snap}
    if applies:
        entry["applies"] = applies
    try:
        settings_log(entry)
    except Exception:
        pass
    return entry


def apply_in_place(snap):
    """A snapshot read into the running FreeCAD's settings (the whole
    "User parameter:" tree replaced from it) and written out at once, for a
    rollback with nothing to restart FreeCAD around the file."""
    import FreeCAD

    FreeCAD.ParamGet("User parameter:").Import(snap)
    FreeCAD.saveParameter()
