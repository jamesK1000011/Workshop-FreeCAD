# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's answers as a person reads them in the GUI: a check's verdict
first, then its figures with units, and one line for the Report view.
Refusals in person-facing words: the tool's message is written for the
agent (it may name tools and their arguments), so that part is dropped
here and the menu path said instead. Pure Python, no FreeCAD, no Qt."""
import re

from workshop_make import finding_words as fw

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
    try:
        from workshop import matname

        # A filament, a custom card, or FreeCAD's library by its id (a
        # UUID): its name, never the bare id.
        name = matname.shown(mid)
    except Exception:  # noqa: BLE001 — a name is never worth a failure
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


def basis_says(v):
    """The "as" record of a mass figure (how it was found) in a line, for a
    person: "solid", "printed: 2 walls, …", "sliced by …"."""
    if not isinstance(v, dict):
        return str(v or "")
    b = v.get("basis")
    if b == "solid":
        return "solid"
    if b == "sliced":
        parts = [f"sliced by {v.get('slicer') or 'the slicer'}: {v.get('grams')} g"]
        if v.get("partOnly"):
            parts.append("the part only")
            if v.get("supportGrams"):
                parts.append(f"supports {v['supportGrams']} g more")
            if v.get("otherGrams"):
                parts.append(f"prime tower and flush {v['otherGrams']} g more")
        else:
            parts.append("all the G-code's filament, brim and supports included")
        text = ", ".join(parts)
        if v.get("estimateGrams") is not None:
            text += f"; the estimate from walls and infill was {v['estimateGrams']:.1f} g"
        return text
    walls, top, bottom = v.get("walls"), v.get("topLayers"), v.get("bottomLayers")
    if v.get("layerHeight") is not None:
        text = (f"printed: {walls} walls, {top} top and {bottom} bottom layers of {v['layerHeight']} mm, {v.get('infillPct'):.0f}% infill — "
                f"{v.get('solidPct'):.0f}% of the solid, from {v.get('read') or 'nothing read: taken as solid'} "
                "(an estimate; the slicer's figure is the authority)")
    else:
        text = (f"printed: {walls} walls, {top} top and {bottom} bottom layers, {v.get('infillPct'):.0f}% infill "
                "(an estimate; the shells' mass on the surface)")
    if v.get("calibratedScale") is not None:
        text += f"; calibrated ×{v['calibratedScale']:.3f} to a weighed print of {v.get('weighedBody')} ({v.get('weighedGrams')} g)"
    return text


def unjudged_says(u):
    """One "unjudged" record in words."""
    if not isinstance(u, dict):
        return str(u).split(":", 1)[-1].strip()
    r = u.get("reason")
    if r == "noWallReading":
        return "no wall reading"
    if r == "waived":
        return f"the least wall is waived, and the check reads walls only under {u.get('readsUnder')} mm"
    if r == "stale":
        return "stale — the body changed since the solve; fea_solve again"
    if r == "nothingSolved":
        return "nothing solved"
    if r == "noSheet":
        return "give sheet [w, h] mm (or set the cut setup's sheet) to check it fits"
    return str(r)


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
        a = basis_says(fig["as"])
        bits.append("As " + a if a.startswith("printed") else "Made " + a)
    shown = ("volume", "mass", "encasedMass", "material", "wall", "safety", "as")
    bits += [f"{k} {v}" for k, v in fig.items() if k not in shown]
    return "  ·  ".join(bits)


def _count(n, word):
    return f"no {word}s" if not n else f"{n} {word}" + ("" if n == 1 else "s")


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
            lines.append(f"{SEVERITY.get(f.get('severity'), 'Note')}: {fw.says(f, out) or f.get('rule', '')}")
        if len(open_) > 8:
            lines.append(f"…and {len(open_) - 8} more.")
    waived = len(out.get("findings") or []) - len(open_)
    if waived:
        lines.append(f"Waived: {waived}")
    line = f"{verdict} DFM check: {_count(len(errors), 'problem')}, {_count(len(warns), 'warning')}."
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
            lines.append(f"{SEVERITY.get(f.get('severity'), 'Note')}: {fw.says(f, out)}")
    for u in out.get("unjudged") or []:
        lines.append(f"Not judged: {unjudged_says(u)}")
    line = f"{verdict} Part review: {_count(len(finds), 'finding')}."
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
                  f"Material: {material_name(str(b.get('material') or '') + (' (assumed)' if b.get('materialAssumed') else ''))}, {_g(b.get('density'), 'g/cm³')}",
                  f"Volume: {_g(b.get('volume'), 'mm³', 1)}",
                  "Centre of mass: " + (", ".join(_g(c, n=2) for c in com) + " mm" if com else "–"),
                  f"Made as: {basis_says(b.get('as', '')).split(' (')[0]}"]
        pr = (b.get("inertia") or {}).get("principal")
        if pr:
            lines.append("Principal inertia: " + ", ".join(_g(x, n=1) for x in pr) + " g·mm²")
        for e in b.get("encased") or []:
            lines.append(f"Encased: {e.get('count')} × {e.get('what')}, {_mass(e.get('mass'))}")
    if out.get("bandFactor"):
        lines += ["", (f"As printed is an estimate from walls and infill, a lower guide: the slicer's figure can be {out['bandFactor'][0]} to {out['bandFactor'][1]} times it "
                       "(massBand). Slice the body alone (slice or slice_with) and this tool uses the slicer's figure instead.")]
    line = verdict if len(bodies) == 1 else verdict[:-1] + ": " + "; ".join(f"{b.get('body')} {_mass(b.get('mass'))}" for b in bodies) + "."
    return verdict, "\n".join(lines), line


SHOWN = {"dfm_check": dfm, "part_review": review, "mass_properties": mass}


# ---- the Report view: one sentence a person reads, units with every figure;
# the machine fields stay in the tool's answer for agents ----

HOLE_KIND = {"clearance": "clearance hole", "counterbore": "counterbored hole", "countersink": "countersunk hole",
             "nut_trap": "hole with a nut trap", "insert": "heat-set insert pocket", "magnet": "magnet pocket"}


def _names(xs):
    xs = [str(x) for x in xs or []]
    return xs[0] if len(xs) == 1 else (", ".join(xs[:-1]) + " and " + xs[-1] if xs else "")


def _file(p):
    import os

    return os.path.basename(str(p))


def calibration_clause(said, allowance=None):
    """"Printer calibration: …" as a sentence: none kept, so what was added."""
    s = str(said or "")
    add = f"{_g(allowance)} mm added" if isinstance(allowance, (int, float)) else None
    if s.startswith("none"):
        return f"Printer calibration: none, so {add or 'the typical 0.2 mm added'}."
    kept = "the one kept with this document" if s == "calibrated" else s
    return f"Printer calibration: {kept}" + (f", {add}." if add else ".")


def _hole(out):
    size = str(out.get("size", ""))
    kind = out.get("kind")
    what = HOLE_KIND.get(kind, "hole")
    if kind == "magnet":
        size = size.replace("x", " × ") + " mm"
    depth = out.get("depth")
    if depth == "through":
        how = f", through {_g(out['through'], 'mm')}" if out.get("through") else ", through"
    elif isinstance(depth, (int, float)) or str(depth).replace(".", "", 1).isdigit():
        how = f", {_g(float(depth), 'mm')} deep"
    else:
        how = ""
    route = ("FreeCAD Hole, editable in Part Design" if out.get("route") == "PartDesign Hole"
             else "cut as a shape: a plain Part solid, not in a Part Design Body")
    s = f"{size} {what} in {out.get('body')}{how} ({route})."
    s += " " + calibration_clause(out.get("printerFit"), out.get("allowance"))
    side = ""
    if out.get("head"):
        if out.get("onSketch"):
            side = f"{out['head']} on the face the sketch is on (FreeCAD's Hole goes into the material from the sketch)"
        elif out.get("face"):
            side = f"{out['head']} on the face at {out['face']}, facing {out['facing']}"
        else:
            side = f"{out['head']} on the face through {out.get('headAt')}, facing {out.get('facing')}"
    if side:
        s += " " + side[0].upper() + side[1:].rstrip(".") + "."
    if out.get("sound") is False:
        s += " The part is no longer sound: check it with DFM Check."
    return s


def _fit(out):
    if "calibration" in out:
        c = out["calibration"]
        return f"Printer calibration kept: holes print {_g(c.get('hole'), 'mm')} small, pegs {_g(c.get('shaft'), 'mm')} big."
    of = "hole" if out.get("of") == "hole" else "peg"
    sizes = "; ".join(f"{k} {_g(v, 'mm')}" for k, v in (out.get("model") or {}).items())
    return f"For a {_g(out.get('nominal'), 'mm')} part, model the {of} at: {sizes}. " + calibration_clause(out.get("printerFit"))


def _setup(out):
    if "added" in out:
        a = out["added"] or {}
        return f"Setup {a.get('name')} made" + (f" with {_names(a.get('bodies'))}." if a.get("bodies") else ".")
    if "setup" in out and isinstance(out["setup"], dict):
        a = out["setup"]
        return f"Setup {a.get('name')} now has {_names(a.get('bodies')) or 'no parts'}."
    if "removed" in out:
        return f"Setup {out['removed']} removed; its parts have no process now."
    return "Setups read."


def _embed(out):
    p, pause = out.get("pocket") or {}, out.get("pause") or {}
    s = f"Pocket for {out.get('what')} in {out.get('body')}, {_g(p.get('depth'), 'mm')} deep; the print pauses after layer {pause.get('afterLayer')} (Z {_g(pause.get('z'), 'mm')}) to put it in."
    if out.get("thinSides"):
        s += " The wall beside or under the pocket is under the least wall: it may break through."
    return s


def _pauses(out):
    ps = out.get("pauses") or []
    if not ps:
        return f"{out.get('body')} needs no pause: nothing is encased in it."
    each = "; ".join(f"after layer {p.get('layer')} (Z {_g(p.get('z'), 'mm')})" + (f": {p.get('note')}" if p.get("note") else "") for p in ps)
    return f"{out.get('body')} needs {len(ps)} pause{'s' if len(ps) > 1 else ''}: {each}."


def _thread(out):
    t = out.get("thread")
    if t:
        bits = [f"major {_g(t.get('major'), 'mm')}"]
        if t.get("pitch") is not None:
            bits.append(f"pitch {_g(t.get('pitch'), 'mm', 3)}" + (f" ({t['tpi']} TPI)" if t.get("tpi") else ""))
        bits.append(f"tap drill {_g(t.get('tapDrill'), 'mm')}" + (f" ({t['tapDrillName']})" if t.get("tapDrillName") else ""))
        if t.get("insert"):
            bits.append(f"heat-set insert hole {_g(t['insert'].get('hole'), 'mm')}")
        return f"{t.get('size')}: " + ", ".join(bits) + " (FreeCAD's thread tables)."
    return f"{len(out.get('threads') or [])} thread sizes listed (FreeCAD's thread tables)."


def _slice(out):
    s = f"{out.get('body')} sliced with {out.get('slicer') or out.get('exe') or 'the slicer'}: {_file(out.get('gcode'))}"
    if out.get("pauses"):
        s += f", {len(out['pauses'])} pause{'s' if len(out['pauses']) > 1 else ''} written in"
    return s + ". Starting the print is up to you."


def _cut(out):
    sh = out.get("sheet") or []
    placed = out.get("placed") or []
    s = f"Cut files for {len(placed)} part{'s' if len(placed) != 1 else ''}"
    if len(sh) == 2:
        s += f" on a {_g(sh[0])} × {_g(sh[1])} mm sheet"
    files = out.get("files") or {}
    names = [_file(v) for v in (files.values() if isinstance(files, dict) else files)]
    s += (": " + ", ".join(names) if names else "") + "."
    if out.get("layout"):
        s += " Nested by FreeCAD's BIM Nest." if str(out["layout"]).startswith("FreeCAD") else " Laid out in rows."
    if out.get("left"):
        s += f" {_names(out['left'].get('bodies'))} did not fit on the sheet."
    return s


def _mill(out):
    st, sheet = out.get("step") or {}, out.get("setupSheet") or {}
    n = out.get("findings") or 0
    return (f"{out.get('body')} for milling: {_file(st.get('path'))} and the setup sheet {_file(sheet.get('path'))}; "
            f"the mill check {VERDICT.get(out.get('verdict'), 'ran')}" + (f" with {n} finding{'s' if n != 1 else ''}." if n else "."))


def _printer_status(out):
    job = out.get("job") or {}
    s = f"{out.get('printer')} is {str(out.get('state') or 'not saying its state').lower()}"
    if job.get("file"):
        s += f", printing {job['file']}" + (f" ({_g(job.get('progress'))} % done)" if job.get("progress") is not None else "")
    return s + "."


def _printer_send(out):
    return f"{_file(out.get('uploaded'))} uploaded to {out.get('printer')}" + (", and started." if out.get("started") else "; not started (starting it is up to you).")


SENTENCES = {"hw_hole": _hole, "fit": _fit, "setup": _setup, "hw_embed": _embed, "hw_pauses": _pauses, "thread_lookup": _thread,
             "slice": _slice, "slice_with": _slice, "cut_export": _cut, "mill_export": _mill, "printer_status": _printer_status,
             "printer_send": _printer_send}


def sentence(tool, title, out):
    """The Report view's line for a tool's answer: "Workshop: " and a
    sentence with units. A tool with no sentence of its own says it is
    done, never its raw fields."""
    fn = SENTENCES.get(tool)
    if fn is not None:
        try:
            return "Workshop: " + fn(out)
        except Exception:  # noqa: BLE001 — an answer of another shape
            pass
    if tool in SHOWN:
        try:
            return "Workshop: " + SHOWN[tool](out)[2]
        except Exception:  # noqa: BLE001
            pass
    return f"Workshop: {title} done."
