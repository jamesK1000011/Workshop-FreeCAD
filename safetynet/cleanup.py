# SPDX-License-Identifier: LGPL-2.1-or-later
# Recovered copies pruned so the list holds what matters: SafetyNet's own
# auto-save copies and unnamed checkpoints, the newest few a document, none
# past a week, a never-saved scratch document's past a day. Never a copy of
# a document open now, the newest copy of any document, a copy from the last
# crash or forced restart, a copy the person used in the last week, or a
# checkpoint someone named. Removed copies go to the Trash where there is
# one. FreeCAD's own recovery files are FreeCAD's, left to it.
#
# Run at SafetyNet's start and at most once a day after, quietly
# (maybe_prune); by hand with Tools ▸ SafetyNet ▸ Clean Up Copies…, which
# shows what would go first. Plain FreeCAD, imported where it is used.

import os
import shutil
import sys
import time

from .files import _load, _save, _size, path, safe

PARAMS = "User parameter:BaseApp/Preferences/Mod/SafetyNet"
# Setting: (default, what it is)
SETTINGS = {
    "CopiesKeep": (3, "copies kept a document"),
    "CopiesMaxAgeDays": (7, "days a copy is kept"),
    "ScratchMaxAgeDays": (1, "days a never-saved document's copies are kept"),
}
LAST_RUN = "CopiesCleanedAt"
DAY = 86400.0


# ---- what the person used and what the last crash brought back -----------------------------

def _state_file(name):
    return path("safetynet", name)


def mark_used(paths, now=None):
    """Copies the person opened (Use Copy, recovery): kept a week from now."""
    f = _state_file("used.json")
    used = _load(f, {}) or {}
    t = now or time.time()
    for p in paths:
        if p:
            used[os.path.abspath(p)] = t
    _save(f, used)


def used(now=None, days=7):
    """{path: t} of the copies used within days."""
    t = now or time.time()
    return {p: u for p, u in (_load(_state_file("used.json"), {}) or {}).items() if t - float(u or 0) <= days * DAY}


def mark_crash(paths, documents=(), now=None, pid=None):
    """The copies a crash or a forced restart brought back: the newest such
    event replaces the one before (a "Last crash" group while this FreeCAD
    runs, never pruned)."""
    _save(_state_file("last-crash.json"), {"t": now or time.time(), "pid": pid or os.getpid(),
                                          "paths": [os.path.abspath(p) for p in paths if p], "documents": list(documents)})


def last_crash():
    """{"t", "pid", "paths", "documents"} of the last crash, or {}."""
    m = _load(_state_file("last-crash.json"), {}) or {}
    return m if isinstance(m, dict) else {}


def crash_this_session(pid=None):
    """The paths of the last crash's copies when it was this FreeCAD's."""
    m = last_crash()
    return set(m.get("paths") or []) if m.get("pid") == (pid or os.getpid()) else set()


# ---- what there is ----------------------------------------------------------------------

def inventory():
    """SafetyNet's own copies: [{document, path, t, kind, size, scratch,
    named}]. kind: autosave | checkpoint."""
    out = []
    root = path("autosave")
    for n in _dirs(root):
        d = os.path.join(root, n)
        about = _load(os.path.join(d, "about.json"), None)
        for f in _files(d):
            p = os.path.join(d, f)
            out.append({"document": n, "path": p, "t": _mtime(p), "kind": "autosave", "size": _size(p),
                        "file": (about or {}).get("fileName") if about else None, "label": (about or {}).get("label")})
    root = path("checkpoints")
    for n in _dirs(root):
        for e in _load(os.path.join(root, n, "index.json"), []) or []:
            p = e.get("file") or ""
            if os.path.isfile(p):
                out.append({"document": n, "path": p, "t": float(e.get("t") or _mtime(p)), "kind": "checkpoint", "size": _size(p),
                            "file": e.get("fileName"), "label": e.get("label"), "named": bool(e.get("name")) and not e.get("auto"),
                            "id": e.get("id")})
    by_doc = {}
    for c in out:
        by_doc.setdefault(c["document"], []).append(c)
    for doc, cs in by_doc.items():
        known = [c.get("file") for c in cs if c.get("file") is not None]
        never = (not any(known)) if known else str(doc).startswith("Unnamed")
        for c in cs:
            c["scratch"] = bool(never)
    return out


def _dirs(root):
    try:
        return sorted(n for n in os.listdir(root) if os.path.isdir(os.path.join(root, n)))
    except OSError:
        return []


def _files(d):
    try:
        return sorted(f for f in os.listdir(d) if f.endswith(".FCStd"))
    except OSError:
        return []


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


# ---- the rules ----------------------------------------------------------------------------

