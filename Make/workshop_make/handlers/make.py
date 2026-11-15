# SPDX-License-Identifier: LGPL-2.1-or-later
# The handlers for the make loop: setup, part_spec, dfm_check, part_review
# and slice — how each part is made, the limits it must meet, the
# printability check, the verdict, and slicing with PrusaSlicer. A thin
# layer over workshop_make.api. Moved from Agent Link's tools.py on 14 Nov
# 2026.

import math
import os

from workshop_make.refusal import Refused
from workshop_make import geo
from workshop_make import materials as fil
from workshop_make import records as store

from .. import api, orcalib, printability, printmass
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal
matfam = None
hooks = None


def card(session, label, given=None):
    """The body's material: (id, density g/cm³, filament word or None,
    name) — from Agent Link's material family (FreeCAD's library and custom
    materials) when it has one, else the filaments."""
    mid = given or store.materials(session.doc).get(label) or "pla"
    c = None
    if matfam is not None:
        c = matfam.card(session.doc, mid)
    key = str(mid).lower()
    if c is None and key in fil.DENSITY:
        c = fil.card(key)
    if not c or not c.get("density"):
        raise ToolError("invalid_input", f"material {mid!r}: not known, or without a density — material_list finds one, material_set gives a body its own.")
    filament = key.split("-")[0] if key in fil.DENSITY else None
    return mid, float(c["density"]), filament, c.get("name", str(mid))


def encased(session, label):
    """Everything dropped into the part mid-print: each with its mass (g)
    and the height to pause at — the magnets gen_make records, the ballast
    mass_ballast cuts, and the parts hw_embed seals in. Heights from the
    part's lowest point, as it stands on the bed."""
    m = session.meta.get(label) or {}
    try:
        z0 = session.body(label).Shape.BoundBox.ZMin
    except ToolError:
        z0 = 0.0
    out = []
    mags = m.get("encased")
    if mags:
        out.append({"what": f"{mags['count']} {mags['what']}", "mass": mags["count"] * math.pi * 3.0 ** 2 * api.MAGNET_T_MM * api.NDFEB / 1000.0, "pauseAt": mags["top"] - z0})
    b = m.get("ballast")
    if b and b.get("pockets"):
        top = max(p["at"][2] + p["depth"] for p in b["pockets"])
        out.append({"what": f"{b['what']} ballast in {len(b['pockets'])} pockets", "mass": sum(p.get("fill", 0) for p in b["pockets"]), "pauseAt": top - z0})
    for e in m.get("embeds") or []:
        if isinstance(e, dict) and ("pauseZ" in e or "pauseAt" in e):
            out.append({"what": e.get("what", "a part"), "mass": float(e.get("mass", 0) or 0), "pauseAt": e.get("pauseZ", e.get("pauseAt"))})
    return out


def last_fea(session):
    """The last FEA solve, through Agent Link's hooks (analysis "fea")."""
    r = hooks.analysis(session, "fea") if hooks is not None else None
    return r if r is not None else getattr(session, "_agentlink_fea", None)


def refused(fn):
    def run(s, a):
        try:
            return fn(s, a)
        except Refused as e:
            raise ToolError(e.code, e.message)
    return run


@refused
def setup(s, a):
    act = a.get("action", "list")
    if act == "list":
        return {"setups": store.setups(s.doc), "types": api.setup_types()}
    if act == "of":
        o = s.body(a.get("body"))
        st = store.setup_of(s.doc, o.Label)
        return {"body": o.Label, "setup": st} if st else {"body": o.Label, "setup": None, "none": "in no setup: how it is made is not recorded — ask, then setup add"}
    if act == "add":
        if a.get("type") not in store.TYPES:
            raise ToolError("invalid_input", f"type: one of {', '.join(store.TYPES)}.")
        bodies = [s.body(b).Label for b in (a.get("bodies") or [])]
        st = api.setup_add(s.doc, a.get("type"), bodies, a.get("settings") or {}, a.get("name"))
        return {"added": st, "setups": len(store.setups(s.doc))}
    if act == "remove":
        return {"removed": api.setup_remove(s.doc, a.get("id"))}
    if act == "set":
        st = api.setup_set(s.doc, a.get("id"),
                           bodies=[s.body(b).Label for b in a["bodies"]] if "bodies" in a else None,
                           add=[s.body(b).Label for b in a.get("add") or []], remove=a.get("remove") or [],
                           settings=a.get("settings"), name=a.get("name"))
        return {"setup": st}
    api.setup_find(s.doc, a.get("id")) if a.get("id") else None
    raise ToolError("invalid_input", "action: list, of, add, set or remove.")


@refused
def part_spec(s, a):
    spec = api.spec_set(s.doc, a.get("spec"), bool(a.get("clear")))
    mats = store.materials(s.doc)
    if a.get("material"):
        mats = api.material_set(s.doc, [s.body(b).Label for b in (a.get("bodies") or [s.body(None).Label])], a["material"])
    elif a.get("material") == "":
        mats = api.material_clear(s.doc, [s.body(b).Label for b in (a.get("bodies") or [s.body(None).Label])])
    return {"spec": spec, "materials": mats}


