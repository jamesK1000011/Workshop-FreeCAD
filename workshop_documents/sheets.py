# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's sheets.py, trimmed to what Documents uses; 14 Nov 2026.
# A drawing sheet of lines and text, written as SVG, PDF and DXF. Nothing
# here needs FreeCAD: the views come in as 2D polylines, in millimetres on
# the paper, origin top left, y down (as SVG has it); PDF and DXF turn y up.

import math
import zlib

PAPER = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "A4P": (210.0, 297.0)}
# Line weights, mm, by kind (ISO 128: thick 0.5, thin 0.25).
WEIGHT = {"visible": 0.5, "hidden": 0.25, "thin": 0.25, "dim": 0.18, "frame": 0.7, "cut": 0.7, "center": 0.18}
DASH = {"hidden": (3.0, 1.5), "trail": (6.0, 1.5, 1.0, 1.5), "center": (8.0, 1.5, 1.5, 1.5)}
SCALES = [10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01]


def scale_text(s):
    if s >= 1:
        return f"{s:g}:1"
    return f"1:{1 / s:g}"


def best_scale(fit):
    """The largest standard scale not over `fit`."""
    for s in SCALES:
        if s <= fit + 1e-9:
            return s
    return None


class Sheet:
    def __init__(self, width, height, title=""):
        self.w = float(width)
        self.h = float(height)
        self.title = title
        self.lines = []  # (kind, [(x, y) …], closed, filled)
        self.texts = []  # (x, y, size, text, anchor)

    def line(self, pts, kind="visible", closed=False, filled=False):
        if len(pts) >= 2:
            self.lines.append((kind, [(float(x), float(y)) for (x, y) in pts], closed, filled))

    def text(self, x, y, size, text, anchor="start"):
        self.texts.append((float(x), float(y), float(size), str(text), anchor))

    def frame(self, margin=10.0):
        m = margin
        self.line([(m, m), (self.w - m, m), (self.w - m, self.h - m), (m, self.h - m)], "frame", closed=True)

    def circle(self, cx, cy, r, kind="thin", n=36):
        self.line([(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)], kind, closed=True)

    def place(self, lines, box, centre, scale, kind=None):
        """Lines of a view (its own mm, y up) onto the paper: the view's box
        centred on `centre`, at `scale`."""
        bx, by = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        cx, cy = centre
        for k, pts in lines:
            self.line([(cx + (x - bx) * scale, cy - (y - by) * scale) for (x, y) in pts], kind or k)

    def arrow(self, tip, toward, size=2.5):
        """A filled arrowhead at tip, pointing from `toward` to tip."""
        dx, dy = tip[0] - toward[0], tip[1] - toward[1]
        n = math.hypot(dx, dy) or 1.0
        ux, uy = dx / n, dy / n
        bx, by = tip[0] - ux * size, tip[1] - uy * size
        hw = size * 0.3
        self.line([tip, (bx - uy * hw, by + ux * hw), (bx + uy * hw, by - ux * hw)], "dim", closed=True, filled=True)

    def dimension(self, a, b, offset, label, size=3.0):
        """A linear dimension between points a and b, its line `offset` to
        the side (positive: to the left going a to b), the value over it."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n < 1e-6:
            return
        ux, uy = dx / n, dy / n
        nx, ny = -uy, ux  # left normal, in y-down coordinates it is to the right on screen
        sgn = 1 if offset >= 0 else -1
        pa = (a[0] + nx * offset, a[1] + ny * offset)
        pb = (b[0] + nx * offset, b[1] + ny * offset)
        ext = 1.5 * sgn
        self.line([(a[0] + nx * sgn * 1.0, a[1] + ny * sgn * 1.0), (pa[0] + nx * ext, pa[1] + ny * ext)], "dim")
        self.line([(b[0] + nx * sgn * 1.0, b[1] + ny * sgn * 1.0), (pb[0] + nx * ext, pb[1] + ny * ext)], "dim")
        self.line([pa, pb], "dim")
        self.arrow(pa, pb)
        self.arrow(pb, pa)
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
        if abs(ux) > 0.5:  # along the page: the value over the line
            self.texts.append((mx, my - 1.0, size, label, "middle"))
        else:  # up the page: the value to its left, read from the right
            self.texts.append((mx - 1.0, my, size, label, "vertical"))

    # ---- writers -------------------------------------------------------------------------

    def svg(self):
        out = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w:g}mm" height="{self.h:g}mm" viewBox="0 0 {self.w:g} {self.h:g}">',
            f"<title>{_esc(self.title)}</title>",
            '<rect width="100%" height="100%" fill="white"/>',
            '<g fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round">',
        ]
        for kind, pts, closed, filled in self.lines:
            d = "M" + " L".join(f"{x:.3f},{y:.3f}" for (x, y) in pts) + (" Z" if closed else "")
            dash = DASH.get(kind)
            extra = f' stroke-dasharray="{" ".join(f"{v:g}" for v in dash)}"' if dash else ""
            fill = ' fill="black"' if filled else ""
            out.append(f'<path d="{d}" stroke-width="{WEIGHT.get(kind, 0.25):g}"{extra}{fill}/>')
        out.append("</g>")
        # One family that exists on macOS: Qt's SVG renderer (TechDraw) warns of a
        # missing "Sans-serif" for the generic name in the Report view.
        out.append('<g font-family="Helvetica" fill="black" stroke="none">')
        for x, y, size, text, anchor in self.texts:
            if anchor == "vertical":
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size:g}" text-anchor="middle" transform="rotate(-90 {x:.3f} {y:.3f})">{_esc(text)}</text>')
            else:
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size:g}" text-anchor="{anchor}">{_esc(text)}</text>')
        out.append("</g></svg>")
        return "\n".join(out) + "\n"

    def pdf(self):
        """One page, its lines and Helvetica text: a PDF 1.4 file's bytes."""
        k = 72.0 / 25.4  # points per mm
        H = self.h
        ops = ["1 J 1 j"]
        for kind, pts, closed, filled in self.lines:
            dash = DASH.get(kind)
            ops.append(f"{WEIGHT.get(kind, 0.25) * k:.3f} w")
            ops.append(("[" + " ".join(f"{v * k:.2f}" for v in dash) + "] 0 d") if dash else "[] 0 d")
            seg = [f"{pts[0][0] * k:.3f} {(H - pts[0][1]) * k:.3f} m"] + [f"{x * k:.3f} {(H - y) * k:.3f} l" for (x, y) in pts[1:]]
            ops.append(" ".join(seg) + (" h" if closed else "") + (" b" if filled else " S"))
        for x, y, size, text, anchor in self.texts:
            fs = size * k
            width = 0.5 * fs * len(text)  # Helvetica averages about half an em
            if anchor == "vertical":
                ops.append(f"BT /F1 {fs:.2f} Tf 0 1 -1 0 {x * k:.3f} {(H - y) * k - width / 2:.3f} Tm ({_pdfstr(text)}) Tj ET")
                continue
            shift = {"middle": width / 2, "end": width}.get(anchor, 0.0)
            ops.append(f"BT /F1 {fs:.2f} Tf {x * k - shift:.3f} {(H - y) * k:.3f} Td ({_pdfstr(text)}) Tj ET")
        content = zlib.compress("\n".join(ops).encode("latin-1", "replace"))
        objs = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.w * k:.2f} {self.h * k:.2f}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".encode(),
            b"<< /Length " + str(len(content)).encode() + b" /Filter /FlateDecode >>\nstream\n" + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            f"<< /Title ({_pdfstr(self.title)}) /Producer (Agent Link for FreeCAD) >>".encode("latin-1", "replace"),
        ]
        buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, o in enumerate(objs, 1):
            offsets.append(len(buf))
            buf += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
        xref = len(buf)
        buf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            buf += f"{off:010d} 00000 n \n".encode()
        buf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {len(objs)} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(buf)

    def dxf(self):
        """AutoCAD R12 DXF: LINE and TEXT entities on a layer per kind, in mm,
        y up."""
        H = self.h
        out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4", "0", "ENDSEC"]
        kinds = sorted({k for (k, _, _, _) in self.lines} | {"text"})
        out += ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(kinds))]
        for kd in kinds:
            out += ["0", "LAYER", "2", kd.upper(), "70", "0", "62", "7", "6", "CONTINUOUS"]
        out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
        for kind, pts, closed, _ in self.lines:
            seq = pts + ([pts[0]] if closed else [])
            for (x0, y0), (x1, y1) in zip(seq, seq[1:]):
                out += ["0", "LINE", "8", kind.upper(), "10", f"{x0:.4f}", "20", f"{H - y0:.4f}", "30", "0.0", "11", f"{x1:.4f}", "21", f"{H - y1:.4f}", "31", "0.0"]
        for x, y, size, text, anchor in self.texts:
            rot = 90 if anchor == "vertical" else 0
            out += ["0", "TEXT", "8", "TEXT", "10", f"{x:.4f}", "20", f"{H - y:.4f}", "30", "0.0", "40", f"{size:g}", "1", text.replace("\u2300", "%%c").replace("\u00b1", "%%p").replace("\u00d7", "x").replace("\u2334", "CBORE ").replace("\u2335", "CSK ").replace("\u21a7", "DEEP "), "50", str(rot)]
            if anchor in ("middle", "vertical", "end"):
                out += ["72", "2" if anchor == "end" else "1", "11", f"{x:.4f}", "21", f"{H - y:.4f}", "31", "0.0"]
        out += ["0", "ENDSEC", "0", "EOF"]
        return "\n".join(out) + "\n"


