# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's answers as a person reads them in the GUI: a check's verdict
first, then its figures with units, and one line for the Report view.
Refusals in person-facing words: the tool's message is written for the
agent (it may name tools and their arguments), so that part is dropped
here and the menu path said instead. Pure Python, no FreeCAD, no Qt."""
import re

_NO_SETUP = re.compile(r"^(?P<body>.+?) is in no print setup\b")
# A part of an agent-facing message: tool syntax ({ … }) or a tool's name.
_AGENT = re.compile(r"[{}]|\b[a-z]+_[a-z_]+\b|\bsetup (add|set|remove)\b")


def person_error(out):
    """What a refusal says to a person: no tool syntax, the menu to use."""
    msg = str((out.get("error") or {}).get("message") or "Refused.")
    m = _NO_SETUP.match(msg)
    if m:
        return f"{m.group('body')} isn't in a print setup yet: Make ▸ New Setup… first."
    keep = []
    for part in re.split(r" — |; ", msg):
        if _AGENT.search(part):
            break
        keep.append(part)
    text = "; ".join(keep).strip() or "Make can't do that with the part as it stands."
    text = text[0].upper() + text[1:]
    return text if text.endswith((".", "?", "!")) else text + "."


def _g(v, unit="", n=2):
    if not isinstance(v, (int, float)):
        return "–"
    s = f"{v:.{n}f}".rstrip("0").rstrip(".")
    return f"{s} {unit}".rstrip()


SEVERITY = {"error": "Problem", "warning": "Warning", "info": "Note"}


def material_name(text):
    """A material as a person reads it: its display name (pla -> PLA), and
    "(assumed)" in words where the tool says none was set, never the tool's
    own name for setting one."""
    t = str(text or "").strip()
    if not t:
        return "not set"
    mid, _, rest = t.partition(" (")
    assumed = "assumed" in rest
    name = None
    try:
        from . import materials

        c = materials.card(mid)
        name = c["name"].split(" (")[0] if c else None
    except Exception:  # noqa: BLE001 — a name is never worth a failure
        name = None
    if name is None:
        name = mid.upper() if len(mid) <= 5 and mid.replace("-", "").isalnum() else mid
    return f"{name} (assumed: no material set yet; the Materials tab sets one)" if assumed else name


def length(v, n=2):
    """A length in mm as FreeCAD shows it (its unit schema and decimals,
    "5.20 mm"), else n decimals and mm where FreeCAD is not here."""
    if not isinstance(v, (int, float)):
        return "–"
    try:
        import FreeCAD

        q = FreeCAD.Units.Quantity(float(v), FreeCAD.Units.Length).UserString
        if isinstance(q, str) and q:
            return q
    except Exception:  # noqa: BLE001 — no FreeCAD, or an older one
        pass
    return f"{v:.{n}f} mm"


def volume(v):
    """A volume given in mm³: mm³ under a cubic centimetre, else cm³."""
    if not isinstance(v, (int, float)):
        return "–"
    return f"{v:.1f} mm³" if abs(v) < 1000 else f"{v / 1000:.1f} cm³"


def figures_line(fig):
    """Part review's figures as the panel's footer line, each with its unit
    and the material by its display name: "Volume 24.0 cm³ · Mass 9.6 g ·
    Material PLA · As printed: …"."""
    bits = []
    if "volume" in fig:
        bits.append(f"Volume {volume(fig['volume'])}")
    if "mass" in fig:
        bits.append(f"Mass {_mass(fig['mass'])}")
    if "encasedMass" in fig:
        bits.append(f"Encased {_mass(fig['encasedMass'])}")
    if fig.get("material") is not None:
        name = material_name(fig["material"])
        bits.append("Material " + (name.split(" (")[0] + " (assumed)" if "(assumed" in name else name))
    if "wall" in fig:
        bits.append(f"Least wall {length(fig['wall'])}")
    if "safety" in fig:
        bits.append(f"Safety factor {_g(fig['safety'])}")
    if fig.get("as"):
        a = str(fig["as"])
        bits.append("As " + a if a.startswith("printed") else "Made " + a)
    shown = ("volume", "mass", "encasedMass", "material", "wall", "safety", "as")
    bits += [f"{k} {v}" for k, v in fig.items() if k not in shown]
    return "  ·  ".join(bits)


# Mass is shown to one decimal everywhere (Part Review and Mass Properties
# agree): a tenth of a gram is past what a printer or scale holds to.
def _mass(v):
    return _g(v, "g", 1)


