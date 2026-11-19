# SPDX-License-Identifier: LGPL-2.1-or-later
# Print-aware strength: a printed part is weaker across its layers than
# along them, and a print is not its solid body (walls, infill). Added to
# Agent Link's FEM tools (fea_setup, fea_solve) through its hooks
# (extend_tool), so FreeCAD's own FEM control stays Agent Link's and the
# knock-downs are Make's:
#
#   fea_setup { buildDir, printed { project, object } }   recorded on the study
#   fea_solve -> acrossLayers (the tension along the build direction against
#                LAYER_FACTOR x yield), asPrinted (the solid's results scaled
#                by the print's estimated knock-downs, read from an
#                OrcaSlicer project through orcalink.printstrength)
#
# Feasibility only, never a sign-off. Moved from Agent Link's strength
# family on 14 Nov 2026.
import math
import os

from workshop_make import ccx
from workshop_make import records as store

from . import orcalib
from .tooldefs import _agent

# Agent Link's hooks, lent by the family layer (register, from
# agentlink_families): this module never imports Agent Link.
hooks = None

LAYER_FACTOR = 0.5  # across-layer strength taken as this share of the yield
KEY = "fea"  # the study's record (Agent Link's strength family keeps it there)

SETUP_ARGS = {
    "buildDir": {"description": "The build direction of a printed part: +x … -z or [x, y, z] (+z from its print setup)."},
    "printed": {"type": "object", "properties": {"project": {"type": "string"}, "object": {"type": ["string", "integer"]}}, "required": ["project"]},
}
SETUP_SAYS = ("For a printed part: buildDir (+z from its print setup), printed { project, object } (an OrcaSlicer project: its walls, "
              "infill and layers read back and the results given as printed too).")
SOLVE_SAYS = ("For a printed part also the tension across the layers against half the yield (a simplification), and with printed "
              "the safety and displacement as printed.")


def build_dir(v):
    """A build direction as a unit vector [x, y, z]."""
    from workshop_make.refusal import Refused

    if isinstance(v, str):
        m = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
        if v.lower() not in m:
            raise Refused("buildDir: +x, -x, +y, -y, +z, -z or [x, y, z].")
        return list(m[v.lower()])
    if isinstance(v, list) and len(v) == 3:
        n = math.sqrt(sum(float(x) ** 2 for x in v))
        if n > 0:
            return [float(x) / n for x in v]
    raise Refused("buildDir: +x, -x, +y, -y, +z, -z or [x, y, z].")


@_agent
def setup_before(a, s):
    # The study before the owner rewrites it: a kept study keeps its print.
    s._make_prev_study = store.read(s.doc, KEY, None)
    if a.get("buildDir") is not None:
        build_dir(a["buildDir"])
    return None


@_agent
def setup_after(a, out, s):
    from workshop_make.refusal import Refused

    st = store.read(s.doc, KEY, None)
    if not st or not isinstance(out, dict):
        return None
    label = st["body"]
    setup = store.setup_of(s.doc, label, "print")
    build = build_dir(a["buildDir"]) if a.get("buildDir") is not None else (build_dir(setup.get("up", "+z")) if setup else None)
    prev = getattr(s, "_make_prev_study", None) or {}
    keep = prev.get("body") == label and not a.get("reset")
    if a.get("printed"):
        # The slicer's settings read back: what the print falls short of the solid body.
        O3, PS = orcalib.module("orca3mf"), orcalib.module("printstrength")
        pr = a["printed"]
        try:
            path = os.path.expanduser(pr["project"])
            proj = O3.Project(path if os.path.isabs(path) else os.path.join(s.out_dir, pr["project"]))
            po = proj.object(pr.get("object", 1))
        except (KeyError, OSError, ValueError) as e:
            raise Refused(f"printed: {{ project (an OrcaSlicer .3mf), object }} — {e}")
        eff = dict(proj.config)
        eff.update(po.get("settings") or {})
        ft = proj.config.get("filament_type") or []
        if ft:
            eff["filament"] = ft[min(int(po.get("extruder") or 1), len(ft)) - 1]
        d = PS.describe(eff, s.body(label).Shape)
        st["print"] = {"project": pr["project"], "object": po["name"], **{k: d[k] for k in ("shellMm", "solidShare", "stiffnessFactor", "strengthFactor", "layerFactor")},
                       "settings": d["settings"], "advice": d["advice"]}
        if not build:
            build = build_dir((setup or {}).get("up", "+z"))
    elif keep and prev.get("print"):
        st["print"] = prev["print"]
    if build:
        st["buildDir"] = build
    store.write(s.doc, KEY, st)
    out["study"] = st
    if build:
        out["printed"] = f"Built along {build}: the safety across the layers is judged at {(st.get('print') or {}).get('layerFactor', LAYER_FACTOR)}× yield."
    if st.get("print"):
        out["printSettings"] = st["print"]
    return out