# ---- laying views out ---------------------------------------------------------------------

# Where each view goes in the grid, front at (0, 0), rows counted down the
# page. First angle (ISO): the top view under the front, the right view on
# its left. Third angle (ASME): the top view over it, the right on its right.
GRID = {
    "first": {"front": (0, 0), "top": (0, 1), "bottom": (0, -1), "right": (-1, 0), "left": (1, 0), "back": (2, 0)},
    "third": {"front": (0, 0), "top": (0, -1), "bottom": (0, 1), "right": (1, 0), "left": (-1, 0), "back": (2, 0)},
}
ISO_CELLS = [(1, -1), (-1, -1), (1, 1), (-1, 1), (2, -1), (2, 1)]


# Room round each straight view on the paper, mm: its name above (LABEL);
# below and to its right an overall dimension 10 mm off the outline, its
# text, and room to stack one more 7 mm further out (DIM_ROOM); GAP between
# neighbours' rooms.
LABEL = 7.0
DIM_OFF = 10.0
DIM_STACK = 7.0
DIM_ROOM = 19.0
GAP = 8.0
# How full a sheet may be (views with their rooms over the drawing area
# the title block leaves): the largest standard scale up to this.
FILL_MAX = 0.72
STEP = 5.0


def _hit(a, b, clear=0.0):
    return a[0] < b[2] + clear and b[0] < a[2] + clear and a[1] < b[3] + clear and b[1] < a[3] + clear


