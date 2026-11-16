# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's answers, one function per tool: fn(ctx, args) -> dict, over its
# plain modules. ctx is the session the call runs in: Agent Link's Session
# when Agent Link runs it (fam_history / fam_safety bind these), or
# SafetyNet's own LocalSession (local.py) when its commands and dock run
# them with no agent. A refusal is a Refused; the family layer turns it into
# Agent Link's. Nothing here imports Agent Link.
import os
import shutil
import sys
import time

from . import checkpoints, macros, recovery, settings
from .files import _load, path, stamp
from .refusal import Refused


def bad(msg):
    return Refused("invalid_input", msg)


# ---- history ------------------------------------------------------------------------------


def history_checkpoint(s, a):
    d = s.doc
    if a.get("list"):
        return {"document": d.Label, "checkpoints": [
            {"checkpoint": e["id"], **({"name": e["name"]} if e.get("name") else {}), "time": stamp(e.get("t")), "bytes": e.get("bytes"),
             **({"auto": True} if e.get("auto") else {}), **({"by": e["by"]} if e.get("by") else {})} for e in checkpoints.cp_index(d.Name)]}
    name = a.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip() or len(name) > 60):
        raise Refused("invalid_input", "name: a short name for the checkpoint (60 characters at most).")
    e, dropped = checkpoints.take(s, name)
    out = {"checkpoint": e["id"], **({"name": name} if name else {}), "step": e["step"], "file": e["file"], "bytes": e["bytes"],
           "note": "A saved copy: history_restore comes back to it even past the undo stack, or after FreeCAD restarts."}
    if dropped:
        out["dropped"] = [x["id"] for x in dropped]
    return out


def history_restore(s, a):
    return checkpoints.restore(s, a.get("checkpoint"))


# ---- recovery -----------------------------------------------------------------------------


def app_recover(s, a):
    import FreeCAD

    action = a.get("action", "list")
    if action == "list":
        return {"documents": recovery.listing(), "note": "action auto { documents } opens the newest good copy of each beside its file; accept { document, confirm } saves one over its file."}
    if action == "auto":
        docs = a.get("documents")
        if not isinstance(docs, list) or not docs:
            raise bad("documents: [{ name, label, file }] — the documents to bring back (app_recover lists what has copies).")
        rec, failed = recovery.recover_docs(docs, a.get("since"))
        again = [f["label"] for f in failed if f.get("notAgain")]
        failed = [f for f in failed if not f.get("notAgain")]
        if rec:
            s.switch(FreeCAD.getDocument(rec[0]["document"]))
        return {"recovered": rec, **({"failed": failed} if failed else {}),
                **({"notRecoveredAgain": again, "why": recovery.NOT_AGAIN} if again else {}),
                "note": "Opened beside the person's files as \"(recovered …)\"; their files are untouched. accept { document, confirm: \"save over <file name>\" } typed by them saves one over its file."}
    if action == "accept":
        nd, out = recovery.accept(a.get("document"), a.get("confirm"))
        s.switch(nd)
        return out
    raise bad("action: list | auto { documents, since } | accept { document, confirm }.")

# ---- settings -------------------------------------------------------------------------


def pref_history(s, a):
    return {"changes": settings.history_rows(int(a.get("limit", 20) or 20)),
            "note": "Newest first. pref_rollback { to: change } puts the settings back as they were before that change (a snapshot of the whole settings file)."}


