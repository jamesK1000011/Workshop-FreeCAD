# SPDX-License-Identifier: LGPL-2.1-or-later
# A library pack to hand on: STEP and STL with nothing personal left in
# their headers, a README, a licence, the credits checked against it. No
# FreeCAD needed here. Moved from Agent Link for FreeCAD's packing.py on
# 14 Nov 2026; the zip writer is AddonKit's.

import datetime
import getpass
import os
import re
from addonkit.archive import write_zip  # noqa: F401 — library packs zip through it

# ---- library packs ------------------------------------------------------------------------

LICENSES = {
    "CC-BY-4.0": ("Creative Commons Attribution 4.0 International", "https://creativecommons.org/licenses/by/4.0/"),
    "CC-BY-SA-4.0": ("Creative Commons Attribution-ShareAlike 4.0 International", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "CC0-1.0": ("CC0 1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "MIT": ("MIT License", "https://opensource.org/license/mit"),
}

MIT_TEXT = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def license_text(spdx, holder, title):
    """The LICENSE file. MIT whole; the Creative Commons ones as their
    notice and link, as Creative Commons asks works to be marked."""
    year = datetime.date.today().year
    if spdx == "MIT":
        return MIT_TEXT.format(year=year, holder=holder)
    name, url = LICENSES[spdx]
    if spdx == "CC0-1.0":
        who = holder or "The person who associated a work with this deed"
        return (
            f"{title}\n\n{who} has dedicated this work to the public domain by waiving all of their rights to the work "
            f"worldwide under copyright law, including all related and neighboring rights, to the extent allowed by law.\n\n"
            f"{name}: {url}\nThe full legal code: {url}legalcode\n"
        )
    return f"{title} © {year} {holder}\n\nThis work is licensed under {name} ({spdx}).\nTo view a copy of this license, visit {url}\nThe full legal code: {url}legalcode\n"


def check_credits(spdx, credits):
    """(refusals, warnings) for remixed parts' licences against the pack's."""
    errors, warnings = [], []
    for i, c in enumerate(credits):
        lic = str(c.get("license") or "").upper().replace(" ", "-")
        what = c.get("title") or c.get("url") or f"credits.{i}"
        if not lic:
            warnings.append(f"{what}: no licence given — check its page says you may remix and share it.")
            continue
        if "ND" in lic.split("-") or "NODERIVS" in lic or "NODERIVATIVES" in lic:
            errors.append(f"{what} is {c['license']}: no derivatives, so it cannot be remixed into a pack at all — leave it out, or ask its author.")
        elif "NC" in lic.split("-"):
            errors.append(f"{what} is {c['license']}: non-commercial, which none of CC-BY-4.0, CC-BY-SA-4.0, CC0-1.0 or MIT keeps — leave it out, or ask its author.")
        elif "SA" in lic.split("-") and spdx != "CC-BY-SA-4.0":
            errors.append(f"{what} is {c['license']}: share-alike, so the remix must be CC-BY-SA-4.0.")
        elif "GPL" in lic and spdx not in ("CC-BY-SA-4.0",):
            errors.append(f"{what} is {c['license']}: the remix must stay under the GPL, which this pack does not offer — leave it out.")
        elif lic.startswith("CC-BY") and spdx == "CC0-1.0":
            errors.append(f"{what} is {c['license']}: its author must be credited, which CC0 does not keep — choose CC-BY-4.0 or CC-BY-SA-4.0.")
        elif lic.startswith("CC-BY") and spdx == "MIT":
            warnings.append(f"{what} is {c['license']}: its part stays CC BY; the credit in the README keeps that.")
    return errors, warnings


def private_strings():
    """What must not leave the computer in a file's header: the home folder
    and the user's name."""
    out = []
    home = os.path.expanduser("~")
    if home and home not in ("/", "~"):
        out.append(home)
    try:
        u = getpass.getuser()
        if u and len(u) >= 3:
            out.append(u)
    except Exception:  # no user name to be had: nothing to strip
        pass
    return out


def clean_step(text, name, author=""):
    """A STEP file's text with its header cleaned: FILE_NAME gives the file's
    own name, the author given (or none), no organisation; the home folder
    and user name gone from the header; the home folder gone from the
    data."""
    m = re.search(r"HEADER;(.*?)ENDSEC;", text, re.S)
    if not m:
        return text
    hdr = m.group(1)

    def q(s):
        return "'" + str(s).replace("'", "''") + "'"

    stamp = re.search(r"FILE_NAME\s*\(\s*'(?:[^']|'')*'\s*,\s*'([^']*)'", hdr)
    when = stamp.group(1) if stamp else datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    new_fn = f"FILE_NAME({q(name)},{q(when)},({q(author)}),({q('')}),{q('')},{q('FreeCAD')},{q('')});"
    hdr = re.sub(r"FILE_NAME\s*\(.*?\)\s*;", lambda _: new_fn, hdr, count=1, flags=re.S)
    for s in private_strings():
        hdr = hdr.replace(s, "")
    body = text[m.end():]
    home = os.path.expanduser("~")
    if home and home not in ("/", "~"):
        body = body.replace(home, "")
    return text[: m.start()] + "HEADER;" + hdr + "ENDSEC;" + body


def clean_stl(data, name):
    """An STL's header (binary) or solid name (ASCII) set to the part's name."""
    if data[:5].lower() == b"solid" and b"facet" in data[:400]:
        text = data.decode("ascii", "replace").splitlines()
        if text:
            text[0] = f"solid {name}"
            for i in range(len(text) - 1, -1, -1):
                if text[i].strip().startswith("endsolid"):
                    text[i] = f"endsolid {name}"
                    break
        return ("\n".join(text) + "\n").encode("ascii", "replace")
    head = f"STL {name}".encode("ascii", "replace")[:80].ljust(80, b" ")
    return head + data[80:]


def readme(title, description, author, spdx, parts, settings, credits, notes=()):
    lines = [f"# {title}", ""]
    if description:
        lines += [description, ""]
    lines += [f"By {author}." if author else "", f"Licence: {spdx} — see LICENSE.", "", "## Parts", "", "| File | Size (mm) | Volume (cm³) | Material | Mass (g) |", "|---|---|---|---|---|"]
    for p in parts:
        lines.append(f"| {' / '.join(p['files'])} | {' x '.join(f'{v:g}' for v in p['size'])} | {p['volume'] / 1000:.1f} | {p.get('material') or '—'} | {p.get('mass') if p.get('mass') is not None else '—'} |")
    lines += ["", "## Printing", ""]
    if settings:
        for k, v in settings.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No print setup recorded: PLA, 0.2 mm layers, 3 walls and 15% infill suit most parts like these.")
    for n in notes:
        lines.append(f"- {n}")
    if credits:
        lines += ["", "## Credits", ""]
        for c in credits:
            bits = [c.get("title") or "A part"]
            if c.get("author"):
                bits.append(f"by {c['author']}")
            if c.get("url"):
                bits.append(f"({c['url']})")
            if c.get("license"):
                bits.append(f"— {c['license']}")
            if c.get("changes"):
                bits.append(f"; changed: {c['changes']}")
            lines.append("- " + " ".join(bits))
    lines += ["", "Made with FreeCAD."]
    return "\n".join(x for x in lines if x is not None) + "\n"
