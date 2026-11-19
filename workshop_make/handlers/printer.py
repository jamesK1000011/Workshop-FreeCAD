# SPDX-License-Identifier: LGPL-2.1-or-later
# Printers on the network: kept by name (the key or password in
# ~/AgentLink/printers.json, never given back), their state, a G-code file
# sent to one, and a job paused or stopped. Starting, pausing and stopping a
# print are the person's to decide (red team 3, R3-1). With Agent Link, each
# needs the person's approval through the client (approve_file, Agent
# Link's hooks.person_ok), bound to the printer, the file and its SHA-256;
# a typed confirm is refused, as an agent can type it. Without Agent Link
# (no agent), the person's typed confirm. printer_send reads the file first:
# commands that change the printer, and heat over the caps, need the same
# approval (R3-4).

import hashlib
import os

from workshop.guard import read_ok

from .. import gcodecheck as G
from .. import printers as P
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal
# Agent Link's approval (hooks.person_ok) and its read check (paths.in_file),
# lent the same way. HUB: True when Agent Link binds these handlers.
PERSON_OK = None
IN_FILE = None
HUB = False
# The approval's kind: one of Agent Link's approve_file kinds
# (approvals.FILE_KINDS), so the client asks with approve_file.
KIND = "dialog"


def _err(e):
    return ToolError(e.code, e.message)


def get(s, name):
    ps = P.load(s.out_dir)
    if not ps:
        raise ToolError("not_found", "No printer kept yet: printer_add { name, kind, url, key } first.")
    if name is None and len(ps) == 1:
        name = next(iter(ps))
    if name not in ps:
        raise ToolError("not_found", f"printer {name!r}: not kept — the printers: {', '.join(ps)}." if name else f"printer: say which — {', '.join(ps)}.")
    return name, ps[name]


def _ask(kind, name, title, lines, sha, shown):
    import inspect

    ask = PERSON_OK
    try:
        takes = "shown" in inspect.signature(ask).parameters
    except (TypeError, ValueError):
        takes = False
    return ask(kind, name, title, lines, sha, None, shown=shown) if takes else ask(kind, name, title, lines, sha, None)


def person_ok(a, word, name, p, title, lines, file=None, sha=None):
    """None once the person approved this action, else the pending answer.
    With Agent Link: its approval (approve_file), for this printer, this
    action and this file's sha256; a typed confirm is refused. Without it:
    the typed confirm "<word> <name>"."""
    if HUB:
        if a.get("confirm") not in (None, ""):
            raise ToolError("invalid_input", f"confirm: not taken with Agent Link. An agent can type it. The person approves {word} through the client: call again without confirm; the answer is pending with the approve_file arguments.")
        if PERSON_OK is None:
            raise ToolError("unavailable", "This Agent Link has no approval (person_ok). Update Agent Link, then ask again. Nothing was sent to the printer.")
        # The approval names the printer (name, address), the action and the
        # file's sha256: another printer, address or file needs a new one.
        fp = "sha256:" + hashlib.sha256(f"{word}\0{name}\0{p.get('url')}\0{sha or ''}".encode("utf-8")).hexdigest()
        shown = {"document": f"printer {name} ({p.get('kind')}, {p.get('url')})", "button": word}
        if file:
            shown["file"] = f"{os.path.basename(file)}, {sha}"
        got = _ask(KIND, f"printer {word} {name}", title, lines, fp, shown)
        if got.get("ok"):
            return None
        return {"pending": True, "printer": name, "action": word, **({"sha256": sha} if sha else {}),
                **({"approve": got["approve"]} if got.get("approve") else {}), "next": got.get("next"),
                "note": "Nothing was sent to the printer. After the person approves, call this tool again with the same arguments."}
    want = f"{word} {name}"
    if (a.get("confirm") or "").strip() != want:
        raise ToolError("invalid_input", f"confirm: \"{want}\", word for word. Ask the person first; it is their call, not yours.")
    return None