def pref_rollback(s, a):
    import FreeCAD

    to = a.get("to")
    if to in (None, ""):
        raise bad("to: a change's number (pref_history) or a time, YYYYMMDD-HHMMSS.")
    snap = settings.settings_snapshot_for(to)
    if not snap:
        raise Refused("not_found", f"to {to!r}: no settings snapshot for it — pref_history lists the changes with theirs.")
    gui = getattr(FreeCAD, "GuiUp", False)
    if not gui:
        hb = _load(path("heartbeat.json"), {}) or {}
        if time.time() - float(hb.get("t") or 0) < 10:
            raise Refused("invalid_state", "The FreeCAD window is open with its link off: it would write its own settings over the rollback as it quits. Turn its link on (the rollback then restarts it) or close it, then pref_rollback again. Nothing was changed.")
    if not gui and not os.environ.get("AGENTLINK_SUPERVISED"):
        raise Refused("unavailable", "Rolling settings back needs FreeCAD to start again around the file: through the window's link, or the supervised server the launcher runs. Nothing was changed.")
    restart = (getattr(getattr(s, "server", None), "tools", None) or {}).get("app_restart")
    if gui and restart is None and getattr(s, "in_place", False):
        # SafetyNet on its own in the window (no Agent Link to restart
        # FreeCAD): the snapshot read into the running settings instead.
        current = settings.snapshot_now()
        settings.settings_log({"tool": "pref_rollback", "to": str(to), "restoredFrom": snap, "snapshot": current, "restart": False, "inPlace": True})
        settings.apply_in_place(snap)
        return {"rolledBackTo": os.path.basename(snap), "before": current,
                "note": "Read into FreeCAD's settings now and saved; a setting FreeCAD reads only at start takes effect when it next opens. Rolling back to the newest change undoes this."}
    if gui and restart is None:
        raise Refused("unavailable", "No app_restart here to start FreeCAD again around the file. Nothing was changed.")
    current = settings.snapshot_now()
    settings.settings_log({"tool": "pref_rollback", "to": str(to), "restoredFrom": snap, "snapshot": current, "restart": True})
    if gui:
        out = restart.fn({"_cfg_from": snap, "save": a.get("save", "agent")})
        out.update({"rolledBackTo": os.path.basename(snap), "note": "FreeCAD quits, its settings file is put back, and it opens again in the background with its documents. pref_rollback again with the newest change undoes this."})
        return out
    shutil.copy2(snap, settings.user_cfg())
    s.exit_after_reply = "nosave"
    return {"rolledBackTo": os.path.basename(snap), "restarting": "the hidden FreeCAD, at once (the window is closed: it reads these settings when it next opens)"}


# ---- macros ---------------------------------------------------------------------------


def _macro(name):
    if not macros.macro_name_ok(name):
        raise bad("name: letters, digits, spaces, - and _ (60 at most; a .py macro with its .py), no folders.")
    return macros.macro_path(name)


def macro_save(s, a):
    VERSION = getattr(sys.modules.get("agentlink.server"), "VERSION", "?")
    name = a.get("name")
    p = _macro(name)
    if os.path.exists(p) and not a.get("overwrite"):
        raise Refused("invalid_state", f"A macro named {name} is there already ({p}): another name, or overwrite: true (it then needs approving again).")
    calls = list(s.calls)
    lo, hi = a.get("from"), a.get("to")

    def tx_of(ref):
        """A from / to bound as an undo-step count: a step number (the
        calls up to that step) or a checkpoint of this session."""
        if ref is None:
            return None
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            n = int(ref)
            return max([c["tx"] for c in calls if c["step"] <= n] or [0])
        cp = checkpoints.find(s, ref)
        if not cp:
            raise Refused("not_found", f"{ref!r}: no such checkpoint or step.")
        if cp.get("session") != id(s):
            raise Refused("invalid_state", f"{cp['id']} is from an earlier session: its steps are not here to save — from: a step of this one.")
        return int(cp.get("tx", 0))

    t0, t1 = tx_of(lo), tx_of(hi)
    picked = [c for c in calls if (t0 is None or c["tx"] > t0) and (t1 is None or c["tx"] <= t1)]
    # A step undone and not redone is not part of the work.
    picked = [c for c in picked if c["tx"] <= s.tx]
    if not picked:
        raise Refused("invalid_state", "No changing calls in that range to save: make the part first, or widen from / to.")
    params = a.get("params") or {}
    if not isinstance(params, dict) or any(not isinstance(v, (int, float, str)) or isinstance(v, bool) for v in params.values()):
        raise bad("params: { name: number or text } — the key sizes, e.g. { \"wall\": 2.0, \"length\": 60 }; each place a value appears in the calls takes its name.")
    made = [o.Label for o in s.bodies()]
    header = [
        f"{name}: made by Agent Link {VERSION} from {len(picked)} calls of a session on {time.strftime('%Y-%m-%d %H:%M')}",
        f"Makes: {', '.join(made) or 'the changes below'} in {s.doc.Label if s.doc else 'the document'}",
        "Runs through agentlink.run(tool, arguments): the same refusals and undo steps as live calls.",
        "Run by Agent Link only once approved (macro_approve, the person's typed OK); a change to this file needs approving again.",
    ]
    text = macros.macro_text(name, picked, params, header)
    compile(text, p, "exec")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    state = macros.approval_state(name, p)
    consts, _ = macros.macro_calls(text)
    return {"macro": name, "path": p, "calls": len(picked), "constants": consts, "approved": state == "approved",
            "note": "Saved in FreeCAD's macro folder (Macro › Macros… runs it by hand too). Agent Link runs it only after the person approves it: macro_approve { name, confirm: \"approve " + name + "\" } typed by them."}


def macro_list(s, a):
    d, rows = macros.listing()
    return {"folder": d, "macros": rows}


