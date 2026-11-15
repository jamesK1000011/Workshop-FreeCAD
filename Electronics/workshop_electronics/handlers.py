# SPDX-License-Identifier: LGPL-2.1-or-later
# Electronics' tool handlers: {tool_name: fn(ctx, args)} for kicad_import,
# board_enclosure, pcb_order_package and printed_channel, over this
# package's api modules. ctx is the session the call runs in (Agent Link's,
# or the add-on's own runner's). No Agent Link import here: the family
# layer (fam_electronics.py, loaded by Agent Link only) binds them with
# bound(), and this is the one place an answer is shaped. The definitions
# are data (data/tools.json). Moved from Agent Link for FreeCAD on 14 Nov
# 2026.

import functools
import json
import math
import os
import re
import shutil
import subprocess
import tempfile

import FreeCAD
import Part

from workshop_electronics.refusal import Refused
from workshop_electronics import geo
from workshop_electronics import records as store

from . import board as B
from . import enclosure as boxes
from . import kicad, pcb


V = FreeCAD.Vector


def calibration(doc):
    """The printer's fit calibration kept with the document (the "fit"
    record, docs/records.md in Agent Link), else the typical printer's:
    holes print 0.2 mm small. Gives (calibration, how it was found)."""
    c = store.read(doc, "fit", None) if doc is not None else None
    if c:
        return {"hole": float(c.get("hole", 0.2)), "shaft": float(c.get("shaft", 0.0))}, "calibrated"
    return {"hole": 0.2, "shaft": 0.0}, "none — the typical printer assumed (holes print 0.2 mm small)"


def add_bodies(session, made, base_name=None, placement=None):
    """Each shape as its own body; the labels given back."""
    labels = []
    for i, (name, shape) in enumerate(made):
        label = session.unique(base_name + ("" if i == 0 else " lid") if base_name else name)
        o = session.doc.addObject("Part::Feature", "Body")
        o.Label = label
        if placement is not None:
            shape = shape.copy()
            shape.translate(placement)
        o.Shape = shape
        labels.append(label)
    session.doc.recompute()
    return labels


def boards(s):
    return store.read(s.doc, "boards", {})


# ---- kicad_import ----------------------------------------------------------------------

def kicad_import(s, a):
    path = a.get("path")
    if not path or not os.path.isfile(path):
        raise Refused(code="not_found", message=f"path: {path!r} is not a file — the .kicad_pcb's full path.")
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    b = kicad.read_board(text, path)
    heights = a.get("heights") or {}
    min_h = float(a.get("minHeight", 3.0))
    x0, y0, x1, y1 = b["outline"]["box"]
    off = (-(x0 + x1) / 2, -(y0 + y1) / 2) if a.get("centre", True) else (0.0, 0.0)
    shape = B.board_shape(b)
    name = a.get("name") or os.path.splitext(os.path.basename(path))[0]
    made = [(f"PCB {name}", shape)]
    tall, unknown = [], []
    t = b["thickness"]
    for fp in b["footprints"]:
        c = fp["courtyard"]
        if not c or "mountinghole" in fp["footprint"].lower():
            continue
        h, src = None, None
        if fp["ref"] in heights:
            h, src = float(heights[fp["ref"]]), "given"
        elif fp["model"]:
            h = B._model_height(fp["model"]["path"], fp["model"]["scale"][2], os.path.dirname(path))
            src = "3D model" if h else None
        if h is None and fp["height"]:
            h, src = fp["height"], "Height property"
        fp["heightFrom"] = src
        if h is None:
            unknown.append(fp["ref"])
            continue
        fp["height"] = round(h, 3)
        if h < min_h:
            continue
        w, d = c[2] - c[0], c[3] - c[1]
        if w < 0.2 or d < 0.2:
            continue
        z = t if fp["side"] == "top" else -h
        made.append((f"{fp['ref']} {fp['value']}".strip(), Part.makeBox(w, d, h, V(c[0], c[1], z))))
        tall.append({"ref": fp["ref"], "value": fp["value"], "side": fp["side"], "height": round(h, 2), "from": src})
    labels = add_bodies(s, made, placement=V(off[0], off[1], 0))
    info = {
        "file": b["source"],
        "thickness": t,
        "copperLayers": b["copperLayers"],
        "size": b["size"],
        "box": [round(x0 + off[0], 3), round(y0 + off[1], 3), round(x1 + off[0], 3), round(y1 + off[1], 3)],
        "holes": [{"at": [round(h["at"][0] + off[0], 3), round(h["at"][1] + off[1], 3)], "d": h["d"], "kind": h["kind"]} for h in b["holes"]],
        "footprints": [
            {"ref": f["ref"], "value": f["value"], "side": f["side"], "courtyard": [round(f["courtyard"][0] + off[0], 3), round(f["courtyard"][1] + off[1], 3), round(f["courtyard"][2] + off[0], 3), round(f["courtyard"][3] + off[1], 3)] if f["courtyard"] else None, "height": f["height"]}
            for f in b["footprints"]
        ],
        "edge": kicad.edge_connectors(b),
        "path": os.path.abspath(path),
        "components": labels[1:],
    }
    all_ = boards(s)
    all_[labels[0]] = info
    store.write(s.doc, "boards", all_)
    s.meta[labels[0]] = {"generator": "kicad_import"}
    s.snapshot("kicad_import")
    out = {
        "board": labels[0],
        "size": b["size"],
        "thickness": t,
        "copperLayers": b["copperLayers"],
        "holes": info["holes"],
        "footprints": len(b["footprints"]),
        "tall": tall,
        "edgeConnectors": info["edge"],
        "bodies": labels,
        "step": len(s.steps),
    }
    if unknown:
        out["noHeight"] = {"count": len(unknown), "refs": unknown[:20], "note": "No height for these: no STEP model here, no Height property. heights { ref: mm } gives them."}
    if b["outline"]["open"]:
        out["openOutline"] = f"{b['outline']['open']} piece(s) of Edge.Cuts join nothing and were left out."
    if a.get("centre", True):
        out["moved"] = [round(off[0], 3), round(off[1], 3)]
    return out


