# SPDX-License-Identifier: LGPL-2.1-or-later
# Printers on the network: kept by name (the key or password in a file
# beside the session's, never given back), their state, a G-code file sent
# to one, and a job paused or stopped. Starting, pausing and stopping a
# print are the person's to decide: each needs a confirm string that says
# so, word for word.

import os

from agentlink.protocol import ToolError

from . import printers as P
from . import tooldefs

GROUP = "printer"
INFO = "Printers on the network (OctoPrint, Moonraker/Klipper, PrusaLink): add, list, status, send G-code; start, pause and stop only on the person's word."



def _err(e):
    return ToolError(e.code, e.message)


def tools(session):
    s = session

    def get(name):
        ps = P.load(s.out_dir)
        if not ps:
            raise ToolError("not_found", "No printer kept yet: printer_add { name, kind, url, key } first.")
        if name is None and len(ps) == 1:
            name = next(iter(ps))
        if name not in ps:
            raise ToolError("not_found", f"printer {name!r}: not kept — the printers: {', '.join(ps)}." if name else f"printer: say which — {', '.join(ps)}.")
        return name, ps[name]

    def need(a, word, name):
        want = f"{word} {name}"
        if (a.get("confirm") or "").strip() != want:
            raise ToolError("invalid_input", f"confirm: \"{want}\", word for word — ask the person first; it is their call, not yours.")

    def printer_add(a):
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
        out = {"added": P.public(name, p), "replaced": replaced, "kept": os.path.basename(P.path(s.out_dir))}
        if a.get("check", True):
            try:
                st = P.status(p)
                out["reached"] = True
                out["state"] = st.get("state")
            except P.PrinterError as e:
                out["reached"] = False
                out["why"] = e.message
        return out

    def printer_list(a):
        ps = P.load(s.out_dir)
        if a.get("remove"):
            if a["remove"] not in ps:
                raise ToolError("not_found", f"{a['remove']!r}: not kept — the printers: {', '.join(ps) or 'none'}.")
            ps.pop(a["remove"])
            P.save(s.out_dir, ps)
        return {"printers": [P.public(n, p) for n, p in ps.items()], **({"removed": a["remove"]} if a.get("remove") else {})}

    def printer_status(a):
        name, p = get(a.get("printer"))
        try:
            return {"printer": name, "kind": p["kind"], **P.status(p)}
        except P.PrinterError as e:
            raise _err(e)

    def printer_send(a):
        name, p = get(a.get("printer"))
        f = a.get("file")
        if not f:
            raise ToolError("invalid_input", "file: the G-code to send — slice or slice_with writes it.")
        path = f if os.path.isabs(f) else os.path.join(s.out_dir, f)
        if not os.path.isfile(path):
            raise ToolError("not_found", f"{path}: no such file — slice it first.")
        if not path.lower().endswith(P.GCODE):
            raise ToolError("invalid_input", f"file: G-code only ({', '.join(P.GCODE)}).")
        start = bool(a.get("start"))
        if start:
            need(a, "start", name)
            try:
                st = P.status(p)
            except P.PrinterError as e:
                raise _err(e)
            busy = str(st.get("state") or "").lower()
            if any(w in busy for w in ("printing", "paused", "busy")):
                raise ToolError("invalid_state", f"{name} is {busy}: it has a job — wait, or printer_stop it first (the person's call).")
        try:
            r = P.send(p, path, start, a.get("storage"))
        except P.PrinterError as e:
            raise _err(e)
        r.update({"printer": name, "bytes": os.path.getsize(path)})
        if not start:
            r["note"] = "Uploaded, not started: starting the print is the person's call — printer_send again with start: true and their confirm, or start it on the printer."
        return r

    def control(action):
        def run(a):
            name, p = get(a.get("printer"))
            need(a, action, name)
            try:
                return {"printer": name, **P.control(p, action)}
            except P.PrinterError as e:
                raise _err(e)

        return run

    return tooldefs.build("printer", {"printer_add": printer_add, "printer_list": printer_list, "printer_status": printer_status, "printer_send": printer_send,
                                      "printer_pause": control("pause"), "printer_stop": control("stop")})