def _grid(sizes, projection, s):
    """The straight views at scale s in their grid cells: ({view: (col,
    row)}, column widths, row heights, cell rects relative to the grid's
    top left) — each cell the view, its name above and its dimension room
    below and right."""
    cells = {v: GRID[projection][v] for v in sizes if v != "iso"}
    cols = sorted({c for (c, _) in cells.values()})
    rows = sorted({r for (_, r) in cells.values()})
    cw = {c: max(sizes[v][0] * s + DIM_ROOM for v in cells if cells[v][0] == c) for c in cols}
    rh = {r: max(sizes[v][1] * s + DIM_ROOM + LABEL for v in cells if cells[v][1] == r) for r in rows}
    xs, x = {}, 0.0
    for c in cols:
        xs[c] = x
        x += cw[c] + GAP
    ys, y = {}, 0.0
    for r in rows:
        ys[r] = y
        y += rh[r] + GAP
    rects = {}
    for v, (c, r) in cells.items():
        w, h = sizes[v][0] * s, sizes[v][1] * s
        # The view in its column's middle, at its row's top under its name.
        vx = xs[c] + (cw[c] - DIM_ROOM - w) / 2
        vy = ys[r] + LABEL + (rh[r] - LABEL - DIM_ROOM - h) / 2
        rects[v] = (vx, vy - LABEL, vx + w + DIM_ROOM, vy + h + DIM_ROOM)
    return cells, x - GAP if cols else 0.0, y - GAP if rows else 0.0, rects