@refused
def dfm_check(s, a):
    o = s.body(a.get("body"))
    last = getattr(s, "_last_dfm", {})
    out = api.dfm(s.doc, o, a.get("waive"), last.get(o.Label, []))
    last[o.Label] = out["findings"]
    s._last_dfm = last
    return out


def part_review(s, a):
    o = s.body(a.get("body"))
    spec = {**store.spec(s.doc), **(a.get("spec") or {})}
    material, rho, _, _ = card(s, o.Label, a.get("material"))
    shape = o.Shape
    findings, checks, unjudged, informed = [], {}, [], []

    def find(into, source, severity, says, at=None):
        into.append({"source": source, "severity": severity, "says": says, **({"at": at} if at else {})})

    snd = geo.soundness(shape)
    checks["body_check"] = "ran"
    for p in snd["problems"]:
        find(findings, "body_check", "error", p)

    setup = store.setup_of(s.doc, o.Label)
    printed = bool(setup and setup["type"] == "print")
    # Waivers given here are kept, as dfm_check's are.
    if a.get("waive"):
        ws = store.waivers(s.doc)
        for x in a["waive"]:
            ws.append({"body": o.Label, "rule": x.get("rule", "thin-wall"), "at": x.get("at"), "reason": x.get("reason", "waived")})
        store.write(s.doc, "waivers", ws)
    rules, _ = api.rules_of(s.doc, o.Label)
    dfm = printability.check(shape, rules, [x for x in store.waivers(s.doc) if x.get("body") == o.Label])
    checks["dfm_check"] = "ran" if printed or not setup else "skipped: not printed"
    into = findings if printed else informed
    if printed or not setup:
        for f in dfm["findings"]:
            if not f.get("waived"):
                find(into, "dfm_check", f["severity"], f"{f['id']} {f['rule']}: {f['says']}", f["at"])
    least = dfm["wall"]["least"]
    if "minWall" in spec:
        open_thin = [f["value"] for f in dfm["findings"] if f["rule"] == "thin-wall" and not f.get("waived")]
        judged = min(open_thin) if open_thin else (least if least is not None and least >= spec["minWall"] else None)
        if least is None:
            unjudged.append("minWall: no wall reading")
        elif judged is not None and judged < spec["minWall"]:
            find(findings, "dfm_check", "error", f"Least wall not waived {judged:.2f} mm, under the spec's {spec['minWall']} mm.")
        elif judged is None and spec["minWall"] > rules["minWall"]:
            unjudged.append(f"minWall: the least wall is waived, and the check reads walls only under {rules['minWall']} mm")

    vol = shape.Volume
    walls = int((setup or {}).get("walls", 2))
    infill = float((setup or {}).get("infill", 15)) / 100
    if printed:
        # Sectioned as a slicer lays it down (printmass.sliced):
        # perimeters, top and bottom skins and sparse infill per layer.
        lh = float((setup or {}).get("layerHeight", 0.2))
        tops = int((setup or {}).get("topLayers", 5))
        bottoms = int((setup or {}).get("bottomLayers", 4))
        share, found = printmass.solid_of(shape, setup, walls)
        f = 1.0 if share is None else share + infill * (1 - share)
        body_g = vol * f * rho / 1000.0
        as_ = f"printed: {walls} walls, {tops} top and {bottoms} bottom layers of {lh} mm, {infill * 100:.0f}% infill — {f * 100:.0f}% of the solid, from {found or 'nothing read: taken as solid'} (an estimate; the slicer's figure is the authority)"
    else:
        body_g = vol * rho / 1000.0
        as_ = "solid"
    mags = encased(s, o.Label)
    mag_g = sum(e["mass"] for e in mags)
    mass = body_g + mag_g
    checks["mass"] = "ran"
    if "massMax" in spec and mass > spec["massMax"]:
        find(findings, "mass", "error", f"Weighs {mass:.1f} g; the spec asks at most {spec['massMax']} g.")
    if "massMin" in spec and mass < spec["massMin"]:
        find(findings, "mass", "error", f"Weighs {mass:.1f} g; the spec asks at least {spec['massMin']} g.")
    sfl = None
    fea = last_fea(s)
    fea_ok = bool(fea and fea.get("body") == o.Label and fea.get("stats") == geo.stats(shape) and fea.get("result"))
    if fea_ok:
        r = fea["result"]
        sf = r.get("safety")
        across = (r.get("acrossLayers") or {}).get("safety")
        sfl = min(x for x in (sf, across) if x is not None) if (sf is not None or across is not None) else None
        checks["fea_results"] = "ran"
        if sfl is not None and "minSafety" in spec and sfl < spec["minSafety"]:
            find(findings, "fea_results", "error", f"Safety factor {sfl:.2f}, under the spec's {spec['minSafety']}.")
    elif fea and fea.get("body") == o.Label:
        checks["fea_results"] = "skipped: stale — the body changed since the solve; fea_solve again"
    else:
        checks["fea_results"] = "skipped: nothing solved"
    if "minSafety" in spec and not fea_ok:
        unjudged.append("minSafety: " + checks["fea_results"].replace("skipped: ", ""))
    order = {"error": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: order[f["severity"]])
    verdict = "fix" if any(f["severity"] == "error" for f in findings) else ("unknown" if unjudged else "pass")
    out = {
        "body": o.Label,
        "process": "printed" if printed else (setup["type"] if setup else "unknown"),
        "processFrom": f"setup {setup['name']} ({setup['id']})" if setup else "not said — setup add records it",
        "verdict": verdict,
        "findings": findings[:8],
        "figures": {"volume": round(vol, 1), "mass": round(mass, 1), "material": material, "as": as_, **({"encasedMass": round(mag_g, 1)} if mags else {}),
                    **({"safety": sfl} if fea_ok and sfl is not None else {}), **({"wall": least} if least is not None else {})},
        "checks": checks,
        "spec": spec,
    }
    if informed:
        out["ifPrinted"] = informed[:5]
    if unjudged:
        out["unjudged"] = unjudged
    if mags and printed:
        lh = float(setup.get("layerHeight", 0.2))
        pauses = {}
        for e in mags:
            layer = int(math.ceil(e["pauseAt"] / lh - 1e-9))
            p = pauses.setdefault(layer, {"z": round(layer * lh, 3), "afterLayer": layer, "note": []})
            p["note"].append(e["what"])
        out["printing"] = {"pauses": [{**p, "note": "Insert " + "; ".join(p["note"])} for _, p in sorted(pauses.items())]}
    return out


