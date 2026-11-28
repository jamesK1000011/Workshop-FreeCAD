# SPDX-License-Identifier: LGPL-2.1-or-later
# G-code checks before a file goes to a printer (red team 3, R3-4): the
# pause command only from a short list, and a read of the whole file for
# commands that change the printer itself and for heat over the caps.
# Plain Python.

import hashlib
import re

from workshop.guard import clean_text

# The pause commands a slice may write. One command, no new lines.
PAUSES = ("M601", "M600", "M0", "M1", "PAUSE")
# Heat caps, °C: no hobby nozzle or bed goes over these.
NOZZLE_CAP = 300
BED_CAP = 120
# Commands that change the printer itself, turn off what protects it, or
# cut the power. The OrcaSlicer Agent Link's list, and more (red team 3).
RISKY = {"M997": "firmware update", "M500": "saves settings to the printer", "M502": "factory reset", "M501": "reloads saved settings",
         "M211": "software endstops", "M302": "cold extrusion", "M303": "PID autotune", "M112": "emergency stop", "M552": "network", "M587": "Wi-Fi",
         "M906": "motor current", "M92": "steps per mm", "M851": "probe offset", "M80": "power on", "M81": "power off",
         "M999": "restart after a halt", "M98": "runs a macro file", "M550": "printer name", "M540": "network address",
         "FIRMWARE_RESTART": "firmware restart", "RESTART": "host restart", "SAVE_CONFIG": "saves the printer configuration"}
MOTORS_OFF = ("M18", "M84")
MOVE = re.compile(r"^G[0-3]\b")
CODE = re.compile(r"^([GMT]\d+|[A-Z_]+)\b")
MAX_ISSUES = 20


class PauseError(ValueError):
    pass


def pause_command(cmd, default):
    """The pause command to write: default when cmd is empty, else cmd
    when it is one of PAUSES (or the slicer's own default). Raises
    PauseError."""
    if cmd in (None, ""):
        return default
    c = str(cmd)
    if "\n" in c or "\r" in c:
        raise PauseError("pauseCommand: one command, no new lines.")
    c = c.strip()
    if c.upper() in PAUSES or c == default:
        return c.upper() if c.upper() in PAUSES else c
    raise PauseError(f"pauseCommand: one of {', '.join(PAUSES)}. Got {clean_text(c, 40)!r}.")


def _num(word, letter):
    m = re.search(r"\b" + letter + r"(-?\d+(?:\.\d+)?)", word)
    return float(m.group(1)) if m else None


def line_issue(code_line, nozzle_cap=NOZZLE_CAP, bed_cap=BED_CAP):
    """The issue in one G-code line (comment removed, upper case) as a record
    ({code, does} or {code, heater, value, cap}), or None."""
    m = CODE.match(code_line)
    if not m:
        return None
    c = m.group(1)
    if c in RISKY:
        return {"code": c, "does": RISKY[c]}
    if c in ("M104", "M109"):
        t = max(x for x in (_num(code_line, "S"), _num(code_line, "R"), 0.0) if x is not None)
        if t > nozzle_cap:
            return {"code": c, "heater": "nozzle", "value": t, "cap": nozzle_cap}
    if c in ("M140", "M190"):
        t = max(x for x in (_num(code_line, "S"), _num(code_line, "R"), 0.0) if x is not None)
        if t > bed_cap:
            return {"code": c, "heater": "bed", "value": t, "cap": bed_cap}
    if c == "SET_HEATER_TEMPERATURE":
        h = re.search(r"HEATER=(\S+)", code_line)
        t = _num(code_line, "TARGET=")
        cap = bed_cap if h and "BED" in h.group(1) else nozzle_cap
        if t is not None and t > cap:
            return {"code": c, "heater": h.group(1).lower() if h else "heater", "value": t, "cap": cap}
    return None


def issue_says(x):
    """One issue in words, for the approval the person reads."""
    if x.get("reason") == "binaryGcode":
        return "binary G-code (.bgcode): its commands cannot be checked here"
    if x.get("reason") == "motorsOffWhileMoving":
        return "motors off (M18/M84) while the print still moves"
    if x.get("heater"):
        return f"{x['code']}: {x['heater']} {x['value']:g} °C, over the cap of {x['cap']} °C"
    return f"{x.get('code')}: {x.get('does')}"


def scan(path, nozzle_cap=NOZZLE_CAP, bed_cap=BED_CAP):
    """Read a G-code file once: (sha256, issues). issues: [{ line, text,
    code, does | heater, value, cap | reason }], at most MAX_ISSUES; the text
    is cleaned and capped. A binary G-code file (.bgcode) cannot be read
    here: one issue says so (reason binaryGcode)."""
    h = hashlib.sha256()
    issues = []
    off_at = None
    binary = str(path).lower().endswith(".bgcode")
    with open(path, "rb") as f:
        for n, raw in enumerate(f, 1):
            h.update(raw)
            if binary or len(issues) >= MAX_ISSUES:
                continue
            text = raw.decode("utf-8", "replace")
            code = text.split(";", 1)[0].strip().upper()
            if not code:
                continue
            why = line_issue(code, nozzle_cap, bed_cap)
            if why is None and code.split()[0] in MOTORS_OFF:
                off_at = (n, text)
            elif why is None and off_at and MOVE.match(code):
                why = {"code": "M18/M84", "reason": "motorsOffWhileMoving"}
                n, text = off_at
                off_at = None
            if why:
                issues.append({"line": n, **why, "text": clean_text(text, 120)})
    if binary:
        issues.append({"line": 0, "reason": "binaryGcode", "text": ""})
    return "sha256:" + h.hexdigest(), issues