def _spots(area, w, h):
    x0, y0, x1, y1 = area
    nx, ny = int((x1 - x0 - w) // STEP), int((y1 - y0 - h) // STEP)
    for i in range(nx + 1):
        for j in range(ny + 1):
            yield x0 + i * STEP, y0 + j * STEP


def _arrange(sizes, area, block, projection, s, iso_scales):
    """One try at scale s: None when it does not fit, else (centres, view
    rects, cell rects, iso scale)."""
    x0, y0, x1, y1 = area
    cells, gw, gh, rel = _grid(sizes, projection, s)
    if gw > x1 - x0 + 1e-9 or gh > y1 - y0 + 1e-9:
        return None
    # The grid where it clears the title block, nearest the middle of the
    # band above the block (else of the whole area).
    aim = ((x0 + x1) / 2, (y0 + (block[1] if block else y1)) / 2)
    best = None
    for gx, gy in _spots(area, gw, gh):
        placed = {v: (gx + r[0], gy + r[1], gx + r[2], gy + r[3]) for v, r in rel.items()}
        if block and any(_hit(r, block) for r in placed.values()):
            continue
        d = (gx + gw / 2 - aim[0]) ** 2 + (gy + gh / 2 - aim[1]) ** 2
        if best is None or d < best[0]:
            best = (d, placed)
    if best is None:
        return None
    rects = best[1]
    centres, outline = {}, {}
    for v, r in rects.items():
        w, h = sizes[v][0] * s, sizes[v][1] * s
        vx, vy = r[0], r[1] + LABEL
        centres[v] = (vx + w / 2, vy + h / 2)
        outline[v] = (vx, vy, vx + w, vy + h)
    si = None
    if "iso" in sizes:
        # The pictorial view in the room left, at the largest standard
        # scale up to the views' (smaller is fine: it is not measured).
        taken = list(rects.values()) + ([block] if block else [])
        free_c = [c for c in ((cc, rr) for cc in {c for c, _ in cells.values()} for rr in {r for _, r in cells.values()}) if c not in cells.values()]
        for t in iso_scales:
            if t > s + 1e-9:
                continue
            w, h = sizes["iso"][0] * t, sizes["iso"][1] * t + LABEL
            near = None
            if free_c and rects:
                # Aim at the empty grid cell (beside the front, over or under the side view).
                fc = free_c[0]
                col_x = [r for v, r in rects.items() if cells[v][0] == fc[0]]
                row_y = [r for v, r in rects.items() if cells[v][1] == fc[1]]
                ax = (min(r[0] for r in col_x) + max(r[2] for r in col_x)) / 2 if col_x else (x0 + x1) / 2
                ay = (min(r[1] for r in row_y) + max(r[3] for r in row_y)) / 2 if row_y else (y0 + y1) / 2
                near = (ax, ay)
            near = near or ((x0 + x1) / 2, (y0 + y1) / 2)
            got = None
            for px, py in _spots(area, w, h):
                r = (px, py, px + w, py + h)
                if any(_hit(r, q, GAP / 2) for q in taken):
                    continue
                d = (px + w / 2 - near[0]) ** 2 + (py + h / 2 - near[1]) ** 2
                if got is None or d < got[0]:
                    got = (d, r)
            if got is not None:
                r = got[1]
                rects["iso"] = r
                outline["iso"] = (r[0], r[1] + LABEL, r[2], r[3])
                centres["iso"] = ((r[0] + r[2]) / 2, (r[1] + LABEL + r[3]) / 2)
                si = t
                break
        if si is None:
            return None
    return centres, outline, rects, si


def layout(sizes, paper, projection="first", scale=None, margin=10.0, title_h=18.0, gap=None, area=None, block=None):
    """Views in their places on the paper: sizes {view: (w, h)} in model mm;
    paper (W, H). The straight views in their projection's grid, each with
    room for its name above and its overall dimensions below and right
    (outside the outline); the iso view in the room left, at its own
    standard scale up to theirs. area: the drawing area (x0, y0, x1, y1;
    else the frame at margin); block: the title block's (w, h) in the
    area's bottom right corner (else a strip title_h high across).

    {scale, scales: {view: scale}, centres: {view: (x, y)}, boxes: {view:
    outline rect}, cells: {view: rect with its rooms}, fill} in paper mm (y
    down), at the largest standard scale that fits and fills the area at
    most FILL_MAX, or the scale given. A ValueError says when it cannot."""
    W, H = paper
    area = area or (margin, margin, W - margin, H - margin)
    bw, bh = block if block else (area[2] - area[0], title_h)
    brect = (area[2] - bw, area[3] - bh, area[2], area[3]) if bw > 0 and bh > 0 else None
    if not sizes or any(w <= 0 or h <= 0 for w, h in sizes.values()):
        raise ValueError("The views are empty: nothing to draw.")
    room = (area[2] - area[0]) * (area[3] - area[1]) - (bw * bh if brect else 0.0)
    tries = [scale] if scale is not None else SCALES
    first_fit = None
    for s in tries:
        got = _arrange(sizes, area, brect, projection, s, SCALES)
        if got is None:
            continue
        centres, outline, rects, si = got
        fill = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects.values()) / room
        out = {"scale": s, "fit": s, "scales": {v: (si if v == "iso" else s) for v in sizes}, "centres": centres, "boxes": outline,
               "cells": rects, "fill": round(fill, 3), "area": area, "block": brect}
        if scale is not None or fill <= FILL_MAX:
            return out
        first_fit = first_fit or out
    if scale is not None:
        fit = next((t for t in SCALES if _arrange(sizes, area, brect, projection, t, SCALES)), None)
        raise ValueError(f"scale: {scale_text(scale)} does not fit this paper with room for the dimensions ({fit and scale_text(fit)} the largest standard one that does).")
    if first_fit:
        return first_fit
    raise ValueError("Too big for the paper even at 1:100 — A3, or fewer views.")


