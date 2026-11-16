# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' archive.py, the source copy (Workshop Electronics carries its own); it was AddonKit's addonkit.archive, 14 Nov 2026.
"""Zips to hand on (an order package, a library pack): deflated, with no
folder of the computer's in them and ordinary file modes. Plain Python."""

import datetime
import os
import zipfile


def write_zip(path, entries):
    """A zip of [(name in the zip, source path, bytes or text)], deflated,
    with no folder of the computer's in it. Returns path."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in entries:
            info = zipfile.ZipInfo(name.replace("\\", "/").lstrip("/"), date_time=datetime.datetime.now().timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            if isinstance(src, (bytes, bytearray)):
                z.writestr(info, bytes(src))
            elif isinstance(src, str) and os.path.isfile(src):
                with open(src, "rb") as f:
                    z.writestr(info, f.read())
            else:
                z.writestr(info, str(src).encode("utf-8"))
    return path