def _last(s):
    """The session's last FEA run: Agent Link's (hooks.analysis, lent at
    register) or the one kept on the session."""
    r = None
    if hooks is not None and hasattr(hooks, "analysis"):
        r = hooks.analysis(s, "fea")
    return r if r is not None else getattr(s, "_agentlink_fea", None)


def _this_solve(fea, out):
    """The kept run is the solve that answered out: the same object, or (a
    data tool's answer is a new dict made from it) the same body and peaks."""
    r = fea.get("result")
    if r is out:
        return True
    if not isinstance(r, dict):
        return False
    return (fea.get("body") == out.get("body") and r.get("vonMisesMax") == out.get("vonMisesMax")
            and r.get("displacementMax") == out.get("displacementMax"))


@_agent
def solve_after(a, out, s):
    fea = _last(s)
    if not isinstance(out, dict) or not fea or not _this_solve(fea, out):
        return None
    st = dict(fea.get("study") or {})
    # The study as fea_setup left it (its extension writes buildDir and the
    # print there), where the kept run holds an older copy.
    kept = store.read(s.doc, KEY, None) or {}
    if kept.get("body") in (None, st.get("body")):
        for k in ("buildDir", "print"):
            if st.get(k) is None and kept.get(k) is not None:
                st[k] = kept[k]
    field = fea.get("field") or {}
    bd = st.get("buildDir")
    y = (out.get("material") or {}).get("yield")
    if bd and field.get("stress"):
        sn = [ccx.normal_stress(sv, bd) for sv in field["stress"]]
        i = max(range(len(sn)), key=sn.__getitem__)
        p = field["points"][i]
        where = {"at": [round(p[0], 2), round(p[1], 2), round(p[2], 2)]}
        try:
            import FreeCAD
            import Part

            vx = Part.Vertex(FreeCAD.Vector(*p))
            faces = s.body(st["body"]).Shape.Faces
            best = min(((vx.distToShape(f)[0], k) for k, f in enumerate(faces)), default=(0, 0))
            where["face"] = f"Face{best[1] + 1}"
        except Exception:  # noqa: BLE001 — the body gone since: the point alone
            pass
        lf = (st.get("print") or {}).get("layerFactor", LAYER_FACTOR)
        out["acrossLayers"] = {"tensileMPa": round(max(0.0, sn[i]), 3), **where, "buildDir": bd, "factor": lf}
        if y:
            out["acrossLayers"]["safety"] = round(lf * y / sn[i], 2) if sn[i] > 0 else None
        out["acrossLayers"]["note"] = (f"Printed layers are weaker across than along: the tension along the build direction is judged against {LAYER_FACTOR}× yield. "
                                       "A simplification — the real factor depends on printer, material and settings.")
    smax = (out.get("vonMisesMax") or {}).get("MPa") or 0
    if st.get("print") and y and smax > 0:
        pp = st["print"]
        dmax = (out.get("displacementMax") or {}).get("mm") or 0
        out["asPrinted"] = {"safety": round(pp["strengthFactor"] * y / smax, 2), "displacementMm": round(dmax / pp["stiffnessFactor"], 4),
                            "from": f"{pp['object']} in {os.path.basename(pp['project'])}: shell {pp['shellMm']} mm, solid share {pp['solidShare']}",
                            "note": "Solved on the solid body, scaled by the print's estimated knock-downs: a feasibility check, never a sign-off."}
        if out["asPrinted"]["safety"] < 2 and pp.get("advice"):
            out["asPrinted"]["stronger"] = pp["advice"]
    return out


def register(host_hooks):
    """Print-aware strength on Agent Link's fea_setup and fea_solve; its
    hooks kept for _last. Called by the family layer, which lends them."""
    global hooks
    hooks = host_hooks
    try:
        hooks.extend_tool("fea_setup", SETUP_ARGS, setup_before, setup_after, SETUP_SAYS)
        hooks.extend_tool("fea_solve", {}, None, solve_after, SOLVE_SAYS)
    except TypeError:  # an Agent Link before describe: the arguments without the sentence
        hooks.extend_tool("fea_setup", SETUP_ARGS, setup_before, setup_after)
        hooks.extend_tool("fea_solve", {}, None, solve_after)
