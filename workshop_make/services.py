# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make's services for other add-ons, offered through Agent Link's hooks
(hooks.provide) when Agent Link loads Make. Make owns mass and materials:
Agent Link's measure_mass and material_set defer to these when Make is
installed. The names and call shapes are stable; README ▸ Hook services
lists them. No Agent Link import here.

- "mass_properties": f(session, args) -> mass_properties' answer (args as
  the tool takes them: body, as printed in a print setup, inserts
  included). Raises the tool's refusal.
- "material_set": f(doc, bodies, material) -> {"materials", "freecadMaterial"}:
  Make's filament for bodies (labels) and FreeCAD's material set to match;
  material "" or None forgets it (PLA assumed, FreeCAD's default back).
  Raises Refused for a material Make does not know."""

from . import api

NAMES = ("mass_properties", "material_set")


def mass_properties(session, args=None):
    from .handlers import mass as H

    return H.mass_properties(session, dict(args or {}))


def material_set(doc, bodies, material):
    bodies = list(bodies or [])
    if material:
        mats = api.material_set(doc, bodies, material)
        fc = api.freecad_material(doc, bodies, material)
    else:
        mats = api.material_clear(doc, bodies)
        fc = api.freecad_material(doc, bodies, None)
    return {"materials": mats, "freecadMaterial": fc}


SERVICES = {"mass_properties": mass_properties, "material_set": material_set}


def provide(hooks):
    """Offer every service on Agent Link's hooks."""
    if not hasattr(hooks, "provide"):
        return []
    for name, fn in SERVICES.items():
        hooks.provide(name, fn)
    return list(SERVICES)


# ---- Make's reading for the shared health check ------------------------------------------

HEALTH_OWNER = "workshop_make"
HEALTH_MAX = 12  # records looked at per call: the check has a time budget


def health_reading(session, tool, changed):
    """Make's own reading after a changing call, for Agent Link's shared
    health check (health.register(owner, fn): fn(session, tool, changed) ->
    [{ line, red, todo }]). Only reads, and only Make's records against
    the document as it now stands:

    - a setup that names a body no longer in the document (deleted, or
      renamed: records are kept by Label) — its process, material and
      pauses no longer reach it;
    - an encased part's record (hw_embed) in a body the call recomputed,
      whose pocket is solid again: its pause would stop the print for
      nothing.

    Neither is red (the model is sound); each says the call that puts it
    right. No Agent Link import here: families.py registers it."""
    from . import records

    doc = getattr(session, "doc", None)
    if doc is None:
        return []
    out = []
    try:
        labels = {o.Label for o in doc.Objects}
    except Exception:  # noqa: BLE001
        return []
    for st in records.setups(doc)[:HEALTH_MAX]:
        gone = [b for b in st.get("bodies") or [] if b not in labels]
        if gone:
            out.append({"line": f"setup {st.get('name')} ({st.get('id')}) names {', '.join(gone[:3])}, not in the document now (deleted or renamed: setups go by label)",
                        "red": False, "todo": f"setup set {{ id: \"{st.get('id')}\", remove: [\"{gone[0]}\"] }} — and add: [its new name] if it was renamed"})
    embeds = records.read(doc, "embeds", {}) or {}
    if embeds:
        looked = 0
        for o in changed or []:
            recs = embeds.get(getattr(o, "Label", None))
            if not recs:
                continue
            try:
                solid = o.Shape
                import FreeCAD

                filled = [r["id"] for r in recs[:HEALTH_MAX] if solid.isInside(FreeCAD.Vector(*r["centre"]), 1e-6, True)]
            except Exception:  # noqa: BLE001
                continue
            looked += len(recs)
            if filled:
                out.append({"line": f"{o.Label}: the pocket of encased part {', '.join(filled[:4])} is solid again; its pause is still recorded",
                            "red": False, "todo": f"hw_embed_list {{ body: \"{o.Label}\" }} drops the dead record (or history_undo if the change filled it by mistake)"})
            if looked >= HEALTH_MAX:
                break
    return out

