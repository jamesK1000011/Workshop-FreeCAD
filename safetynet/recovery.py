# SPDX-License-Identifier: LGPL-2.1-or-later
# Documents back after a crash, a hang or a restart: from SafetyNet's
# auto-saves and checkpoints and from FreeCAD's own recovery files, opened
# beside the person's file as "<label> (recovered HH:MM)" and saved over it
# only with their typed say-so. Also what a hidden FreeCAD holds (hidden.json,
# for whoever restarts it after a crash), the documents to reopen from copies
# after a restart (reopen.json), and FreeCAD's own AutoSave kept on.
# A copy is named after its original once, however often it was recovered,
# one per original (a recovered copy is not brought back beside its own
# original), and kept off File > Open Recent.
#
# Plain FreeCAD, imported where it is used.

import json
import os
import re
import shutil
import tempfile
import time

from . import autosave, checkpoints, settings
from .files import _load, _save, path, safe, stamp
from .refusal import Refused

RECOVERED_FOR = "AgentLinkRecoveredFor"
# Past this a reopen list is stale (a restart that never came back).
REOPEN_LIMIT = 600.0
# The folder a recovered copy is opened from (open_copy).
TMP_PREFIX = "agentlink-recovered-"


# ---- names: a recovered copy named after its original, once -----------------------------

_NAME_TAIL = re.compile(r"(?:_recovered\d*)+$")
_LABEL_TAIL = re.compile(r"(?:\s*\(recovered[^)]*\)|_recovered\d*)+\s*$")


def original_name(name):
    """A document's name with every "_recovered", "_recovered1" … taken off
    its end: the name of the document it was recovered from."""
    n = str(name or "")
    return _NAME_TAIL.sub("", n) or n


def original_label(label):
    """A label with every " (recovered HH:MM)" and "_recovered…" taken off
    its end: AgentLink_recovered (recovered 10:02) (recovered 10:05) -> AgentLink."""
    t = str(label or "")
    return _LABEL_TAIL.sub("", t).strip() or t


def copy_label(label):
    """A recovered copy's label with one suffix: the original's label and
    the newest "(recovered HH:MM)" it carries, or "(recovered)"."""
    t = str(label or "")
    times = re.findall(r"\(recovered ([^)]*)\)", t)
    return f"{original_label(t)} (recovered{' ' + times[-1] if times else ''})"


def from_copy_folder(file):
    """True for a file open_copy opened (in a temporary agentlink-recovered- folder)."""
    return TMP_PREFIX in os.path.basename(os.path.dirname(str(file or "")))


def _changed(d):
    """Changes since the copy was saved: the window's own modified mark when
    there is one (FreeCAD 1.1 reports a document touched as soon as it is
    opened), else touched."""
    try:
        import FreeCAD

        if getattr(FreeCAD, "GuiUp", False):
            import FreeCADGui

            g = FreeCADGui.getDocument(d.Name)
            if g is not None:
                return bool(g.Modified)
    except Exception:
        pass
    try:
        return bool(d.isTouched())
    except Exception:
        return True


def is_recovered(d):
    """True for a document entry ({ name, label, file, recovered }) that is
    itself a recovered copy not yet saved over its file: marked so, opened
    from open_copy's folder, or never saved and named like one."""
    f = d.get("file") or ""
    if d.get("recovered") or from_copy_folder(f):
        return True
    return not f and (original_name(d.get("name")) != str(d.get("name") or "") or original_label(d.get("label")) != str(d.get("label") or ""))


def _keys(d):
    """What names a document's original: its file and its name."""
    f = d.get("original") if is_recovered(d) else d.get("file")
    out = {"name:" + original_name(d.get("name") or d.get("label"))}
    if f and not from_copy_folder(f):
        out.add("file:" + os.path.abspath(f))
    return out


