# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents: the handler of library_pack (definition in
# data/tools.json; moved from Agent Link for FreeCAD on 14 Nov 2026). No
# Agent Link import here.
# Sharing parts: a library pack of bodies as STEP and STL, with a README of
# their sizes and how to print them, a licence, and credits for the parts
# remixed — with the computer's paths and the user's name kept out of the
# files.

import os
import re
import tempfile

from workshop_documents import geo
from workshop_documents import records as store

from .. import libpack as packing
from ._lent import Refusal

# Lent by the family layer when Agent Link binds these handlers (lend()); alone
# a refusal is this add-on's own and Agent Link's helpers are absent.
ToolError = Refusal


SETTING_WORDS = {"printer": "Printer", "nozzle": "Nozzle (mm)", "layerHeight": "Layer height (mm)", "firstLayer": "First layer (mm)", "walls": "Walls", "infill": "Infill (%)"}


# The library-pack service another add-on offers through Agent Link's
# hooks (ScanRuler-FreeCAD's pack, Stefan Hermann's pack_setup / plan /
# write): an object with pack(session, args) -> the answer library_pack
# gives (pack, files, license, parts, bytes, and its own fields), raising
# for a refusal. Documents' own pack below is the fallback when none is.
SERVICE = "library_pack"


def service():
    """The library-pack service when an add-on provides one, else None."""
    try:
        import importlib

        got = importlib.import_module("agentlink.hooks").service(SERVICE)
        return got if got is not None and hasattr(got, "pack") else None
    except Exception:  # noqa: BLE001 — Agent Link or the provider not installed
        return None


def library_pack(s, a):
    """The pack by the service when an add-on provides one (ScanRuler's,
    when ScanRuler-FreeCAD is installed); else Documents' own, below. A
    refusal from the service is the answer; a failure falls back."""
    svc = service() if a.get("provider", "auto") != "documents" else None
    if svc is not None:
        try:
            out = svc.pack(s, {k: v for k, v in a.items() if k != "provider"})
        except Exception as e:  # noqa: BLE001
            if getattr(e, "code", None) and getattr(e, "message", None):
                raise  # the provider's refusal, in its words
            fell = f"the library-pack service failed ({e}); Documents' own pack made it"
        else:
            out = dict(out or {})
            out.setdefault("by", getattr(svc, "NAME", "ScanRuler-FreeCAD"))
            return out
    else:
        fell = None
    out = own_pack(s, a)
    out["by"] = "Workshop Documents"
    if fell:
        out["serviceNote"] = fell
    return out


def own_pack(s, a):
    """Documents' own library pack: the fallback when no add-on provides
    the service."""
    from workshop_documents.materials import DENSITY

    lic = a.get("license")
    if lic not in packing.LICENSES:
        raise ToolError("invalid_input", f"license: one of {', '.join(packing.LICENSES)} — ask the person which; it decides what others may do with the parts.")
    author = (a.get("author") or "").strip()
    if lic in ("MIT", "CC-BY-4.0", "CC-BY-SA-4.0") and not author:
        raise ToolError("invalid_input", f"author: {lic} names who holds the copyright and is to be credited — the name the person wants shown (a handle will do).")
    credits = a.get("credits") or []
    if not isinstance(credits, list) or not all(isinstance(c, dict) for c in credits):
        raise ToolError("invalid_input", "credits: [{ title, author, url, license, changes }] for each remixed part.")
    errors, warnings = packing.check_credits(lic, credits)
    if errors:
        raise ToolError("invalid_input", "license: " + " ".join(errors))
    formats = a.get("formats") or ["step", "stl"]
    if not formats or any(f not in ("step", "stl") for f in formats):
        raise ToolError("invalid_input", "formats: step, stl or both.")
    objs = [s.body(b) for b in a["bodies"]] if a.get("bodies") else s.bodies()
    if not objs:
        raise ToolError("not_found", "No body in the document: make one first.")
    title = a.get("name") or (objs[0].Label if len(objs) == 1 else "Parts")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "parts"
    mats = store.materials(s.doc)
    import Mesh  # noqa: F401
    import MeshPart

    # The exports are read into the pack and the folder removed (red team 3, R3-13).
    with tempfile.TemporaryDirectory() as tmp:
        entries, parts, unsound = [], [], []
        settings, notes = {}, []
        for o in objs:
            fn = re.sub(r"[^A-Za-z0-9._-]+", "_", o.Label).strip("_") or "part"
            if not geo.soundness(o.Shape)["ok"]:
                unsound.append(o.Label)
            files = []
            if "step" in formats:
                p = os.path.join(tmp, fn + ".step")
                o.Shape.exportStep(p)
                with open(p, encoding="utf-8", errors="replace") as f:
                    text = packing.clean_step(f.read(), fn + ".step", author if lic != "CC0-1.0" else "")
                entries.append((f"{slug}/{fn}.step", text.encode("utf-8")))
                files.append(fn + ".step")
            if "stl" in formats:
                p = os.path.join(tmp, fn + ".stl")
                MeshPart.meshFromShape(Shape=o.Shape, LinearDeflection=float(a.get("tolerance", 0.01)), AngularDeflection=0.0873, Relative=False).write(p)
                with open(p, "rb") as f:
                    entries.append((f"{slug}/{fn}.stl", packing.clean_stl(f.read(), fn)))
                files.append(fn + ".stl")
            b = o.Shape.BoundBox
            m = mats.get(o.Label)
            parts.append({"files": files, "size": [round(b.XLength, 1), round(b.YLength, 1), round(b.ZLength, 1)], "volume": o.Shape.Volume, "material": m.upper() if m else None, "mass": round(o.Shape.Volume * DENSITY[m] / 1000, 1) if m in DENSITY else None})
            setup = store.setup_of(s.doc, o.Label, "print")
            if setup:
                for k, label in SETTING_WORDS.items():
                    if k in setup:
                        settings[label] = setup[k]
            enc = (s.meta.get(o.Label) or {}).get("encased")
            if enc:
                notes.append(f"{o.Label}: pause at {enc['top']} mm to drop in {enc['count']} {enc['what']}, or press them in after.")
    text = packing.readme(title, a.get("description"), author, lic, parts, settings, credits, notes)
    entries.append((f"{slug}/README.md", text.encode("utf-8")))
    entries.append((f"{slug}/LICENSE", packing.license_text(lic, author, title).encode("utf-8")))
    path = os.path.join(s.out_dir, f"{slug}.zip")
    packing.write_zip(path, entries)
    # What the pack holds may not carry the computer's paths or user name.
    leaks = []
    for name, data in entries:
        if name.endswith((".step", ".stl")):
            head = data[:4000].decode("utf-8", "replace")
            leaks += [name for x in packing.private_strings() if x in head]
    out = {"pack": path, "files": [n for n, _ in entries], "license": lic, "parts": [{"files": p["files"], "size": p["size"]} for p in parts], "bytes": os.path.getsize(path)}
    if warnings:
        out["warnings"] = warnings
    if unsound:
        out["unsound"] = {"bodies": unsound, "from": "body_check"}
    if leaks:
        out["personal"] = {"files": sorted(set(leaks)), "in": "firstLines"}
    return out


HANDLERS = {
    "library_pack": library_pack,
}
