# SPDX-License-Identifier: LGPL-2.1-or-later
"""The window's words for Make's calls that gave only their tool's name or
no figure (Agent Link window review, round 6: setup, part_spec, hw_hole,
mass_properties, mass_target, mass_ballast, mass_calibrate; round 7:
hw_embed, hw_unembed, thread_cut; fastener_add's are in
workshop_fasteners/fam_fasteners.py): a short sentence with the
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


def _mat_name(v):
    """A material row's name in words: a string, or a dict's name or id."""
    if isinstance(v, dict):
        v = v.get("name") or v.get("id")
    return results.material_name(v) if v else None


def _spec(b):
    """The spec and the materials in words, never a dict's text (window
    round 7, 04-012: "Material set: Bracket {'note': …}"): "Bracket in
    PETG; spec minWall 1.2, massMax 60", and "no FreeCAD card" where
    FreeCAD's library has none."""
    fc = b.get("freecadMaterial") if isinstance(b.get("freecadMaterial"), dict) else {}
    mats = b.get("materials") if isinstance(b.get("materials"), dict) else {}
    bits = []
    names = list(fc) or list(mats)
    if names:
        rows = []
        for k in names[:3]:
            m = _mat_name(mats.get(k))
            card = fc.get(k) if isinstance(fc.get(k), dict) else {}
            row = f"{k} in {m}" if m else str(k)
            if card and not card.get("card"):
                row += " (no FreeCAD card)"
            rows.append(row)
        bits.append(("Material set: " if fc else "Materials: ") + ", ".join(rows))
    spec = b.get("spec")
    if isinstance(spec, dict) and spec:
        bits.append(("spec " if bits else "Part spec: ") + ", ".join(f"{k} {v}" for k, v in list(spec.items())[:3]
                                                              if not isinstance(v, (dict, list))))
    return "; ".join(bits) or None


def _embed(b):
    p, pause = b.get("pocket") or {}, b.get("pause") or {}
    if not isinstance(p, dict) or "what" not in b:
        return None
    s = f"Pocket for {b.get('what')} in {b.get('body')}: {_g(p.get('depth'), 'mm')} deep"
    if isinstance(pause, dict) and pause.get("afterLayer") is not None:
        s += f", pause after layer {pause.get('afterLayer')}"
    return s


def _unembed(b):
    if "removed" not in b:
        return None
    pocket = b.get("pocket")
    said = "pocket filled" if pocket == "filled" else "pocket left open" if isinstance(pocket, str) else None
    return f"Took {b.get('removed')} out of {b.get('body')}" + (f": {said}" if said else "")


def _thread_cut(b):
    t = b.get("thread")
    if not isinstance(t, dict) or not t.get("size"):
        return None
    s = f"{t.get('size')} {t.get('mode') or ''} thread in {t.get('body') or b.get('body')}".replace("  ", " ")
    if t.get("depth") is not None:
        s += f", {_g(t.get('depth'), 'mm')} deep"
    if isinstance(b.get("removed"), (int, float)) and not isinstance(b.get("removed"), bool):
        s += f", {_g(b['removed'], 'mm³')} removed"
    return s


BY_TOOL = {"mass_properties": _mass, "mass_target": _target, "mass_ballast": _ballast, "mass_calibrate": _calibrate,
           "hw_hole": _hole, "setup": _setup, "part_spec": _spec, "hw_embed": _embed, "hw_unembed": _unembed,
           "thread_cut": _thread_cut}


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