def dedupe(documents):
    """The documents to bring back, one per original: a recovered copy is
    dropped when its original or an earlier copy of it is in the list too.
    Each entry gets "base" and "baseLabel", the original's name and label,
    to name the new copy by; a copy's "file" is its original's."""
    docs = [d for d in documents or [] if isinstance(d, dict) and (d.get("name") or d.get("label"))]
    taken = set()
    for d in docs:
        if not is_recovered(d):
            taken |= _keys(d)
    out = []
    for d in docs:
        e = dict(d)
        if is_recovered(d):
            if _keys(d) & taken:
                continue
            taken |= _keys(d)
            e["file"] = d.get("original") or ""
        e["base"] = original_name(d.get("name") or d.get("label"))
        e["baseLabel"] = original_label(d.get("label") or d.get("name"))
        out.append(e)
    return out


def recent_without_copies(files):
    """FreeCAD's recent-files list without the recovered copies' temporary files."""
    return [f for f in files if f and not from_copy_folder(f)]


def recovery_sources(doc, freecad_recovery=()):
    """What a document could come back from, newest first: our auto-saves,
    checkpoints, and FreeCAD's own recovery files ([(path, t)] passed in).
    Each { source, path, t }."""
    out = []
    d = autosave.autosave_dir(doc)
    try:
        for f in os.listdir(d):
            if f.endswith(".FCStd"):
                p = os.path.join(d, f)
                out.append({"source": "autosave", "path": p, "t": os.path.getmtime(p)})
    except OSError:
        pass
    for e in checkpoints.cp_index(doc):
        if os.path.isfile(e.get("file", "")):
            out.append({"source": "checkpoint", "path": e["file"], "t": os.path.getmtime(e["file"]), "checkpoint": e.get("id"),
                        **({"by": e["by"]} if e.get("by") else {})})
    for p, t in freecad_recovery:
        out.append({"source": "freecad", "path": p, "t": t})
    return sorted(out, key=lambda x: -x["t"])


def freecad_recovery_files(cache_dirs, doc_label=None):
    """FreeCAD's own recovery copies under its cache folders: each holds
    fc_recovery_file.fcstd and an .xml naming the document. [(path, t, label)]"""
    found = []
    for root in cache_dirs:
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for n in names:
            d = os.path.join(root, n)
            f = os.path.join(d, "fc_recovery_file.fcstd")
            if not os.path.isfile(f):
                continue
            label = None
            try:
                with open(os.path.join(d, "fc_recovery_file.xml"), encoding="utf-8", errors="replace") as fh:
                    m = re.search(r"<Label>([^<]*)</Label>", fh.read())
                    label = m.group(1) if m else None
            except OSError:
                pass
            if doc_label is None or label in (None, doc_label):
                found.append((f, os.path.getmtime(f), label))
    return sorted(found, key=lambda x: -x[1])


# ---- with FreeCAD ------------------------------------------------------------------------

def _hm(t):
    return time.strftime("%H:%M", time.localtime(t))


def cache_dirs():
    import FreeCAD

    out = []
    for fn in ("getUserCachePath", "getUserCacheDir"):
        try:
            p = getattr(FreeCAD, fn)()
            if p and p not in out:
                out.append(p)
        except Exception:
            pass
    return out


def forget_recent():
    """Recovered copies' temporary files taken off File ▸ Open Recent."""
    import FreeCAD

    try:
        g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/RecentFiles")
        n = int(g.GetInt("RecentFiles", 4) or 4) + 20
        files = [g.GetString(f"MRU{i}", "") for i in range(n)]
        keep = recent_without_copies(files)
        if keep == [f for f in files if f]:
            return 0
        for i in range(n):
            if i < len(keep):
                g.SetString(f"MRU{i}", keep[i])
            elif g.GetString(f"MRU{i}", ""):
                g.RemString(f"MRU{i}")
        return len([f for f in files if f]) - len(keep)
    except Exception:
        return 0


EMPTY_SHAPES_NOTE = "SafetyNet: FreeCAD's autosave left some cached shapes empty; they are rebuilt on recompute.\n"


def empty_shapes(fcstd):
    """The objects whose cached shapes a saved copy holds as empty blobs
    (FreeCAD's autosave writes "Sketch.InternalShape.bin" of 0 bytes, which
    reading reports as an error in red): {"Sketch", "Pad"}. Read from the
    file's zip index only; nothing is written."""
    import zipfile

    out = set()
    try:
        with zipfile.ZipFile(fcstd) as z:
            for i in z.infolist():
                base = i.filename.rsplit("/", 1)[-1]
                if i.file_size == 0 and base.endswith(".bin") and "." in base[:-4]:
                    out.add(base.split(".", 1)[0])
    except (OSError, zipfile.BadZipFile):
        pass
    return out


