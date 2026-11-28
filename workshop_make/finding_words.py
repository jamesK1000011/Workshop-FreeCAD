# SPDX-License-Identifier: LGPL-2.1-or-later
# A finding as a sentence, for the person: the panel, the Report view, the
# CAM report and the mill sheet. The tools answer findings as records (rule,
# severity, value, limit, unit, at, …); the words are made here, from the
# record and the answer it came in. Not part of any tool's answer.


def _n(v, d=2):
    return f"{float(v):.{d}f}"


def _g(v):
    return f"{float(v):g}"


def _dir(f):
    return f.get("direction", "")


def _thin_wall_print(f, c):
    tail = ("thinner than one line, it can't be printed: thicken it" if f["severity"] == "error"
            else f"under {_g(f['limit'])} mm it prints as a single line: thicken it if it must be strong")
    return f"a wall {_n(f['value'])} mm thick over {f.get('readings')} readings — " + tail


def _overhang(f, c):
    return (f"{f['areaMm2']:.0f} mm² facing down at {f['value']:.0f}° from vertical, past {f['limit']:.0f}°: "
            "support it, chamfer it to 45°, or turn the part")


def _bridge(f, c):
    return (f"a flat ceiling about {f['value']:.1f} mm across, {f['areaMm2']:.0f} mm²: past the {f['limit']:.0f} mm bridge limit — "
            "support it, add a rib, or arch it")


def _print_small_hole(f, c):
    return f"an upright hole Ø{_n(f['value'])} mm, under {f['limit']} mm: it may print closed — drill it after, or make it bigger"


def _bed(f, c):
    return f"{f.get('bedMm2', 0):.0f} mm² on the bed, {100 * f['value']:.0f}% of its footprint: add a brim, or stand it on a flatter face"


def _tall(f, c):
    return f"{f['value']:.1f} times as tall as its base is narrow: it may wobble or snap — widen the base or lay it down"


def _volume(f, c):
    x, y, z = f.get("size", [0, 0, 0])
    vx, vy, vz = f.get("volume", [0, 0, 0])
    return f"{x:.0f} × {y:.0f} × {z:.0f} mm does not fit the {f.get('printer', 'printer')} ({vx} × {vy} × {vz} mm): split it or turn it"


def _check_geometry(f, c):
    return ("FreeCAD's Check Geometry finds the shape broken (" + "; ".join(f.get("problems") or []) + "): a slicer reads it wrongly — rebuild the last step")


# ---- cut ----

def _not_sheet(f, c):
    sh = (c or {}).get("sheet") or {}
    bits = []
    if sh.get("notSquare"):
        bits.append(f"faces not square to the sheet: {', '.join(sh['notSquare'][:12])}")
    if sh.get("steps"):
        bits.append(f"flat faces between the two sides (steps or pockets): {', '.join(sh['steps'][:12])}")
    problem = "; ".join(bits) or "fewer than two parallel flat faces"
    return f"Not a sheet part — {problem}. A sheet is cut straight through: make every side square to the faces, or mill it."


def _thickness(f, c):
    return f"{_n(f['value'])} mm thick, the setup's sheet is {_g(f['limit'])} mm: make the part as thick as the sheet, or set the setup's thickness."


def _cut_small_hole(f, c):
    if f["severity"] == "error":
        m = (c or {}).get("machine")
        why = {"plasma": "under the sheet's thickness, plasma can't cut it clean", "router": "under the cutter's diameter"}.get(m, "too small for the beam to pierce clean")
        return f"A hole {_n(f['value'])} mm across, {why}: drill it after, or make it at least {_n(f['limit'])} mm."
    t = ((c or {}).get("sheet") or {}).get("thickness")
    return (f"A hole {_n(f['value'])} mm across, under {_n(f['limit'])} mm for {(c or {}).get('machine')} in {_g(t) if t is not None else '?'} mm "
            f"{(c or {}).get('material')}: it may come out tapered or not round — make it bigger or drill it.")


