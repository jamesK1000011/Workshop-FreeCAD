# SPDX-License-Identifier: LGPL-2.1-or-later
# Screw thread sizes from the standards' tables, in millimetres: ISO metric
# coarse and fine (ISO 261 / ISO 724 basic profile, tap drills after
# ISO 2306) and Unified UNC / UNF (ASME B1.1 basic sizes, the usual 75 %
# tap drills). No FreeCAD here, so it is tested anywhere.

import os

from addonkit import data

INCH = 25.4

# The basic profile's heights, as fractions of the pitch (ISO 68-1).
PITCH_DIA = 0.649519  # d2 = d - 0.649519 P
MINOR_INT = 1.082532  # D1 = D - 1.082532 P (the nut's minor)
MINOR_EXT = 1.226869  # d3 = d - 1.226869 P (the bolt's minor)

# The tables are data (data/threads.json: every size with its source); the
# person's own sizes go in ~/.config/addonkit/workshop_make/threads.json.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROWS = data.load(os.path.join(_HERE, "data"), "threads", package="workshop_make")["entries"].values()
# (nominal mm, coarse pitch, tap drill mm)
METRIC_COARSE = [(r["nominal"], r["pitch"], r["tapDrill"]) for r in _ROWS if r["series"] == "metric"]
# (nominal mm, fine pitch): tap drill D - P.
METRIC_FINE = [(r["nominal"], r["pitch"]) for r in _ROWS if r["series"] == "metric-fine"]
# (name, major inch, threads per inch, series, tap drill inch, the drill's name)
UNIFIED = [(r["name"], r["majorInch"], r["tpi"], r["series"].upper(), r["tapDrillInch"], r["tapDrillName"]) for r in _ROWS if r["series"] in ("unc", "unf")]
SERIES = ("metric", "metric-fine", "unc", "unf")


def _num(x):
    return f"{x:g}"


def _metric(d, p, fine, tap=None):
    tap = tap if tap is not None else round(d - p, 2)
    return {
        "size": f"M{_num(d)}" + (f"x{_num(p)}" if fine else ""),
        "series": "metric-fine" if fine else "metric",
        "major": d,
        "pitch": p,
        "pitchDia": round(d - PITCH_DIA * p, 3),
        "minorInt": round(d - MINOR_INT * p, 3),
        "minorExt": round(d - MINOR_EXT * p, 3),
        "tapDrill": tap,
        "freecad": _fc_metric(d, p),
    }


def _fc_metric(d, p):
    """The size as FreeCAD's Hole lists it: M6x1.0, M10x1.25."""
    ps = f"{p:.2f}".rstrip("0")
    if ps.endswith("."):
        ps += "0"
    return f"M{_num(d)}x{ps}"


def _unified(name, maj, tpi, series, tap, drill):
    p = INCH / tpi
    d = maj * INCH
    return {
        "size": f"{name}-{tpi}",
        "series": series.lower(),
        "major": round(d, 3),
        "pitch": round(p, 4),
        "tpi": tpi,
        "pitchDia": round(d - PITCH_DIA * p, 3),
        "minorInt": round(d - MINOR_INT * p, 3),
        "minorExt": round(d - MINOR_EXT * p, 3),
        "tapDrill": round(tap * INCH, 3),
        "tapDrillName": drill,
        "majorInch": maj,
        "freecad": name,
    }


def table(series=None):
    out = []
    if series in (None, "all", "metric"):
        out += [_metric(d, p, False, t) for d, p, t in METRIC_COARSE]
    if series in (None, "all", "metric-fine"):
        out += [_metric(d, p, True) for d, p in METRIC_FINE]
    if series in (None, "all", "unc", "unf"):
        out += [_unified(*u) for u in UNIFIED if series in (None, "all") or u[3].lower() == series]
    return out


def _norm(s):
    return str(s).strip().lower().replace(" ", "").replace("×", "x").replace("unc", "").replace("unf", "").rstrip("-")


def lookup(size):
    """One size by name: M6, M10x1.25, 1/4-20, #10-32, 1/4 (the coarse one)."""
    key = _norm(size)
    rows = table()
    for r in rows:
        if _norm(r["size"]) == key:
            return r
    # M8x1.25 names the coarse pitch; 1/4 or #10 alone means UNC.
    for r in rows:
        if r["series"].startswith("metric") and key in (_norm(r["size"]) + "x" + _num(r["pitch"]), _norm(r["freecad"])):
            return r
    for r in rows:
        if r["series"] == "unc" and key == _norm(r["freecad"]):
            return r
    return None


def nearest(diameter, inside, count=3):
    """The standard sizes nearest a measured diameter. A hole is read as a
    tap drill (to be tapped), the internal minor (a thread drawn
    cosmetically) or the major (a modelled thread's crest); a shaft as the
    major. Each with how far off, signed (measured − standard)."""
    out = []
    for r in table():
        if inside:
            cands = [("tapDrill", r["tapDrill"]), ("minorInt", r["minorInt"]), ("major", r["major"])]
        else:
            cands = [("major", r["major"])]
        as_, ref = min(cands, key=lambda c: abs(diameter - c[1]))
        out.append({"size": r["size"], "series": r["series"], "pitch": r["pitch"], "as": as_, "standard": ref, "off": round(diameter - ref, 3)})
    rank = {"tapDrill": 0, "minorInt": 1, "major": 2}
    out.sort(key=lambda x: (round(abs(x["off"]), 2), rank[x["as"]], x["series"] != "metric"))
    return out[:count]


def tie(near, within=0.02, limit=0.15):
    """The pitches to ask about when the nearest sizes share a diameter and
    differ by pitch alone (M10 coarse or fine, 1/4-20 or 1/4-28)."""
    if len(near) < 2 or abs(near[0]["off"]) > limit:
        return None
    same = [n for n in near if abs(abs(n["off"]) - abs(near[0]["off"])) <= within and n["as"] == near[0]["as"]]
    if len(same) < 2 or len({n["pitch"] for n in same}) < 2:
        return None
    return same
