# SPDX-License-Identifier: LGPL-2.1-or-later
# Printers on the network, by their own published HTTP APIs: OctoPrint
# (REST API, X-Api-Key), Moonraker (Klipper's API server) and PrusaLink
# (its v1 API, an API key or HTTP digest). What is known of each printer is
# kept in ~/AgentLink/printers.json (or $AGENTLINK_HOME), readable by its
# owner only, never in the session's folder that people share (red team 3,
# R3-8); keys and passwords are never given back. A redirect to another
# host is refused, so the key never goes there (R3-9). Python's standard library
# only. Bambu Lab printers are not here: they take jobs over their own LAN
# mode protocol or from Bambu Studio.

import ipaddress
import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
import uuid

from workshop.guard import clean_text

FILE = "printers.json"
OLD_FILE = ".agentlink-printers.json"  # in the session's folder, before 19 Nov 2026
KINDS = ("octoprint", "moonraker", "prusalink")
ALIASES = {"klipper": "moonraker", "mainsail": "moonraker", "fluidd": "moonraker", "prusa": "prusalink"}
BAMBU = ("bambu", "bambulab", "bambu-lab", "bambu lab")
GCODE = (".gcode", ".gco", ".g", ".bgcode")
SECRET = ("key", "password")
# Where a file may go on each kind of printer (R3-9): the first is the default.
STORAGE = {"octoprint": ("local", "sdcard"), "moonraker": ("gcodes",), "prusalink": ("usb", "local")}


class PrinterError(Exception):
    """code: unavailable (cannot reach it), failed (it said no), invalid_state."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# ---- the config file ----------------------------------------------------------------------

def home():
    return os.environ.get("AGENTLINK_HOME") or os.path.expanduser("~/AgentLink")


def path(out_dir=None):
    """The printers file: ~/AgentLink/printers.json. out_dir is not used
    (the file was there before 19 Nov 2026; load() moves it once)."""
    return os.path.join(home(), FILE)


def shown_path(p=None):
    """The file as a person reads it: ~/… under the home folder."""
    p = p or path()
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if h and h != "/" and p.startswith(h.rstrip("/") + "/") else p


def _read(p):
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as f:
        try:
            got = json.load(f).get("printers", {})
        except (ValueError, AttributeError):
            return {}
    return got if isinstance(got, dict) else {}


def _migrate(out_dir):
    """An old printers file in the session's folder, moved once into the
    new file (the new file's entries win) and removed."""
    if not out_dir:
        return
    old = os.path.join(out_dir, OLD_FILE)
    if not os.path.isfile(old) or os.path.realpath(old) == os.path.realpath(path()):
        return
    got = _read(old)
    now = _read(path())
    save(out_dir, {**got, **now})
    try:
        os.remove(old)
    except OSError:
        pass


def load(out_dir=None):
    _migrate(out_dir)
    return _read(path())


def save(out_dir, printers):
    d = home()
    os.makedirs(d, mode=0o700, exist_ok=True)
    p = path()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"printers": printers}, f, indent=1)
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def public(name, p):
    """A printer as it may be shown: no key, no password."""
    out = {"name": name, **{k: v for k, v in p.items() if k not in SECRET}}
    out["auth"] = "api key" if p.get("key") else ("digest" if p.get("password") else "none")
    return out


def kind_of(kind):
    k = str(kind or "").strip().lower()
    if k in BAMBU:
        raise PrinterError("unavailable", "Bambu Lab printers take jobs over their own LAN-mode protocol (the printer's access code, MQTT and FTPS) or from Bambu Studio, not by an open HTTP API: slice with slice_with { slicer: \"bambustudio\" } and send the file from Bambu Studio, or Bambu Handy.")
    k = ALIASES.get(k, k)
    if k not in KINDS:
        raise PrinterError("invalid_input", f"kind: one of {', '.join(KINDS)} (klipper is moonraker).")
    return k


