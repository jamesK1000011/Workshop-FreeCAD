# SPDX-License-Identifier: LGPL-2.1-or-later
"""Screw thread sizes, in millimetres, from FreeCAD's own thread tables:
the ones PartDesign Hole sizes its holes from (ISO metric coarse and fine,
UNC, UNF), read off a Hole in a hidden scratch document once a session.
Each size's major diameter is FreeCAD's ThreadDiameter and its tap drill
the Diameter FreeCAD gives a threaded, unmodelled hole of that size.

Workshop's own data (data/threads.json) holds only what FreeCAD lacks:
a Unified size's threads per inch (FreeCAD's Python gives no Unified
pitch) and its tap drill's name; heat-set insert holes come from
data/metric-hardware.json. The person's own sizes that FreeCAD has no row
for go in ~/.config/workshop_make/threads.json.

The arithmetic below is pure Python: the tests give it a stand-in table
(use()), as FreeCAD is not needed to check it."""

import os
import re

from workshop_make import datafiles as data

INCH = 25.4

# The basic profile's heights, as fractions of the pitch (ISO 68-1).
PITCH_DIA = 0.649519  # d2 = d - 0.649519 P
MINOR_INT = 1.082532  # D1 = D - 1.082532 P (the nut's minor)
MINOR_EXT = 1.226869  # d3 = d - 1.226869 P (the bolt's minor)

SERIES = ("metric", "metric-fine", "unc", "unf")
# FreeCAD's Hole ThreadType for each series.
HOLE_TYPE = {"metric": "ISOMetricProfile", "metric-fine": "ISOMetricFineProfile", "unc": "UNC", "unf": "UNF"}

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_HERE, "data")


def _extras():
    return data.load(_DATA, "threads", accepts=">=2.0,<3", package="workshop_make")["entries"]


def _inserts():
    try:
        rows = data.load(_DATA, "metric-hardware", package="workshop_make")["entries"]
    except Exception:  # noqa: BLE001
        return {}
    return {k: v["insert"] for k, v in rows.items() if v.get("insert")}


def _insert(size, inserts):
    """A heat-set insert's hole: Fasteners Workbench's IUT table when it is
    installed and has the size, else Workshop's typical figures (FreeCAD
    has none)."""
    try:
        from workshop_fasteners import api as _fasteners

        f = _fasteners.insert_figures(size)
    except Exception:  # noqa: BLE001
        f = None
    if f:
        return {"hole": f["hole"], "depth": f["depth"], "source": f["source"]}
    if size in inserts:
        ins = inserts[size]
        return {"hole": ins[0], "depth": ins[1], "source": "Workshop Make"}
    return None


# ---- FreeCAD's tables ------------------------------------------------------------------

def read_freecad():
    """FreeCAD's thread rows: [{series, designation, major, tapDrill}],
    read off a PartDesign Hole in a hidden scratch document (closed after;
    the active document is put back). [] when PartDesign is not here."""
    try:
        import FreeCAD
        import PartDesign  # noqa: F401
    except ImportError:
        return []
    was = FreeCAD.ActiveDocument
    doc = None
    rows = []
    try:
        try:
            doc = FreeCAD.newDocument("WorkshopThreadTables", hidden=True, temp=True)
        except TypeError:  # an older signature
            doc = FreeCAD.newDocument("WorkshopThreadTables")
        h = doc.addObject("PartDesign::Hole", "Probe")
        for series, tt in HOLE_TYPE.items():
            try:
                h.ThreadType = tt
            except Exception:  # noqa: BLE001 — a type this release lacks
                continue
            for name in list(h.getEnumerationsOfProperty("ThreadSize") or []):
                try:
                    h.ThreadSize = name
                    h.Threaded = True
                    h.ModelThread = False
                    major = float(getattr(h, "ThreadDiameter", 0) or 0)
                    tap = float(h.Diameter)
                except Exception:  # noqa: BLE001
                    continue
                if major > 0 and tap > 0:
                    rows.append({"series": series, "designation": str(name), "major": round(major, 4), "tapDrill": round(tap, 4)})
    except Exception:  # noqa: BLE001
        rows = []
    finally:
        if doc is not None:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:  # noqa: BLE001
                pass
        if was is not None:
            try:
                FreeCAD.setActiveDocument(was.Name)
            except Exception:  # noqa: BLE001
                pass
    return rows


_SOURCE = [read_freecad]
_CACHE = []


def use(source):
    """Where the raw rows come from: FreeCAD's (read_freecad) unless a test
    gives a stand-in. Clears the cache."""
    _SOURCE[0] = source or read_freecad
    _CACHE.clear()


def _num(x):
    return f"{x:g}"


def _profile(row, d, p):
    row.update({"major": round(d, 3), "pitch": None if p is None else round(p, 4)})
    if p is None:
        row.update({"pitchDia": None, "minorInt": None, "minorExt": None})
    else:
        row.update({"pitchDia": round(d - PITCH_DIA * p, 3), "minorInt": round(d - MINOR_INT * p, 3), "minorExt": round(d - MINOR_EXT * p, 3)})
    return row