# ---- board_enclosure -------------------------------------------------------------------

def board_enclosure(s, a):
    all_ = boards(s)
    if not all_:
        raise Refused(code="invalid_state", message="No board imported: kicad_import reads one first (or gen_part board_box takes the sizes by hand).")
    ref = a.get("board")
    if ref is None:
        if len(all_) > 1:
            raise Refused(code="invalid_input", message=f"board: say which — {', '.join(all_)}.")
        ref = next(iter(all_))
    if ref not in all_:
        raise Refused(code="not_found", message=f"board {ref!r}: the boards imported are {', '.join(all_)}.")
    b = all_[ref]
    x0, y0, x1, y1 = b["box"]
    top = [f for f in b["footprints"] if f["side"] == "top" and f.get("height")]
    under = [f for f in b["footprints"] if f["side"] == "bottom" and f.get("height")]
    params = {k: a[k] for k in ("wall", "floor", "radius", "lid", "lip", "clearance", "gap", "margin") if k in a}
    params["board"] = [x1 - x0, y1 - y0]
    params["thickness"] = b["thickness"]
    # Standoffs under the mounting holes; other unplated holes (a
    # connector's pegs, say) only when the board has no mounting hole.
    holes = [h for h in b["holes"] if h.get("kind") == "mounting"] or b["holes"]
    params["holes"] = [[h["at"][0] - x0, h["at"][1] - y0] for h in holes]
    if holes:
        params["screw"] = a.get("screw") or kicad.screw_for(min(h["d"] for h in holes))
    params["standoff"] = a.get("standoff") or max(5.0, max((f["height"] for f in under), default=0) + 1.0)
    params["headroom"] = a.get("headroom") or max(5.0, max((f["height"] for f in top), default=0) + 2.0)
    openings, guessed = [], []
    skip = set(a.get("skip") or [])
    for e in b["edge"]:
        if e["ref"] in skip:
            continue
        fp = next((f for f in b["footprints"] if f["ref"] == e["ref"]), None)
        h = (fp or {}).get("height")
        if not h:
            h = B.GUESS_H
            guessed.append(e["ref"])
        lo, hi = max(e["from"], 0.0), min(e["to"], (x1 - x0) if e["side"] in ("front", "back") else (y1 - y0))
        if hi - lo < 0.5:
            continue
        openings.append({"side": e["side"], "at": (lo + hi) / 2, "width": hi - lo, "height": h, "z": 0, "ref": e["ref"]})
    for o in a.get("openings") or []:
        openings.append(o)
    params["openings"] = [{k: v for k, v in o.items() if k != "ref"} for o in openings]
    cal, said = calibration(s.doc)
    p = boxes.check(boxes.BOARD_BOX, params)
    box, lid, info = boxes.board_box(p, cal)
    # Moved so the board's seat in the box is where the imported board is.
    bx, by, bz = info["boardAt"]
    shift = V(x0 - bx, y0 - by, -bz)
    base = a.get("name") or f"{ref} enclosure"
    labels = add_bodies(s, [(base, box), (base + " lid", lid)], placement=shift)
    s.snapshot("board_enclosure")
    out = {
        "board": ref,
        "bodies": labels,
        "outside": info["outside"],
        "standoff": p["standoff"],
        "headroom": p["headroom"],
        **({"standoffs": info["standoffs"]} if "standoffs" in info else {}),
        "openings": [{**o, "for": openings[i].get("ref", "given")} for i, o in enumerate(info.get("openings", []))],
        "printerFit": said,
        "sound": {lb: geo.soundness(sh)["ok"] for lb, sh in zip(labels, (box, lid))},
        "step": len(s.steps),
    }
    if guessed:
        out["openingHeightGuessed"] = {"refs": guessed, "mm": B.GUESS_H, "note": "No height known for these connectors: give it as heights in kicad_import, or openings by hand."}
    return out