def normal_url(url):
    u = str(url or "").strip().rstrip("/")
    if "://" not in u:
        u = "http://" + u
    p = urllib.parse.urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise PrinterError("invalid_input", "url: the printer's address, http://host[:port] — as the browser opens it.")
    return u


def is_local(url):
    """True when the printer's host is on this network: a private, link-local
    or loopback address, a .local, .lan or .home.arpa name, or a name with no
    dot (the LAN's own names)."""
    host = (urllib.parse.urlparse(url).hostname or "").lower().rstrip(".")
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_link_local or ip.is_loopback
    except ValueError:
        return "." not in host or host.endswith((".local", ".lan", ".home.arpa"))


def storage_of(kind, storage):
    """The storage on the printer: from STORAGE[kind] only (R3-9)."""
    ok = STORAGE[kind]
    if storage in (None, ""):
        return ok[0]
    if storage not in ok:
        raise PrinterError("invalid_input", f"storage: for {kind}, one of {', '.join(ok)}.")
    return storage


# ---- HTTP ---------------------------------------------------------------------------------

class _SameHost(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only on the printer's own host: the key is never
    sent to another host (R3-9)."""

    def __init__(self, base):
        super().__init__()
        self.host = (urllib.parse.urlparse(base).hostname or "").lower()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        to = (urllib.parse.urlparse(urllib.parse.urljoin(req.full_url, newurl)).hostname or "").lower()
        if to != self.host:
            raise PrinterError("failed", f"The printer sent a redirect to another host ({to or 'unknown'}). It was not followed, and the key was not sent there.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, p, timeout=10):
        self.p = p
        self.base = p["url"]
        self.timeout = timeout
        handlers = [_SameHost(self.base)]
        if p.get("password"):
            mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, self.base, p.get("user") or "maker", p["password"])
            handlers.append(urllib.request.HTTPDigestAuthHandler(mgr))
        self.opener = urllib.request.build_opener(*handlers)

    def request(self, method, route, body=None, headers=None, raw=False):
        h = dict(headers or {})
        if self.p.get("key"):
            h["X-Api-Key"] = self.p["key"]
        data = body
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + route, data=data, headers=h, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as r:
                text = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            detail = clean_text(e.read()[:200].decode("utf-8", "replace"), 200)
            if e.code in (401, 403):
                raise PrinterError("failed", f"{self.base} refused the key or password ({e.code}): printer_add the printer again with the right one.")
            raise PrinterError("failed", f"{method} {route}: the printer said {e.code} {e.reason}{(' — ' + detail) if detail else ''}.")
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise PrinterError("unavailable", f"{self.base}: can't reach it ({reason}) — is it on and on this network, and the address right?")
        if raw:
            return status, text
        if not text:
            return {}
        try:
            return json.loads(text)
        except ValueError:
            return {"text": clean_text(text[:200].decode("utf-8", "replace"), 200)}


def _multipart(fields, file_field, filename, data):
    b = "----agentlink" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
    parts.append(data)
    parts.append(f"\r\n--{b}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={b}"


def _t(v):
    return None if v is None else round(float(v), 1)


# ---- per kind -----------------------------------------------------------------------------

def status(p):
    """The printer's state, its text cleaned for the agent (R3-11)."""
    st = _status(p)
    for k in ("state",):
        st[k] = clean_text(st.get(k), 60)
    job = st.get("job") or {}
    if job.get("file") is not None:
        job["file"] = clean_text(job["file"], 120)
    return st


def _status(p):
    c = Client(p)
    k = p["kind"]
    if k == "octoprint":
        job = c.request("GET", "/api/job")
        try:
            pr = c.request("GET", "/api/printer")
        except PrinterError as e:
            if "409" not in e.message:
                raise
            pr = {}
        temps = pr.get("temperature") or {}
        tool = temps.get("tool0") or {}
        bed = temps.get("bed") or {}
        prog = job.get("progress") or {}
        return {
            "state": job.get("state") or (pr.get("state") or {}).get("text"),
            "nozzle": {"now": _t(tool.get("actual")), "target": _t(tool.get("target"))},
            "bed": {"now": _t(bed.get("actual")), "target": _t(bed.get("target"))},
            "job": {"file": ((job.get("job") or {}).get("file") or {}).get("name"), "progress": None if prog.get("completion") is None else round(prog["completion"], 1), "left": prog.get("printTimeLeft")},
        }
    if k == "moonraker":
        q = c.request("GET", "/printer/objects/query?print_stats&extruder&heater_bed&virtual_sdcard")
        s = (q.get("result") or {}).get("status") or {}
        ps, ex, hb, sd = s.get("print_stats") or {}, s.get("extruder") or {}, s.get("heater_bed") or {}, s.get("virtual_sdcard") or {}
        prog = sd.get("progress")
        return {
            "state": ps.get("state"),
            "nozzle": {"now": _t(ex.get("temperature")), "target": _t(ex.get("target"))},
            "bed": {"now": _t(hb.get("temperature")), "target": _t(hb.get("target"))},
            "job": {"file": ps.get("filename") or None, "progress": None if prog is None else round(100 * prog, 1), "printed": ps.get("print_duration")},
        }
    s = c.request("GET", "/api/v1/status")
    pr, job = s.get("printer") or {}, s.get("job") or {}
    return {
        "state": (pr.get("state") or "").lower() or None,
        "nozzle": {"now": _t(pr.get("temp_nozzle")), "target": _t(pr.get("target_nozzle"))},
        "bed": {"now": _t(pr.get("temp_bed")), "target": _t(pr.get("target_bed"))},
        "job": {"id": job.get("id"), "progress": job.get("progress"), "left": job.get("time_remaining")},
    }


def send(p, file_path, start=False, storage=None):
    storage = storage_of(p["kind"], storage)
    c = Client(p, timeout=120)
    name = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        data = f.read()
    k = p["kind"]
    if k == "octoprint":
        fields = {"select": "true" if start else "false", "print": "true" if start else "false"}
        body, ctype = _multipart(fields, "file", name, data)
        r = c.request("POST", "/api/files/" + storage, body, {"Content-Type": ctype})
        return {"uploaded": name, "where": clean_text((r.get("files") or {}).get(storage, {}).get("path") or name, 200), "started": bool(start and r.get("done", True))}
    if k == "moonraker":
        fields = {"root": storage}
        if start:
            fields["print"] = "true"
        body, ctype = _multipart(fields, "file", name, data)
        r = c.request("POST", "/server/files/upload", body, {"Content-Type": ctype})
        return {"uploaded": name, "where": clean_text((r.get("item") or {}).get("path") or name, 200), "started": bool(r.get("print_started", start))}
    route = f"/api/v1/files/{storage}/{urllib.parse.quote(name, safe='')}"
    headers = {"Content-Type": "text/x.gcode", "Overwrite": "?1", "Print-After-Upload": "?1" if start else "?0"}
    c.request("PUT", route, data, headers, raw=True)
    return {"uploaded": name, "where": f"{storage}/{name}", "started": bool(start)}


def control(p, action):
    """action: pause or stop (the job's own, as the printer's screen does)."""
    c = Client(p)
    k = p["kind"]
    if k == "octoprint":
        body = {"command": "pause", "action": "pause"} if action == "pause" else {"command": "cancel"}
        c.request("POST", "/api/job", body, raw=True)
        return {"done": action}
    if k == "moonraker":
        c.request("POST", "/printer/print/pause" if action == "pause" else "/printer/print/cancel", raw=True)
        return {"done": action}
    s = c.request("GET", "/api/v1/status")
    jid = (s.get("job") or {}).get("id")
    if jid is None:
        raise PrinterError("invalid_state", "The printer has no job running: nothing to pause or stop.")
    if action == "pause":
        c.request("PUT", f"/api/v1/job/{jid}/pause", raw=True)
    else:
        c.request("DELETE", f"/api/v1/job/{jid}", raw=True)
    return {"done": action, "job": jid}