def other_tool(s, name):
    server = getattr(s, "server", None)
    t = server.tools.get(name) if server is not None else None
    return t.fn if t is not None else None


def slice(s, a):
    o = s.body(a.get("body"))
    setup = store.setup_of(s.doc, o.Label, "print")
    if not setup:
        raise ToolError("invalid_state", f"{o.Label} is in no print setup: slicing prints it — setup add {{ type: \"print\", bodies: [\"{o.Label}\"] }} once the person says it is printed.")
    chosen = setup.get("slicerPresets")
    slice_with = other_tool(s, "slice_with")
    if chosen and not a.get("settings") and slice_with is not None:
        # The person's own presets chosen: their slicer slices it.
        want = chosen.get("slicer")
        if chosen.get("bundle"):
            try:
                want = orcalib.module("presets").load_saved(s.out_dir, chosen["bundle"])["slicer"]
            except Refused:
                raise
            except Exception as e:  # noqa: BLE001 — PresetError: the bundle cannot be read
                raise ToolError("invalid_state", f"The setup's presets cannot be read: {e}")
        return slice_with({k: v for k, v in {**a, "slicer": want}.items() if k in ("body", "slicer", "pauseCommand", "name")})
    settings = {**setup, **(a.get("settings") or {})}
    mat, rho, filament, name = card(s, o.Label)
    if filament is None:
        raise ToolError("invalid_state", f"{o.Label} is in {name}, not a printing filament: material_set a filament ({', '.join(fil.DENSITY)}) before slicing.")
    settings["filament"] = filament
    settings["density"] = rho
    import Mesh  # noqa: F401
    import MeshPart

    base = os.path.join(s.out_dir, a.get("name") or o.Label.replace(" ", "_"))
    stl, gcode = base + ".stl", base + ".gcode"
    MeshPart.meshFromShape(Shape=o.Shape, LinearDeflection=0.01, AngularDeflection=0.0873, Relative=False).write(stl)
    slicer = orcalib.module("prusa")
    try:
        exe = slicer.slice_stl(stl, gcode, settings)
    except FileNotFoundError as e:
        # No PrusaSlicer: the slicer the person has, by slice_with.
        if slice_with is None:
            raise ToolError("unavailable", f"{e}")
        other = next((n for n, here in orcalib.module("cli").present().items() if here and n != "prusaslicer"), None)
        if not other:
            raise ToolError("unavailable", f"{e} OrcaSlicer and Bambu Studio are not here either.")
        out = slice_with({k: v for k, v in {**a, "slicer": other}.items() if k in ("body", "slicer", "pauseCommand", "name", "profiles")})
        out["note"] = f"PrusaSlicer is not on this computer: sliced with {other} (slice_with). " + out.get("note", "")
        return out
    except RuntimeError as e:
        raise ToolError("failed", str(e))
    read = slicer.read_gcode(gcode)
    mags = encased(s, o.Label)
    pauses = []
    if mags:
        pauses = slicer.insert_pauses(gcode, [{"z": e["pauseAt"], "note": f"Insert {e['what']}"} for e in mags], a.get("pauseCommand", "M601"))
    return {
        "body": o.Label,
        "slicer": os.path.basename(exe),
        "gcode": gcode,
        "bytes": os.path.getsize(gcode),
        **read,
        "setup": f"{setup['name']} ({setup['id']})",
        **({"pauses": pauses} if mags else {}),
        "note": "Sliced with the slicer's own defaults for anything the setup leaves unset; the printer's profile in the slicer is the authority. Starting the print is the person's.",
    }


HANDLERS = {
    "setup": setup,
    "part_spec": part_spec,
    "dfm_check": dfm_check,
    "part_review": part_review,
    "slice": slice,
}