# ---- pcb_order_package -----------------------------------------------------------------

def pcb_order_package(s, a):
    files = a.get("files") or []
    missing = [p for p in files if not os.path.isfile(p)]
    if missing:
        raise Refused(code="not_found", message=f"files: {missing[0]} is not a file — give each file's full path (KiCad's File › Fabrication Outputs writes them).")
    vendor = a.get("vendor", "jlcpcb")
    if vendor not in pcb.vendors():
        raise Refused(code="invalid_input", message=f"vendor: one of {', '.join(pcb.vendors())}.")
    sorted_ = pcb.classify(files)
    if not sorted_["gerbers"]:
        raise Refused(code="invalid_input", message="files: no Gerber among them (.gbr, .gtl, .gbl …) — plot them from KiCad first.")
    board = {"name": a.get("name"), "thickness": a.get("thickness", 1.6), "layers": a.get("layers"), "size": a.get("size")}
    ref = a.get("board")
    if ref:
        bi = boards(s).get(ref)
        if not bi:
            raise Refused(code="not_found", message=f"board {ref!r}: the boards imported are {', '.join(boards(s)) or 'none'}.")
        board.update({"name": board["name"] or ref, "thickness": bi["thickness"], "layers": bi["copperLayers"], "size": bi["size"]})
    warnings = []
    outline = [p for p in sorted_["gerbers"] if pcb.is_outline(p)]
    if not outline:
        warnings.append("No board outline Gerber (Edge_Cuts, .gko, .gm1): the board house cannot cut the board without it.")
    if not board["size"] and outline:
        with open(outline[0], encoding="ascii", errors="replace") as f:
            bx = pcb.gerber_box(f.read())
        if bx:
            board["size"] = [round(bx[2] - bx[0], 3), round(bx[3] - bx[1], 3)]
    if not board["layers"]:
        board["layers"] = sum(1 for p in sorted_["gerbers"] if pcb.is_copper(p)) or None
    if not sorted_["drill"]:
        warnings.append("No drill file (.drl): a board with holes needs it.")
    if (sorted_["bom"] or sorted_["cpl"]) and not (sorted_["bom"] and sorted_["cpl"]):
        warnings.append("Assembly needs both a BOM and a placement (CPL) file; one is here.")
    drc, drc_out = None, None
    pcb_file = a.get("kicadPcb") or ((boards(s).get(ref) or {}).get("path") if ref else None)
    cli = shutil.which("kicad-cli")
    if pcb_file and cli and os.path.isfile(pcb_file):
        rep = os.path.join(tempfile.mkdtemp(), "drc.json")
        try:
            subprocess.run([cli, "pcb", "drc", "--format", "json", "--output", rep, pcb_file], capture_output=True, timeout=180, check=False)
            with open(rep, encoding="utf-8") as f:
                r = json.load(f)
            errs = [v for v in r.get("violations", []) if v.get("severity") == "error"]
            warns = [v for v in r.get("violations", []) if v.get("severity") != "error"]
            unc = len(r.get("unconnected_items", []))
            drc_out = {"errors": len(errs), "warnings": len(warns), "unconnected": unc, "first": [v.get("description") for v in errs[:5]]}
            drc = f"kicad-cli DRC: {len(errs)} error(s), {len(warns)} warning(s), {unc} unconnected." + (" Fix the errors before ordering." if errs or unc else "")
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            drc = f"kicad-cli DRC did not run through: {e}. Run it in KiCad before ordering."
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", board["name"] or "board")
    gz = os.path.join(s.out_dir, f"{name}_gerbers.zip")
    pcb.write_zip(gz, [(os.path.basename(p), p) for p in sorted_["gerbers"] + sorted_["drill"]])
    sheet = pcb.order_sheet(vendor, board, sorted_, a.get("quantity"), drc)
    entries = [(os.path.basename(gz), gz), ("ORDER.md", sheet.encode("utf-8"))]
    entries += [("assembly/" + os.path.basename(p), p) for p in sorted_["bom"] + sorted_["cpl"]]
    entries += [("other/" + os.path.basename(p), p) for p in sorted_["other"]]
    oz = os.path.join(s.out_dir, f"{name}_order.zip")
    pcb.write_zip(oz, entries)
    with open(os.path.join(s.out_dir, f"{name}_ORDER.md"), "w", encoding="utf-8") as f:
        f.write(sheet)
    out = {
        "gerberZip": gz,
        "package": oz,
        "orderSheet": os.path.join(s.out_dir, f"{name}_ORDER.md"),
        "vendor": pcb.vendors()[vendor]["name"],
        "board": {k: board[k] for k in ("size", "layers", "thickness")},
        "files": {k: len(v) for k, v in sorted_.items()},
        "drc": drc_out if drc_out else ("not run: kicad-cli is not on this computer's PATH" if not cli else ("not run: kicadPcb (the .kicad_pcb) not given" if not pcb_file else drc)),
        "note": "Uploading and paying are the person's to do.",
    }
    if warnings:
        out["warnings"] = warnings
    return out