def rebuild_empty(nd, names):
    """The objects with empty cached shapes touched and the copy recomputed,
    so their shapes are built again (in memory: the copy lives in its
    temporary folder and nothing is saved). The one plain Report view line
    that says why FreeCAD reported them. True when it recomputed."""
    import FreeCAD

    FreeCAD.Console.PrintMessage(EMPTY_SHAPES_NOTE)
    touched = False
    for n in sorted(names):
        o = nd.getObject(n) if hasattr(nd, "getObject") else None
        if o is not None:
            try:
                o.touch()
                touched = True
            except Exception:  # noqa: BLE001
                pass
    return touched


def open_copy(src, name, label, t):
    """A saved copy opened beside the person's file, never over it: named
    after the original document once, "<name>_recovered" and the label
    "<label> (recovered HH:MM)", however often it was recovered before;
    kept off Open Recent. Cached shapes FreeCAD's autosave left empty are
    rebuilt by its recompute, with one line saying so."""
    import FreeCAD

    name, label = original_name(name), original_label(label)
    tmpd = tempfile.mkdtemp(prefix=TMP_PREFIX)
    tmp = os.path.join(tmpd, f"{safe(name)}_recovered.FCStd")
    shutil.copy2(src, tmp)
    empty = empty_shapes(tmp)
    nd = FreeCAD.openDocument(tmp)
    if empty:
        rebuild_empty(nd, empty)
    try:
        nd.recompute()
    except Exception:
        pass
    nd.Label = f"{label} (recovered {_hm(t)})"
    forget_recent()
    return nd


def recover_docs(documents, since=None):
    """The newest copy of each document that opens, beside its file: one
    per original (dedupe), named after the original. (recovered, failed)"""
    rec, failed, opened = [], [], []
    for d in dedupe(documents):
        name, label, fname = d.get("name"), d["baseLabel"], d.get("file") or ""
        if not name:
            continue
        fc = [(p, t) for p, t, _ in freecad_recovery_files(cache_dirs(), d.get("label") or label)]
        srcs = recovery_sources(name, fc)
        if not srcs:
            failed.append({"label": label, "why": "no saved copy (no checkpoint, auto-save or FreeCAD recovery file)"})
            continue
        errors = []
        for src in srcs:
            try:
                nd = open_copy(src["path"], d["base"], label, src["t"])
            except Exception as e:
                errors.append(f"{src['source']} {_hm(src['t'])}: {e}")
                continue
            m = dict(nd.Meta or {})
            m[RECOVERED_FOR] = json.dumps({"file": fname, "label": label, "source": src["source"], "t": src["t"]})
            nd.Meta = m
            lost = None
            if since:
                mins = max(0, int(round((float(since) - src["t"]) / 60.0)))
                lost = "nothing after it lost" if mins == 0 else f"about {mins} min of changes lost"
            opened.append(src["path"])
            rec.append({"label": label, "document": nd.Name, "as": nd.Label, "source": src["source"], "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(src["t"])),
                        **({"lost": lost} if lost else {}), **({"skipped": errors} if errors else {}), "file": fname or None})
            break
        else:
            failed.append({"label": label, "why": "; ".join(errors)[:400]})
    _remember(opened, [r["label"] for r in rec], crash=bool(since))
    return rec, failed


def _remember(paths, labels, crash):
    """Copies opened kept from pruning a week (cleanup.used); after a crash
    (since given) or a forced restart they are the Last crash too."""
    if not paths:
        return
    try:
        from . import cleanup

        cleanup.mark_used(paths)
        if crash:
            cleanup.mark_crash(paths, labels)
    except Exception:  # noqa: BLE001 — never fail a recovery over this
        pass


