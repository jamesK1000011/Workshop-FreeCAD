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
