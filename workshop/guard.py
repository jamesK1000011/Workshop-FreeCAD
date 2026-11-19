# SPDX-License-Identifier: LGPL-2.1-or-later
# Checks that every part of Workshop shares (red team 3, 19 Nov 2026):
# text from a file or a device made safe to give to the agent, and the
# check of a file that a tool reads. With Agent Link, the read check is its
# paths.in_file (lent by each family layer as IN_FILE). Without it, the
# fallback here refuses the same credential and shell-settings folders.
# Plain Python: no FreeCAD, no Agent Link import.

import os
import unicodedata

TEXT_CAP = 300
# The folders Agent Link's paths.SECRET_PARTS names: credentials and shell
# settings. Compared without case (macOS disks ignore case).
SECRET_PARTS = {".ssh", ".aws", ".gnupg", ".kube", ".docker", ".config", ".netrc", ".git", ".password-store", "keychains",
                ".zshrc", ".bashrc", ".profile", ".bash_profile", ".zprofile", ".env"}


def clean_text(text, cap=TEXT_CAP):
    """One line of text from a file or a device, safe to give to the agent:
    no format characters (Unicode Cf: zero-width, direction marks, tag
    characters), no control characters, capped at cap characters."""
    if text is None:
        return None
    out = []
    for c in str(text):
        cat = unicodedata.category(c)
        if cat == "Cf" or 0xE0000 <= ord(c) <= 0xE007F:
            continue
        out.append(" " if cat == "Cc" else c)
    t = " ".join("".join(out).split())
    return t[:cap] + ("…" if len(t) > cap else "")


def clean_obj(obj, cap=2000):
    """clean_text on every string in a JSON-like answer (dicts, lists)."""
    if isinstance(obj, str):
        return clean_text(obj, cap)
    if isinstance(obj, dict):
        return {k: clean_obj(v, cap) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_obj(v, cap) for v in obj]
    return obj


def secret_part(path):
    """The credential or settings folder in path (after links), or None."""
    real = os.path.realpath(os.path.expanduser(str(path)))
    for x in real.replace("\\", "/").split("/"):
        if x and x.casefold() in SECRET_PARTS:
            return x
    return None


def read_ok(session, tool, path, key, in_file=None, error=ValueError):
    """The path a tool reads, checked: Agent Link's paths.in_file when it is
    lent (in_file), else the fallback here. Raises error(code, message), or
    the hub's own refusal."""
    if in_file is not None:
        return in_file(session, tool, path, key)
    bad = secret_part(path)
    if bad:
        raise error("invalid_input", f"{key}: {path} is in {bad}. Credentials and shell settings are off limits.")
    return path