def dfm(out):
    """(verdict, text, Report-view line) for dfm_check's answer."""
    body = out.get("body", "The part")
    open_ = [f for f in out.get("findings") or [] if not f.get("waived")]
    errors = [f for f in open_ if f.get("severity") == "error"]
    warns = [f for f in open_ if f.get("severity") == "warning"]
    if errors:
        verdict = f"{body} is not printable as it stands."
    elif warns:
        verdict = f"{body} is printable, with warnings."
    else:
        verdict = f"{body} is printable."
    lines = [verdict, ""]
    least = (out.get("wall") or {}).get("least")
    lines.append(f"Least wall: {_g(least, 'mm')}" if least is not None else "Least wall: not read")
    if out.get("setup"):
        lines.append(f"Print setup: {out['setup']}")
    if open_:
        lines.append("")
        for f in open_[:8]:
            lines.append(f"{SEVERITY.get(f.get('severity'), 'Note')}: {f.get('says') or f.get('rule', '')}")
        if len(open_) > 8:
            lines.append(f"…and {len(open_) - 8} more.")
    waived = len(out.get("findings") or []) - len(open_)
    if waived:
        lines.append(f"Waived: {waived}")
    line = f"DFM Check · {verdict} {len(errors)} problems, {len(warns)} warnings."
    return verdict, "\n".join(lines), line


VERDICT = {"pass": "passes", "fix": "needs fixing", "unknown": "can't be judged yet"}


def review(out):
    """(verdict, text, Report-view line) for part_review's answer."""
    body = out.get("body", "The part")
    verdict = f"{body} {VERDICT.get(out.get('verdict'), 'was reviewed')}."
    fig = out.get("figures") or {}
    lines = [verdict, "", f"Made by: {out.get('process', 'unknown')}"]
    if "mass" in fig:
        lines.append(f"Mass: {_mass(fig['mass'])} ({material_name(fig.get('material'))})")
    if "volume" in fig:
        lines.append(f"Volume: {_g(fig['volume'], 'mm³', 1)}")
    if "wall" in fig:
        lines.append(f"Least wall: {_g(fig['wall'], 'mm')}")
    if "safety" in fig:
        lines.append(f"Safety factor: {_g(fig['safety'])}")
    finds = out.get("findings") or []
    if finds:
        lines.append("")
        for f in finds:
            lines.append(f"{SEVERITY.get(f.get('severity'), 'Note')}: {f.get('says', '')}")
    for u in out.get("unjudged") or []:
        lines.append(f"Not judged: {u.split(':', 1)[-1].strip()}")
    line = f"Part Review · {verdict} {len(finds)} findings."
    return verdict, "\n".join(lines), line


def mass(out):
    """(verdict, text, Report-view line) for mass_properties' answer."""
    bodies = out.get("bodies") or []
    total = sum(b.get("mass") or 0 for b in bodies)
    verdict = (f"{bodies[0].get('body')} weighs {_mass(bodies[0].get('mass'))}." if len(bodies) == 1
               else f"{len(bodies)} parts weigh {_mass(total)} in all.")
    lines = [verdict]
    for b in bodies:
        com = b.get("com") or []
        lines += ["", f"{b.get('body')}: {_mass(b.get('mass'))}",
                  f"Material: {material_name(b.get('material'))}, {_g(b.get('density'), 'g/cm³')}",
                  f"Volume: {_g(b.get('volume'), 'mm³', 1)}",
                  "Centre of mass: " + (", ".join(_g(c, n=2) for c in com) + " mm" if com else "–"),
                  f"Made as: {str(b.get('as', '')).split(' (')[0]}"]
        pr = (b.get("inertia") or {}).get("principal")
        if pr:
            lines.append("Principal inertia: " + ", ".join(_g(x, n=1) for x in pr) + " g·mm²")
        for e in b.get("encased") or []:
            lines.append(f"Encased: {e.get('count')} × {e.get('what')}, {_mass(e.get('mass'))}")
    if out.get("printedNote"):
        lines += ["", out["printedNote"]]
    line = "Mass Properties · " + "; ".join(f"{b.get('body')} {_mass(b.get('mass'))}" for b in bodies) + "."
    return verdict, "\n".join(lines), line


SHOWN = {"dfm_check": dfm, "part_review": review, "mass_properties": mass}


def _short(v):
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    if isinstance(v, list) and all(isinstance(x, (str, int, float)) for x in v):
        return ", ".join(str(x) for x in v)
    if isinstance(v, (list, tuple)):
        return f"{len(v)} item" + ("" if len(v) == 1 else "s")
    return None


def line(title, out):
    """One Report-view line for any other answer: its plain figures, a count
    for anything nested, never a raw dict."""
    bits = []
    for k, v in out.items():
        if k in ("step", "note", "next") or isinstance(v, dict):
            continue
        s = _short(v)
        if s:
            bits.append(f"{k} {s}")
    return f"{title} · " + ("; ".join(bits)[:300] if bits else "done") + "."
