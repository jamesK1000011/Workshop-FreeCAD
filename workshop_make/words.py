# SPDX-License-Identifier: LGPL-2.1-or-later
"""The window's words for Make's calls that gave only their tool's name or
no figure (Agent Link window review, round 6: setup, part_spec, hw_hole,
mass_properties, mass_target, mass_ballast, mass_calibrate; fastener_add's
are in workshop_fasteners/fam_fasteners.py): a short sentence with the
answer's value. Agent Link's echo asks each family's WORDS(name, args,
body) and shows the first words given in its caption and Activity row.
Pure Python, no FreeCAD, no Qt."""

from . import results


def _g(v, unit=""):
    return results._g(v, unit)


def _mass(b):
    rows = [r for r in (b.get("bodies") or []) if isinstance(r, dict)]
    if not rows:
        return None
    if len(rows) == 1:
        r = rows[0]
        return f"Weighed {r.get('body')}: {_g(r.get('mass'), 'g')} in {results.material_name(r.get('material'))}"
    total = sum(r.get("mass") or 0 for r in rows)
    return f"Weighed {len(rows)} bodies: {_g(total, 'g')} in all"


def _target(b):
    now = (b.get("now") or {}).get("mass")
    s = f"{b.get('body')} is {_g(now, 'g')}"
    if b.get("met"):
        return s + ": the target is met"
    m = b.get("mass") or {}
    if m:
        off = m.get("off")
        side = "under" if isinstance(off, (int, float)) and off < 0 else "over"
        s += f", {_g(abs(off) if isinstance(off, (int, float)) else off, 'g')} {side} the target {_g(m.get('target'), 'g')}"
    c = b.get("com") or {}
    if c.get("distance") is not None:
        s += f"; centre of mass {_g(c.get('distance'), 'mm')} off"
    if (b.get("ballast") or {}).get("mass") is not None:
        s += f"; {_g(b['ballast']['mass'], 'g')} of ballast would do"
    return s


def _ballast(b):
    n = len(b.get("pockets") or [])
    what = (b.get("fill") or {}).get("what") or "ballast"
    after = (b.get("after") or {}).get("mass")
    verb = "Cut" if b.get("cut") else "Laid out"
    return f"{verb} {n} ballast pocket{'s' if n != 1 else ''} in {b.get('body')}: {_g(b.get('fillMass'), 'g')} of {what}, {_g(after, 'g')} in all"


def _calibrate(b):
    if "reset" in b:
        return f"Mass calibration {b.get('reset')} put back to the material's figures"
    return f"Calibrated {b.get('for')}: weighed {_g(b.get('weighed'), 'g')} against {_g(b.get('expected'), 'g')} (x{b.get('scale')})"


def _hole(b):
    return results._hole(b).split(" (")[0].rstrip(".")


def _setup(b):
    if "added" not in b and "setup" not in b and "removed" not in b:
        rows = b.get("setups")
        if isinstance(rows, list):
            return f"Read {len(rows)} setup{'s' if len(rows) != 1 else ''}"
        if "body" in b:
            st = b.get("setup")
            return f"{b.get('body')} is in setup {st.get('name')}" if isinstance(st, dict) else f"{b.get('body')} is in no setup"
    return results._setup(b).rstrip(".")


def _spec(b):
    fc = b.get("freecadMaterial")
    mats = b.get("materials")
    if isinstance(fc, dict) and fc:
        return "Material set: " + ", ".join(f"{k} {v}" for k, v in list(fc.items())[:3])
    if isinstance(mats, dict) and mats:
        return "Materials: " + ", ".join(f"{k} {v.get('name', v) if isinstance(v, dict) else v}" for k, v in list(mats.items())[:3])
    spec = b.get("spec")
    if isinstance(spec, dict) and spec:
        return "Part spec: " + ", ".join(f"{k} {v}" for k, v in list(spec.items())[:3])
    return None


BY_TOOL = {"mass_properties": _mass, "mass_target": _target, "mass_ballast": _ballast, "mass_calibrate": _calibrate,
           "hw_hole": _hole, "setup": _setup, "part_spec": _spec}


def words(name, args, body):
    """Words for one of BY_TOOL's calls, or None (another tool's, a
    refusal, an answer without the figures). Never raises."""
    fn = BY_TOOL.get(name)
    if fn is None or not isinstance(body, dict) or body.get("error"):
        return None
    try:
        w = fn(body)
    except Exception:  # noqa: BLE001
        return None
    w = str(w or "").strip()
    return w[:120] or None