def _web(f, c):
    return f"Material {_n(f['value'])} mm wide between two cuts, under {_n(f['limit'])} mm: it can burn through, warp or snap — widen it."


def _slot(f, c):
    if f["severity"] == "error":
        return f"A gap {_n(f['value'])} mm wide, under the cut's own width {_n(f['limit'])} mm: it cannot be cut — widen it."
    return f"A gap {_n(f['value'])} mm wide, under {_n(f['limit'])} mm: the slug may not drop out clean — widen it."


def _cut_corner(f, c):
    r = f["limit"]
    return (f"An inside corner of radius {_n(f['value'])} mm, tighter than the cutter's {_n(r)} mm: it comes out rounded — "
            f"round it to {_n(r)} mm or more, or add a dogbone.")


def _sheet_size(f, c):
    x, y = f.get("size", [0, 0])
    sw, sh = f.get("sheet", [0, 0])
    return f"{x} x {y} mm does not fit the {_g(sw)} x {_g(sh)} mm sheet: split it."


# ---- mill ----

def _undercut(f, c):
    n = f.get("count", 0)
    return (f"{n} face{'s' if n > 1 else ''} no tool direction reaches ({', '.join(f.get('directions') or [])}): an undercut — "
            "add a direction (setup axes \"3+2\"), a second setup, or change the shape.")


def _reach(f, c):
    face = (f.get("faces") or [""])[0]
    return f"{face} is {_n(f['value'], 1)} mm in from {_dir(f)}, past the tool's {_g(f['limit'])} mm reach: a longer tool, or come at it from another side."


def _mill_corner(f, c):
    r = f["limit"]
    return (f"An inside corner of radius {_n(f['value'])} mm along {_dir(f)}, tighter than the least tool's {_n(r)} mm: "
            f"round it to {r * 1.1:.2f} mm or more (a little over the tool's), or EDM it.")


def _mill_small_hole(f, c):
    return f"A hole Ø{_n(f['value'])} mm, under the least end mill's Ø{_g(f['limit'])}: drill or ream it."


def _deep_hole(f, c):
    if f["severity"] == "error":
        return (f"A hole Ø{_n(f['diameter'])} mm {_n(f['value'], 1)} mm deep, past the tool's {_g(f['limit'])} mm reach: "
                "drill it from both sides, or a longer drill.")
    return (f"A hole Ø{_n(f['diameter'])} mm {_n(f['length'], 1)} mm deep, over {_g(f['limit'])} times its width: "
            "a long, thin tool chatters and breaks — drill it, or make it shallower or wider.")


def _deep_pocket(f, c):
    if f["severity"] == "error":
        return f"A pocket {_n(f['value'], 1)} mm deep from {_dir(f)}, past the tool's {_g(f['limit'])} mm reach: a longer tool, or make it shallower."
    return (f"A pocket {_n(f['width'], 1)} mm wide and {_n(f['depth'], 1)} mm deep, over {_g(f['limit'])} times its width: "
            "the tool that fits is too long to cut well — widen it or make it shallower.")


def _mill_wall(f, c):
    return f"A wall {_n(f['value'])} mm thick, under {_g(f['limit'])} mm for the material: it chatters and bends under the tool — thicken it."


def _stock(f, c):
    x, y, z = f.get("size", [0, 0, 0])
    sx, sy, sz = f.get("stock", [0, 0, 0])
    tail = ": it fits turned — turn the stock or the part." if f.get("fitsTurned") else ": bigger stock."
    return f"{x:.1f} x {y:.1f} x {z:.1f} mm does not fit the {_g(sx)} x {_g(sy)} x {_g(sz)} mm stock as it stands" + tail


# ---- part_review ----

def _spec_min_wall(f, c):
    return f"Least wall not waived {_n(f['value'])} mm, under the spec's {f['limit']} mm."


def _spec_mass_max(f, c):
    return f"Weighs {_n(f['value'], 1)} g; the spec asks at most {f['limit']} g."