def plan(copies, now=None, keep=3, max_age_days=7, scratch_days=1, open_names=(), crash=(), used_paths=()):
    """Which copies go: {"go": [...], "keep": [...]}, each copy with "why".
    Per document, newest first: the newest always kept; a copy of an open
    document, from the last crash, used lately or a named checkpoint kept;
    the rest go past the newest `keep`, past `max_age_days`, or for a
    never-saved document past `scratch_days`."""
    t = now or time.time()
    opened = {safe(n) for n in open_names or ()} | set(open_names or ())
    crash, used_paths = {os.path.abspath(p) for p in crash or ()}, {os.path.abspath(p) for p in used_paths or ()}
    out = {"go": [], "keep": []}
    by_doc = {}
    for c in copies or []:
        by_doc.setdefault(c["document"], []).append(c)
    for doc, cs in by_doc.items():
        cs = sorted(cs, key=lambda c: -float(c.get("t") or 0))
        for i, c in enumerate(cs):
            age = (t - float(c.get("t") or 0)) / DAY
            p = os.path.abspath(c["path"])
            why = ("newest" if i == 0 else "open" if doc in opened else "last crash" if p in crash else
                   "used" if p in used_paths else "named" if c.get("named") else None)
            if why:
                out["keep"].append({**c, "why": why})
                continue
            why, extra = ((("pastNewest", {"limit": keep}) if i >= keep else ("tooOld", {"days": max_age_days}) if age > max_age_days else
                           ("scratchTooOld", {"days": scratch_days}) if c.get("scratch") and age > scratch_days else (None, {})))
            out["go" if why else "keep"].append({**c, "why": why or "kept", **extra})
    return out


def summary(rows):
    """{count, mb} of copies."""
    return {"count": len(rows), "mb": round(sum(r.get("size") or 0 for r in rows) / 1048576.0, 1)}


# ---- removing ---------------------------------------------------------------------------

def trash(p, platform=None, home=None):
    """To the Trash where there is one; answers how ("trash" or "removed").
    send2trash when it is installed; on a Mac, ~/.Trash under a name that
    clashes with nothing there; elsewhere removed."""
    try:
        from send2trash import send2trash

        send2trash(p)
        return "trash"
    except ImportError:
        pass
    if (platform or sys.platform) == "darwin":
        bin_ = os.path.join(home or os.path.expanduser("~"), ".Trash")
        if os.path.isdir(bin_):
            name = os.path.basename(p)
            dest = os.path.join(bin_, name)
            stem, ext = os.path.splitext(name)
            n = 1
            while os.path.lexists(dest):
                dest = os.path.join(bin_, f"{stem} {time.strftime('%H-%M-%S')}{'' if n == 1 else ' ' + str(n)}{ext}")
                n += 1
            shutil.move(p, dest)
            return "trash"
    os.unlink(p)
    return "removed"


def remove(rows, bin_=trash):
    """The copies removed (a checkpoint taken off its document's index too).
    {"removed": n, "trashed": n, "mb", "failed": [path]}."""
    done, failed, trashed = [], [], 0
    for r in rows:
        try:
            trashed += bin_(r["path"]) == "trash"
            done.append(r)
        except OSError:
            failed.append(r["path"])
            continue
        if r.get("kind") == "checkpoint":
            idx = os.path.join(path("checkpoints", r["document"]), "index.json")
            entries = _load(idx, []) or []
            _save(idx, [e for e in entries if os.path.abspath(e.get("file") or "") != os.path.abspath(r["path"])])
    return {"removed": len(done), "trashed": trashed, "mb": summary(done)["mb"], "failed": failed}


# ---- with FreeCAD -------------------------------------------------------------------------

def settings(params=None):
    """The person's settings, each from SafetyNet's parameter group."""
    out = {}
    try:
        if params is None:
            import FreeCAD

            params = FreeCAD.ParamGet(PARAMS)
        for k, (d, _) in SETTINGS.items():
            v = params.GetInt(k, d)
            out[k] = v if isinstance(v, int) and v > 0 else d
    except Exception:  # noqa: BLE001 — no FreeCAD: the defaults
        out = {k: d for k, (d, _) in SETTINGS.items()}
    return out


def _open_names():
    try:
        import FreeCAD

        return list(FreeCAD.listDocuments())
    except Exception:  # noqa: BLE001
        return []


def what_goes(now=None, params=None, open_names=None):
    """The plan for the copies here now, by the person's settings."""
    s = settings(params)
    return plan(inventory(), now=now, keep=s["CopiesKeep"], max_age_days=s["CopiesMaxAgeDays"], scratch_days=s["ScratchMaxAgeDays"],
                open_names=_open_names() if open_names is None else open_names, crash=last_crash().get("paths") or (),
                used_paths=used(now, s["CopiesMaxAgeDays"]))


def prune(dry_run=True, now=None, params=None, open_names=None, bin_=trash):
    """What goes ({count, mb, rows}); removed unless dry_run."""
    p = what_goes(now, params, open_names)
    out = {**summary(p["go"]), "rows": p["go"]}
    if not dry_run and p["go"]:
        out.update(remove(p["go"], bin_))
    return out


def maybe_prune(now=None, params=None, open_names=None, bin_=trash, force=False):
    """At start (force) and at most once a day after, quietly: None when
    not due."""
    t = now or time.time()
    try:
        if params is None:
            import FreeCAD

            params = FreeCAD.ParamGet(PARAMS)
        last = float(params.GetString(LAST_RUN, "0") or 0)
    except Exception:  # noqa: BLE001
        params, last = None, 0.0
    if not force and t - last < DAY:
        return None
    if params is not None:
        try:
            params.SetString(LAST_RUN, str(t))
        except Exception:  # noqa: BLE001
            pass
    return prune(dry_run=False, now=t, params=params, open_names=open_names, bin_=bin_)