def printer_add(s, a):
    name = str(a.get("name") or "").strip()
    if not name or len(name) > 40:
        raise ToolError("invalid_input", "name: what to call it, 1 to 40 characters.")
    try:
        kind = P.kind_of(a.get("kind"))
        url = P.normal_url(a.get("url"))
    except P.PrinterError as e:
        raise _err(e)
    p = {"kind": kind, "url": url}
    if a.get("key"):
        p["key"] = str(a["key"])
    if a.get("password"):
        p["password"] = str(a["password"])
        p["user"] = str(a.get("user") or "maker")
    if kind == "octoprint" and not p.get("key"):
        raise ToolError("invalid_input", "key: OctoPrint needs an API key (its Settings › Application Keys, or API).")
    if kind == "prusalink" and not (p.get("key") or p.get("password")):
        raise ToolError("invalid_input", "key, or user and password: PrusaLink's API key or its digest login (on the printer's screen, Settings › Network › PrusaLink).")
    ps = P.load(s.out_dir)
    replaced = name in ps
    ps[name] = p
    P.save(s.out_dir, ps)
    out = {"added": P.public(name, p), "replaced": replaced, "kept": P.shown_path()}
    local = P.is_local(url)
    warn = []
    if not local:
        warn.append(f"{url} is not on this network (not a private address or a .local name). Keep printers on the LAN.")
    if url.startswith("http://") and (p.get("key") or p.get("password")):
        warn.append("Plain http sends the key in clear text on the network.")
    if warn:
        out["warning"] = " ".join(warn)
    if a.get("check", local):
        try:
            st = P.status(p)
            out["reached"] = True
            out["state"] = st.get("state")
        except P.PrinterError as e:
            out["reached"] = False
            out["why"] = e.message
    return out


def printer_list(s, a):
    ps = P.load(s.out_dir)
    if a.get("remove"):
        if a["remove"] not in ps:
            raise ToolError("not_found", f"{a['remove']!r}: not kept — the printers: {', '.join(ps) or 'none'}.")
        ps.pop(a["remove"])
        P.save(s.out_dir, ps)
    return {"printers": [P.public(n, p) for n, p in ps.items()], **({"removed": a["remove"]} if a.get("remove") else {})}


def printer_status(s, a):
    name, p = get(s, a.get("printer"))
    try:
        return {"printer": name, "kind": p["kind"], **P.status(p)}
    except P.PrinterError as e:
        raise _err(e)


def printer_send(s, a):
    name, p = get(s, a.get("printer"))
    f = a.get("file")
    if not f:
        raise ToolError("invalid_input", "file: the G-code to send. slice or slice_with writes it.")
    path = os.path.expanduser(f)
    path = path if os.path.isabs(path) else os.path.join(s.out_dir, path)
    path = read_ok(s, "printer_send", path, "file", IN_FILE, ToolError)
    if not os.path.isfile(path):
        raise ToolError("not_found", f"{f}: no such file. Slice it first.")
    if not path.lower().endswith(P.GCODE):
        raise ToolError("invalid_input", f"file: G-code only ({', '.join(P.GCODE)}).")
    try:
        storage = P.storage_of(p["kind"], a.get("storage"))
    except P.PrinterError as e:
        raise _err(e)
    sha, issues = G.scan(path)
    start = bool(a.get("start"))
    if start or issues:
        word = "start" if start else "send"
        lines = [f"Printer: {name} ({p['kind']}, {p['url']})", f"File: {path}", f"sha256: {sha[7:23]}…",
                 "The printer heats and moves when the print starts." if start else "The file is uploaded, not started."]
        if issues:
            lines.append(f"The file has {len(issues)} command(s) to look at:")
            lines += [f"line {x['line']}: {x['why']}" for x in issues]
        title = f"{'Start a print of' if start else 'Send'} {os.path.basename(path)} on {name}" + (" (it has commands to look at)" if issues else "")
        waits = person_ok(a, word, name, p, title, lines, path, sha)
        if waits is not None:
            if issues:
                waits["issues"] = issues
            return waits
    if start:
        try:
            st = P.status(p)
        except P.PrinterError as e:
            raise _err(e)
        busy = str(st.get("state") or "").lower()
        if any(w in busy for w in ("printing", "paused", "busy")):
            raise ToolError("invalid_state", f"{name} is {busy}: it has a job. Wait, or printer_stop it first (the person's call).")
    try:
        r = P.send(p, path, start, storage)
    except P.PrinterError as e:
        raise _err(e)
    r.update({"printer": name, "bytes": os.path.getsize(path), "sha256": sha})
    if issues:
        r["issues"] = issues
    if not start:
        r["note"] = "Uploaded, not started. Starting the print is the person's call: printer_send again with start: true (the person approves it), or start it on the printer."
    return r


def control(action):
    def run(s, a):
        name, p = get(s, a.get("printer"))
        title = f"{action.capitalize()} the print on {name}" + (" (the job cannot be resumed)" if action == "stop" else "")
        waits = person_ok(a, action, name, p, title, [f"Printer: {name} ({p['kind']}, {p['url']})", title])
        if waits is not None:
            return waits
        try:
            return {"printer": name, **P.control(p, action)}
        except P.PrinterError as e:
            raise _err(e)

    return run


HANDLERS = {
    "printer_add": printer_add,
    "printer_list": printer_list,
    "printer_status": printer_status,
    "printer_send": printer_send,
    "printer_pause": control("pause"),
    "printer_stop": control("stop"),
}