def _metric_name(designation):
    """(nominal, pitch or None) from FreeCAD's "M6x1.0" or "M6"."""
    m = re.match(r"^M([\d.]+)(?:\s*x\s*([\d.]+))?", str(designation).strip())
    if not m:
        return None, None
    return float(m.group(1)), (float(m.group(2)) if m.group(2) else None)


def _build():
    raw = list(_SOURCE[0]() or [])
    extras = _extras()
    unified = {(v["series"], v.get("name")): v for v in extras.values() if v.get("series") in ("unc", "unf") and v.get("tpi") and v.get("name")}
    inserts = _inserts()
    out, have = [], set()
    for r in raw:
        s = r["series"]
        if s.startswith("metric"):
            nom, p = _metric_name(r["designation"])
            if nom is None:
                continue
            fine = s == "metric-fine"
            size = f"M{_num(nom)}" + (f"x{_num(p)}" if fine and p is not None else "")
            row = {"size": size, "series": s, "freecad": r["designation"], "tapDrill": round(r["tapDrill"], 3), "source": "FreeCAD"}
            _profile(row, r["major"], p)
            if not fine:
                ins = _insert(f"M{_num(nom)}", inserts)
                if ins:
                    row["insert"] = ins
        else:
            ex = unified.get((s, r["designation"]))
            tpi = ex["tpi"] if ex else None
            p = INCH / tpi if tpi else None
            row = {"size": f"{r['designation']}-{tpi}" if tpi else r["designation"], "series": s, "freecad": r["designation"],
                   "tapDrill": round(r["tapDrill"], 3), "majorInch": round(r["major"] / INCH, 4), "source": "FreeCAD"}
            _profile(row, r["major"], p)
            if tpi:
                row["tpi"] = tpi
                row["tpiSource"] = "Workshop Make"
            if ex and ex.get("tapDrillName"):
                row["tapDrillName"] = ex["tapDrillName"]
        if (row["series"], row["size"]) in have:
            continue
        have.add((row["series"], row["size"]))
        out.append(row)
    # The person's own sizes, only where FreeCAD has no row for them.
    for k, v in extras.items():
        if v.get("source") != "user" and "nominal" not in v and "majorInch" not in v:
            continue
        s = v.get("series")
        if s in ("metric", "metric-fine") and v.get("nominal") and v.get("pitch") and v.get("tapDrill"):
            d, p = float(v["nominal"]), float(v["pitch"])
            size = f"M{_num(d)}" + (f"x{_num(p)}" if s == "metric-fine" else "")
            row = {"size": size, "series": s, "freecad": None, "tapDrill": float(v["tapDrill"]), "source": v.get("source", "user")}
            _profile(row, d, p)
        elif s in ("unc", "unf") and v.get("majorInch") and v.get("tpi") and v.get("tapDrillInch"):
            d, p = float(v["majorInch"]) * INCH, INCH / int(v["tpi"])
            row = {"size": f"{v.get('name', k)}-{v['tpi']}", "series": s, "freecad": None, "tapDrill": round(float(v["tapDrillInch"]) * INCH, 3),
                   "majorInch": float(v["majorInch"]), "tpi": int(v["tpi"]), "source": v.get("source", "user")}
            _profile(row, d, p)
        else:
            continue
        if (row["series"], row["size"]) not in have:
            have.add((row["series"], row["size"]))
            out.append(row)
    return out


def table(series=None):
    """Every size of a series (all when None), FreeCAD's first. [] when
    FreeCAD's tables cannot be read here."""
    if not _CACHE:
        _CACHE.append(_build())
    rows = _CACHE[0]
    if series in (None, "all"):
        return list(rows)
    return [r for r in rows if r["series"] == series]


def _norm(s):
    return str(s).strip().lower().replace(" ", "").replace("×", "x").replace("unc", "").replace("unf", "").rstrip("-")


def _same_metric(key, r):
    """M8x1.25 names M8's coarse pitch; FreeCAD's own M6x1.0 its row."""
    if not r["series"].startswith("metric"):
        return False
    names = {_norm(r["size"])}
    if r.get("freecad"):
        names.add(_norm(r["freecad"]))
    if r["pitch"] is not None:
        names.add(_norm(r["size"]) + "x" + _num(r["pitch"]))
    return key in names


def lookup(size):
    """One size by name: M6, M10x1.25, 1/4-20, #10-32, 1/4 (the coarse one)."""
    key = _norm(size)
    rows = table()
    for r in rows:
        if _norm(r["size"]) == key:
            return r
    for r in rows:
        if _same_metric(key, r):
            return r
    # 1/4 or #10 alone means UNC.
    for r in rows:
        if r["series"] == "unc" and key == _norm(r.get("freecad") or ""):
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
        cands = [c for c in cands if c[1] is not None]
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