# ---- printed_channel -------------------------------------------------------------------

def printed_channel(s, a):
    o = s.body(a.get("body"))
    path = a.get("path")
    if not (isinstance(path, list) and len(path) >= 2 and all(isinstance(p, list) and len(p) == 3 for p in path)):
        raise Refused(code="invalid_input", message="path: [[x, y, z], …], two points or more, mm — where the channel runs, ends on the part's faces to open there.")
    sec = a.get("section") or {}
    shape_kind = sec.get("shape", "round")
    size = float(sec.get("size", 2.0))
    if shape_kind not in ("round", "square") or not (0.4 <= size <= 20):
        raise Refused(code="invalid_input", message="section: { shape: round|square, size: 0.4 to 20 mm (the diameter or side) }.")
    fill = a.get("fill", "wire")
    if fill not in ("wire", "filament", "paint"):
        raise Refused(code="invalid_input", message="fill: wire (threaded through), filament (printed full of conductive filament: a trace) or paint (conductive paint pushed in).")
    cal, said = calibration(s.doc)
    pts = [V(*p) for p in path]
    for i in range(1, len(pts)):
        if (pts[i] - pts[i - 1]).Length < size:
            raise Refused(code="invalid_input", message=f"path.{i}: {(pts[i] - pts[i - 1]).Length:.2f} mm from the point before — at least the section's size ({size} mm).")
    shp = o.Shape
    # An end on the surface is carried on 1 mm past it, so the channel
    # opens cleanly instead of ending on the face.
    skin = Part.makeCompound(shp.Faces)

    def on_surface(p):
        return skin.distToShape(Part.Vertex(p))[0] < 0.05

    ends = []
    for i, j in ((0, 1), (len(pts) - 1, len(pts) - 2)):
        outside = not shp.isInside(pts[i], 0.01, True)
        surf = on_surface(pts[i])
        ends.append("open" if outside or surf else "blind")
        if surf:
            d = pts[i] - pts[j]
            d.normalize()
            pts[i] = pts[i] + d * 1.0
    bend = float(a.get("bend") or max(size, 2.0))
    edges, length = [], 0.0
    cur = pts[0]
    for i in range(1, len(pts) - 1):
        a_, b_, c_ = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = b_ - a_, c_ - b_
        d1.normalize()
        d2.normalize()
        ang = math.acos(max(-1.0, min(1.0, d1.dot(d2))))
        if ang < 1e-3:
            continue
        if ang > math.radians(170):
            raise Refused(code="invalid_input", message=f"path.{i}: the path turns back on itself there.")
        t = min(bend * math.tan(ang / 2), (b_ - a_).Length * 0.45, (c_ - b_).Length * 0.45)
        p1, p2 = b_ - d1 * t, b_ + d2 * t
        r = t / math.tan(ang / 2)
        bis = (d2 - d1)
        bis.normalize()
        mid = b_ + bis * (r / math.cos(ang / 2) - r)
        if (p1 - cur).Length > 1e-6:
            edges.append(Part.LineSegment(cur, p1).toShape())
        edges.append(Part.Arc(p1, mid, p2).toShape())
        cur = p2
    edges.append(Part.LineSegment(cur, pts[-1]).toShape())
    spine = Part.Wire(edges)
    d0 = pts[1] - pts[0]
    d0.normalize()
    if shape_kind == "round":
        prof = Part.Wire(Part.makeCircle(size / 2 + (cal["hole"] / 2 if fill == "wire" else 0), pts[0], d0))
    else:
        up = V(0, 0, 1) if abs(d0.z) < 0.9 else V(1, 0, 0)
        u = d0.cross(up)
        u.normalize()
        w = d0.cross(u)
        h = size / 2
        q = [pts[0] + u * x + w * y for (x, y) in ((-h, -h), (h, -h), (h, h), (-h, h))]
        prof = Part.makePolygon(q + [q[0]])
    try:
        sweep = Part.Wire(spine).makePipeShell([prof], True, False, 2)
    except Exception as e:
        raise Refused(code="failed", message=f"The channel could not be swept along the path ({e}): fewer, longer segments, or a larger bend.")
    if not sweep.isValid() or sweep.Volume <= 0:
        raise Refused(code="failed", message="The channel came out broken: a larger bend radius, or points further apart.")
    before = shp.Volume
    cut = geo.cut_all(shp, [sweep])
    removed = before - cut.Volume
    if removed < 1e-3:
        raise Refused(code="failed", message="The channel cut nothing: the path runs outside the part — put its points inside the body.")
    sound = geo.soundness(cut)
    if not sound["ok"]:
        raise Refused(code="failed", message="The channel leaves the part unsound: " + "; ".join(sound["problems"]) + " Move the path a little off the faces it grazes.")
    o.Shape = cut
    labels = [o.Label]
    if fill == "filament" and a.get("trace", True):
        trace = geo.clean(sweep.common(shp))
        labels += add_bodies(s, [(f"{o.Label} trace", trace)])
    s.doc.recompute()
    s.snapshot("printed_channel")
    length = spine.Length
    area_mm2 = math.pi * (size / 2) ** 2 if shape_kind == "round" else size * size
    out = {
        "body": o.Label,
        "bodies": labels,
        "length": round(length, 2),
        "section": {"shape": shape_kind, "size": size, "areaMm2": round(area_mm2, 3)},
        "ends": ends,
        "bend": bend,
        "removed": round(removed, 2),
        "sound": True,
        "step": len(s.steps),
    }
    cond = {}
    if fill in ("filament", "paint"):
        mat = a.get("material", "carbon-pla")
        rho = a.get("resistivity") or B.RESISTIVITY.get(mat)
        if rho:
            ohm = float(rho) * (length / 10.0) / (area_mm2 / 100.0)
            cond = {"fill": fill, "resistivityOhmCm": rho, "ohms": round(ohm, 3 if ohm < 10 else 1), "note": "R = ρ·L/A on the channel's section; printed traces read higher across layers (several times, up the Z axis). Typical figures; the filament's sheet is the authority."}
        else:
            cond = {"fill": fill, "ohms": None, "note": f"resistivity (Ω·cm) not known for {mat!r}: give resistivity, or material: {', '.join(B.RESISTIVITY)}."}
    awg = a.get("awg")
    if fill == "wire" or awg:
        n = int(awg or 22)
        if not (10 <= n <= 40):
            raise Refused(code="invalid_input", message="awg: 10 to 40.")
        dw = B.awg_mm(n)
        ohm = B.CU * (length / 10.0) / (math.pi * (dw / 20.0) ** 2)
        need = dw + 0.4 + cal["hole"]
        cond["wire"] = {"awg": n, "diameter": round(dw, 3), "ohms": round(ohm, 5), "channelAtLeast": round(need, 2), "fits": size >= need, "note": "Solid copper at 20 °C; insulation adds to the diameter — check the wire's own."}
    out["conductor"] = cond
    out["printerFit"] = said
    return out


HANDLERS = {
    "kicad_import": kicad_import,
    "board_enclosure": board_enclosure,
    "pcb_order_package": pcb_order_package,
    "printed_channel": printed_channel,
}


def bound(ctx, handlers=None):
    """{tool_name: fn(args)} for one context: handlers (default all) with
    ctx given."""
    return {k: functools.partial(fn, ctx) for k, fn in (HANDLERS if handlers is None else handlers).items()}