def listing():
    """Each document with saved copies (open ones and those with folders here)."""
    import FreeCAD

    names = {}
    for d in FreeCAD.listDocuments().values():
        names[d.Name] = {"label": d.Label, "file": d.FileName or ""}
    for sub in ("autosave", "checkpoints"):
        try:
            for n in os.listdir(path(sub)):
                names.setdefault(n, {"label": n, "file": ""})
        except OSError:
            pass
    try:
        from .cleanup import crash_this_session

        crash = crash_this_session()
    except Exception:  # noqa: BLE001
        crash = set()
    out = []
    for n, info in sorted(names.items()):
        fc = [(p, t) for p, t, _ in freecad_recovery_files(cache_dirs(), info["label"])]
        srcs = recovery_sources(n, fc)[:6]
        if srcs:
            out.append({"document": n, "label": info["label"], "t": srcs[0]["t"],
                        "copies": [{"source": x["source"], "time": time.strftime("%Y-%m-%d %H:%M", time.localtime(x["t"])), "path": x["path"],
                                   **({"by": x["by"]} if x.get("by") else {}),
                                   **({"crash": True} if os.path.abspath(x["path"]) in crash else {})} for x in srcs]})
    return newest_first(out)


def newest_first(rows):
    """Documents with copies, the one with the newest copy first."""
    rows = sorted(rows, key=lambda r: -float(r.get("t") or 0))
    for r in rows:
        r.pop("t", None)
    return rows


def accept(ref, confirm):
    """A recovered copy saved over the person's file, with their typed
    confirm; what was there kept under ~/AgentLink/replaced. The document."""
    import FreeCAD

    nd = next((d for d in FreeCAD.listDocuments().values() if ref in (d.Name, d.Label)), None)
    if nd is None:
        raise Refused("not_found", f"document {ref!r}: not open — app_recover (action list) shows the copies.")
    raw = (nd.Meta or {}).get(RECOVERED_FOR)
    if not raw:
        raise Refused("invalid_state", f"{nd.Label} is not a recovered copy.")
    info = json.loads(raw)
    target = info.get("file")
    if not target:
        raise Refused("invalid_state", f"{nd.Label} was never saved to a file: doc_save {{ path }} saves it where the person says.")
    want = f"save over {os.path.basename(target)}"
    if (confirm or "").strip() != want:
        raise Refused("not_allowed", f"confirm: \"{want}\", word for word, typed by the person — this replaces their file with the recovered copy. Nothing was changed.")
    other = next((d for d in FreeCAD.listDocuments().values() if d is not nd and d.FileName and os.path.abspath(d.FileName) == os.path.abspath(target)), None)
    if other is not None:
        raise Refused("invalid_state", f"{target} is open as {other.Label}: close it first (doc_close — its unsaved changes are the person's call), then accept again.")
    if os.path.isfile(target):
        backup = path("replaced", f"{stamp()}-{os.path.basename(target)}")
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        shutil.copy2(target, backup)
    else:
        backup = None
    m = dict(nd.Meta or {})
    m.pop(RECOVERED_FOR, None)
    nd.Meta = m
    nd.saveAs(target)
    nd.Label = info.get("label") or nd.Label
    return nd, {"saved": target, "document": nd.Name, **({"previousFile": backup} if backup else {}),
                "note": "The recovered copy is now the file; what was there before is kept at previousFile."}


# ---- what a hidden FreeCAD holds, for after a crash ----------------------------------------

def write_hidden():
    """~/AgentLink/hidden.json: the documents this hidden FreeCAD holds, for
    the one that starts it again after a crash to recover (app_recover)."""
    import FreeCAD

    _save(path("hidden.json"), {"pid": os.getpid(), "t": time.time(), "docs": [entry(d) for d in FreeCAD.listDocuments().values()]})


def entry(d):
    """An open document as recovery lists it; a recovered copy marked, with
    the file it was recovered for as "original"."""
    e = {"name": d.Name, "label": d.Label, "file": d.FileName or ""}
    raw = (getattr(d, "Meta", None) or {}).get(RECOVERED_FOR)
    if raw or from_copy_folder(e["file"]):
        e["recovered"] = True
        try:
            e["original"] = json.loads(raw).get("file") or "" if raw else ""
        except ValueError:
            e["original"] = ""
    return e


# ---- documents reopened from copies after a restart ----------------------------------------

def reopen_file():
    return path("reopen.json")