def choose(sizes, papers, projection="first", scale=None):
    """The paper and layout: papers [(name, (W, H), area, block)] smallest
    first. The largest standard scale any of them takes (each at most
    FILL_MAX full); the smallest paper at that scale. (name, layout); a
    ValueError when none fits."""
    best, err = None, None
    for name, paper, area, block in papers:
        try:
            L = layout(sizes, paper, projection, scale, area=area, block=block)
        except ValueError as e:
            err = e
            continue
        if L["fill"] > FILL_MAX and scale is None:
            L = dict(L, crowded=True)
        key = (0 if L.get("crowded") else 1, L["scale"])
        if best is None or key > best[0]:
            best = (key, name, L)
    if best is None:
        raise err or ValueError("nothing fits")
    return best[1], best[2]


def extent_dims(outline, axes, extent, sizes_seen=None):
    """The overall dimensions, each once: for each straight view in order,
    its horizontal extent under it and its vertical extent to its right
    (axes: {view: (h axis, v axis)}), each DIM_OFF mm off the outline,
    stacked DIM_STACK further out when a side has more. [(view, axis,
    a, b, offset, mm)] in paper mm, for Sheet.dimension."""
    done, out, side = set(), [], {}
    for v, box in outline.items():
        if v not in axes:
            continue
        ha, va = axes[v]
        left, top, right, bottom = box
        if ha not in done:
            k = side.get((v, "below"), 0)
            side[(v, "below")] = k + 1
            out.append((v, ha, (left, bottom), (right, bottom), DIM_OFF + DIM_STACK * k, extent[ha]))
            done.add(ha)
        if va not in done:
            k = side.get((v, "right"), 0)
            side[(v, "right")] = k + 1
            out.append((v, va, (right, bottom), (right, top), DIM_OFF + DIM_STACK * k, extent[va]))
            done.add(va)
    return out


def free_spot(L, w, h):
    """A top left corner for a w × h box (a hole table) in L's drawing
    area clear of its views' cells and its title block: over the title
    block first, then wherever is nearest the area's bottom right. None
    when there is no room."""
    area, block = L["area"], L.get("block")
    taken = list(L["cells"].values()) + ([block] if block else [])
    aim = (area[2], block[1] if block else area[3])
    best = None
    for x, y in _spots(area, w, h):
        r = (x, y, x + w, y + h)
        if any(_hit(r, q, 2.0) for q in taken):
            continue
        d = (x + w - aim[0]) ** 2 + (y + h - aim[1]) ** 2
        if best is None or d < best[0]:
            best = (d, (x, y))
    return best[1] if best else None


def text_box(t):
    """A text's box on the paper (x0, y0, x1, y1), its width reckoned at
    0.6 em a character."""
    x, y, size, text, anchor = t
    w = 0.6 * size * len(text)
    if anchor == "vertical":
        return (x - size, y - w / 2, x + 0.2 * size, y + w / 2)
    x0 = {"middle": x - w / 2, "end": x - w}.get(anchor, x)
    return (x0, y - size, x0 + w, y + 0.25 * size)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _pdfstr(s):
    # WinAnsi has Ø, ± and × but no ⌀: the diameter sign is drawn as Ø.
    s = str(s).replace("\u2014", "-").replace("\u2013", "-").replace("\u2300", "\u00d8")
    # Nor the ISO 129 hole symbols: counterbore, countersink and depth in words.
    s = s.replace("\u2334", "CBORE ").replace("\u2335", "CSK ").replace("\u21a7", "DEEP ")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
