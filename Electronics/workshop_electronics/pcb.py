# SPDX-License-Identifier: LGPL-2.1-or-later
# A PCB order: Gerbers, drill, BOM and placement files sorted, the board's
# size read from its outline Gerber, an order sheet for the board house.
# The board houses are data (data/pcb-vendors.json). No FreeCAD needed.
# Moved from Agent Link for FreeCAD's packing.py on 14 Nov 2026.

import datetime
import os
import re

from workshop_electronics import datafiles as data
from workshop_electronics.archive import write_zip  # noqa: F401 — the order zips

HERE = os.path.dirname(os.path.abspath(__file__))
ACCEPTS = ">=1.0,<2"


def vendors():
    """The board houses: {id: {name, upload, assembly, quantity}} (the
    person's own in ~/.config/workshop_electronics/pcb-vendors.json)."""
    return data.load(os.path.join(HERE, "data"), "pcb-vendors", accepts=ACCEPTS, package="workshop_electronics")["entries"]


GERBER_EXT = {".gbr", ".gtl", ".gbl", ".gto", ".gbo", ".gts", ".gbs", ".gtp", ".gbp", ".gko", ".gm1", ".gml", ".gbrjob", ".gm", ".gg1"}
GERBER_INNER = re.compile(r"\.g\d+$|\.gl\d+$", re.I)
DRILL_EXT = {".drl", ".xln", ".exc", ".drd"}


def classify(paths):
    """{gerbers, drill, bom, cpl, other}: each a list of the paths given."""
    out = {"gerbers": [], "drill": [], "bom": [], "cpl": [], "other": []}
    for p in paths:
        base = os.path.basename(p).lower()
        ext = os.path.splitext(base)[1]
        if ext in GERBER_EXT or GERBER_INNER.search(base):
            out["gerbers"].append(p)
        elif ext in DRILL_EXT or (ext == ".txt" and "drill" in base):
            out["drill"].append(p)
        elif ext in (".csv", ".xlsx", ".xls", ".txt") and re.search(r"cpl|pos|position|centroid|placement|pnp|pick", base):
            out["cpl"].append(p)
        elif ext in (".csv", ".xlsx", ".xls", ".txt") and "bom" in base:
            out["bom"].append(p)
        else:
            out["other"].append(p)
    return out


def is_outline(path):
    b = os.path.basename(path).lower()
    return "edge_cuts" in b or "edge.cuts" in b or b.endswith((".gko", ".gm1", ".gml", ".gm"))


def is_copper(path):
    b = os.path.basename(path).lower()
    return bool(re.search(r"[fb]_cu|in\d+_cu|\.gtl$|\.gbl$|\.g\d+$|\.gl\d+$", b))


def gerber_box(text):
    """The extent of a Gerber file's coordinates, mm: [xmin, ymin, xmax,
    ymax], or None. Reads %FS…% and %MO…%; draws and moves alike."""
    fs = re.search(r"%FS[LT]?A?X(\d)(\d)Y(\d)(\d)\*%", text)
    if not fs:
        return None
    xd, yd = int(fs.group(2)), int(fs.group(4))
    inch = "%MOIN*%" in text
    k = 25.4 if inch else 1.0
    xs, ys = [], []
    x = y = 0
    for m in re.finditer(r"(?:X(-?\d+))?(?:Y(-?\d+))?(?:I-?\d+)?(?:J-?\d+)?D0?[123]\*", text):
        if m.group(1) is None and m.group(2) is None:
            continue
        if m.group(1) is not None:
            x = int(m.group(1)) / 10 ** xd * k
        if m.group(2) is not None:
            y = int(m.group(2)) / 10 ** yd * k
        xs.append(x)
        ys.append(y)
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def order_sheet(vendor, board, files, quantity=None, drc=None, finish="HASL (lead-free)", colour="green"):
    """The order sheet, Markdown: the board's figures, the files, what to
    upload where."""
    v = vendors()[vendor]
    q = quantity or v["quantity"]
    if vendor == "oshpark" and q % 3:
        q += 3 - q % 3
    w, d = board.get("size") or (None, None)
    rows = [
        f"# PCB order — {board.get('name') or 'board'}",
        "",
        f"For {v['name']}. Written {datetime.date.today().isoformat()}. Check every figure against the board before paying.",
        "",
        "| | |",
        "|---|---|",
        f"| Size | {f'{w:.2f} x {d:.2f} mm' if w else 'not known — read it from the outline'} |",
        f"| Copper layers | {board.get('layers') or 'not known'} |",
        f"| Thickness | {board.get('thickness', 1.6)} mm |",
        f"| Quantity | {q} |",
        f"| Surface finish | {finish} |",
        f"| Solder mask | {colour} |",
        "",
        "## Files",
        "",
    ]
    for kind in ("gerbers", "drill", "bom", "cpl", "other"):
        if files.get(kind):
            rows.append(f"- {kind}: " + ", ".join(os.path.basename(p) for p in files[kind]))
    rows += ["", "## Design rule check", ""]
    if drc is None:
        rows.append("Not run: kicad-cli was not found on this computer. Run Inspect › Design Rules Checker in KiCad before ordering.")
    else:
        rows.append(drc)
    rows += ["", "## Ordering", "", f"- {v['upload']}", f"- {v['assembly']}", "- Placing the order and paying are yours to do."]
    return "\n".join(rows) + "\n"