def _spec_mass_min(f, c):
    return f"Weighs {_n(f['value'], 1)} g; the spec asks at least {f['limit']} g."


def _spec_safety(f, c):
    return f"Safety factor {_n(f['value'])}, under the spec's {f['limit']}."


def _sound(f, c):
    return SOUND_WORDS.get(f.get("problem"), str(f.get("problem")))


SOUND_WORDS = {
    "checkGeometry": "FreeCAD's Check Geometry finds the shape broken: a boolean or loft left it so. Rebuild the last step.",
    "notClosed": "The shape is not closed: it has open edges, so it has no inside to print or weigh.",
    "solids": "More or fewer than one solid where one is meant: pieces that do not touch, or none.",
    "narrowFaces": "Faces under 0.01 mm wide — a sliver two faces a hair apart leave. Overlap the pieces clearly, or carry a cutter on along its slope.",
}

# One table: (source, rule) first, then the rule alone.
RULES = {
    "overhang": _overhang, "bridge": _bridge, "bed-contact": _bed, "tall-thin": _tall,
    "build-volume": _volume, "check-geometry": _check_geometry,
    "not-sheet": _not_sheet, "thickness": _thickness, "thin-web": _web, "narrow-slot": _slot, "sheet-size": _sheet_size,
    "undercut": _undercut, "reach": _reach, "deep-hole": _deep_hole, "deep-pocket": _deep_pocket, "stock": _stock,
    "spec-minWall": _spec_min_wall, "spec-massMax": _spec_mass_max, "spec-massMin": _spec_mass_min, "spec-minSafety": _spec_safety,
    "unsound": _sound,
}
# Rules that two processes share, told apart by the answer.
SHARED = {
    "small-hole": {"print": _print_small_hole, "cut": _cut_small_hole, "mill": _mill_small_hole},
    "inside-corner": {"cut": _cut_corner, "mill": _mill_corner},
    "thin-wall": {"print": _thin_wall_print, "mill": _mill_wall},
}


def process_of(f, ctx=None):
    """print, cut or mill: from the finding's own fields, else the answer's."""
    if f.get("process"):
        return f["process"]
    c = ctx or {}
    if "machine" in c:
        return "cut"
    if "directions" in c and "tool" in c:
        return "mill"
    return "print"


def says(f, ctx=None):
    """The sentence of one finding record; the finding's own "says" when an
    older record carries one."""
    if f.get("says"):
        return str(f["says"])
    rule = f.get("rule")
    if f.get("source") and f["source"] != "dfm_check" and rule is None:
        return str(f.get("what") or "")
    if rule in SHARED:
        fn = SHARED[rule].get(process_of(f, ctx))
    else:
        fn = RULES.get(rule)
    if fn is None:
        return str(rule or "")
    try:
        text = fn(f, ctx or {})
    except Exception:  # noqa: BLE001 — a record with fields missing
        return str(rule)
    return f"{f['finding']} {rule}: {text}" if f.get("finding") else text


def carried_says(n):
    """The sentence of a "carried" note of dfm_check."""
    if n.get("says"):
        return str(n["says"])
    return f"carried by {n.get('by')} after the pause: {n.get('what')} is in the pocket when the layers close over it, so this ceiling is no bridge"


def assumed_says(key, v):
    """One line of an "assumed" record, for a sheet or report."""
    try:
        if key == "axes":
            return "3 (the setup does not say): the tool from +z only"
        if key == "tool" and isinstance(v, (int, float)):
            return f"Ø{float(v):g} mm end mill (the setup's minTool is not set)"
        if key == "reach" and isinstance(v, (int, float)):
            return f"{float(v):g} mm, five times the tool or 20 mm (a standard length)"
        if key == "material" and isinstance(v, str):
            return f"{v} (not said)"
        if key == "stock" and isinstance(v, (list, tuple)):
            return f"{v[0]:g} x {v[1]:g} x {v[2]:g} mm: the part's box and 2 mm a side, 1 mm top and bottom"
    except Exception:  # noqa: BLE001
        pass
    return str(v)