def macro_show(s, a):
    p = _macro(a.get("name"))
    if not os.path.isfile(p):
        raise Refused("not_found", f"No macro {a.get('name')} in {os.path.dirname(p)}: macro_list lists them.")
    with open(p, encoding="utf-8", errors="replace") as f:
        text = f.read()
    try:
        consts, calls = macros.macro_calls(text)
    except SyntaxError as e:
        consts, calls = {}, []
        text = f"(does not parse: {e})\n" + text
    return {"name": a.get("name"), "state": macros.approval_state(a.get("name"), p), "constants": consts, "calls": len(calls),
            "text": text if len(text) <= 6000 else text[:6000] + f"\n… ({len(text)} characters in all)"}


def macro_approve(s, a):
    name = a.get("name")
    p = _macro(name)
    if not os.path.isfile(p):
        raise Refused("not_found", f"No macro {name}: macro_list lists them.")
    want = f"approve {name}"
    if (a.get("confirm") or "").strip() != want:
        raise Refused("not_allowed", f"confirm: \"{want}\", word for word, typed by the person — a macro is Python that runs with the Mac's full reach, so approving it is theirs. Show them macro_show first. Nothing was changed.")
    e = macros.approve(name, p)
    return {"approved": name, "sha256": e["sha256"], "note": "macro_run runs it from now on; a change to its file needs approving again."}


def macro_unapprove(s, a):
    name = a.get("name")
    _macro(name)
    gone = macros.unapprove(name)
    return {"unapproved": name, "was": bool(gone)}


def macro_run(s, a):
    name = a.get("name")
    p = _macro(name)
    if not os.path.isfile(p):
        raise Refused("not_found", f"No macro {name}: macro_list lists them.")
    state = macros.approval_state(name, p)
    if state != "approved":
        why = "its file changed since it was approved" if state == "changed" else "it has not been approved"
        raise Refused("not_allowed", f"{name} is not run: {why}. The person approves it: macro_approve {{ name: \"{name}\", confirm: \"approve {name}\" }} typed by them (macro_show shows it first).")
    with open(p, encoding="utf-8") as f:
        text = f.read()
    params = a.get("params") or {}
    if not isinstance(params, dict):
        raise bad("params: { CONSTANT: value } — the macro's named sizes (macro_show lists them).")
    tree, missing = macros.with_params(text, params)
    if missing:
        consts, _ = macros.macro_calls(text)
        raise bad(f"params: {', '.join(missing)} — not among the macro's named sizes ({', '.join(consts) or 'none'}).")
    # Run as FreeCAD's Macro dialog runs it (macros.run_file); a macro of
    # Agent Link calls inside Agent Link's serving of them.
    around = None
    if macros.uses_agentlink(text):
        server = getattr(s, "server", None)
        if server is None or "agentlink" not in sys.modules:
            raise Refused("invalid_state", f"{name} is made of Agent Link calls: it runs through Agent Link for FreeCAD (its panel or an agent), not alone.")
        around = sys.modules["agentlink"].serving(server)
    try:
        has_doc = s.doc is not None
    except Exception:  # noqa: BLE001 — no document open
        has_doc = False
    cp = checkpoints.take(s, f"before macro {name}", auto=True)[0] if has_doc else None
    n0 = len(s.calls)
    try:
        macros.run_file(tree, p, around)
    except Exception as e:
        ran = len(s.calls) - n0
        if cp is None:
            raise Refused("failed", f"{name} stopped: {e}. No document was open before it, so there was nothing to roll back.")
        try:
            back = checkpoints.restore(s, cp["id"])
            how = back.get("how")
        except Exception as e2:
            how = f"not rolled back ({e2})"
        made = f" after {ran} call{'s' if ran != 1 else ''}" if around is not None else ""
        raise Refused("failed", f"{name} stopped{made}: {e}. Rolled back whole ({how}) to how it was before.")
    out = {"ran": name, **({"calls": len(s.calls) - n0} if around is not None else {}), **({"params": params} if params else {})}
    try:
        out["bodies"] = [o.Label for o in s.bodies()]
    except Exception:  # noqa: BLE001 — the macro may have closed the document
        pass
    if cp is not None:
        out.update({"checkpoint": cp["id"], "note": f"history_restore {{ checkpoint: {cp['id']} }} goes back to before it."})
    return out


HANDLERS = {f.__name__: f for f in (
    history_checkpoint, history_restore,
    macro_save, macro_list, macro_show, macro_approve, macro_unapprove, macro_run,
    app_recover, pref_history, pref_rollback,
)}


def bound(session):
    """{tool name: fn(args)} for one session: what the family layer wraps."""
    return {n: (lambda a, f=f: f(session, a)) for n, f in HANDLERS.items()}