def keep_for_reopen(docs):
    """Before FreeCAD quits to start again: each document that is not being
    saved copied to its auto-save folder, to reopen beside its file when
    FreeCAD is back. [{ name, label, file, copy, t }]"""
    out = []
    try:
        import FreeCAD

        others = [entry(x) for x in FreeCAD.listDocuments().values() if x not in docs]
    except Exception:
        others = []
    for d in docs:
        f = autosave.copy_now(d)
        out.append({**entry(d), "copy": f, "t": time.time()})
    # A recovered copy whose original comes back too is not reopened again
    # (its copy stays in its auto-save folder, under Recovered Copies).
    out = reopen_list(others, out)
    if out:
        _save(reopen_file(), {"t": time.time(), "docs": out})
    return out


def reopen_list(others, kept):
    """Of the copies kept for a restart, those to reopen: one per original,
    none for a recovered copy whose original is open (others) or kept too."""
    left = dedupe([*[o for o in others if not is_recovered(o)], *kept])
    want = {(e.get("name"), e.get("copy")) for e in left if e.get("copy")}
    return [e for e in kept if (e.get("name"), e.get("copy")) in want]


def reopen_pending(now=None):
    """The copies to reopen, once: the list is taken away as it is read; a
    stale one is dropped."""
    m = _load(reopen_file(), None)
    try:
        os.remove(reopen_file())
    except OSError:
        pass
    if not isinstance(m, dict) or (now or time.time()) - float(m.get("t") or 0) > REOPEN_LIMIT:
        return []
    return [c for c in m.get("docs") or [] if isinstance(c, dict)]


def reopen_now():
    """Open each pending copy beside its file. The labels opened."""
    opened, fresh, used = [], set(), []
    for c in reopen_pending():
        try:
            if os.path.isfile(c.get("copy", "")):
                nd = open_copy(c["copy"], c.get("name") or "doc", c.get("label") or c.get("name") or "doc", float(c.get("t") or time.time()))
                opened.append(nd.Label)
                used.append(c["copy"])
                fresh.add(nd.Name)
        except Exception as e:  # noqa: BLE001
            try:
                import FreeCAD

                FreeCAD.Console.PrintWarning(f"SafetyNet: could not reopen {c.get('label')} from its copy: {e}\n")
            except Exception:
                pass
    _remember(used, opened, crash=True)
    try:
        tidy(fresh)
    except Exception:  # noqa: BLE001
        pass
    return opened


def tidy(fresh=()):
    """After a restart: a recovered copy FreeCAD reopened from its temporary
    file is closed when its original is open and it has no changes of its
    own, else named after its original once; and the temporary files are
    taken off Open Recent. fresh: the copies just reopened, left as they are."""
    import FreeCAD

    docs = list(FreeCAD.listDocuments().values())
    es = [(d, entry(d)) for d in docs]
    originals = set()
    for _, e in es:
        if not is_recovered(e):
            originals |= _keys(e)
    for d, e in es:
        if d.Name in fresh or not from_copy_folder(e["file"]):
            continue
        touched = _changed(d)
        if _keys(e) & originals and not touched:
            FreeCAD.closeDocument(d.Name)
            continue
        lab = copy_label(d.Label)
        if lab != d.Label:
            d.Label = lab
    forget_recent()


class Reopen:
    """What SafetyNet offers Agent Link as its "reopen" service."""

    keep = staticmethod(keep_for_reopen)
    pending = staticmethod(reopen_pending)
    now = staticmethod(reopen_now)


# ---- FreeCAD's own auto-recovery ------------------------------------------------------------

def autosave_on():
    """FreeCAD's own recovery copies stay on: turned on once if they are off,
    and the change logged."""
    try:
        import FreeCAD

        al = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/AgentLink")
        if al.GetBool("AutoRecoveryChecked", False):
            return False
        g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
        changed = False
        if not g.GetBool("AutoSaveEnabled", True):
            g.SetBool("AutoSaveEnabled", True)
            settings.settings_log({"tool": "safetynet", "path": "BaseApp/Preferences/Document", "name": "AutoSaveEnabled", "from": False, "to": True, "restart": False,
                                   "why": "FreeCAD's own recovery copies kept on for unattended use"})
            changed = True
        al.SetBool("AutoRecoveryChecked", True)
        return changed
    except Exception:
        return False
