# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's own copy of Agent Link's keep.py helpers: where things are kept
# (~/AgentLink, or $AGENTLINK_HOME), a document's name as a folder, a time
# stamp, JSON read and written whole. The same paths and formats, so files
# written before the split are read as they are.

import json
import os
import re
import shutil
import time

MB = 1024 * 1024


def home():
    return os.environ.get("AGENTLINK_HOME") or os.path.expanduser("~/AgentLink")


def path(*parts):
    return os.path.join(home(), *parts)


def safe(name):
    """A document's name as a folder: letters, digits, - _ . only."""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "doc")).strip("._") or "doc"
    return s[:80]


def stamp(t=None):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t if t is not None else time.time()))


def _load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(p, value):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1)
    os.replace(tmp, p)


def _size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def free_bytes(where=None):
    p = where or home()
    while p and not os.path.isdir(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    try:
        return shutil.disk_usage(p or "/").free
    except OSError:
        return 0
