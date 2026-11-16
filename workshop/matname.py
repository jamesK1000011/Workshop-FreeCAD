# SPDX-License-Identifier: LGPL-2.1-or-later
"""A material's name as a person reads it, from whatever id a part carries:
a filament key (pla -> PLA), a custom card (custom:…), or FreeCAD's own
material library's id, a UUID ("68b152b2-…" -> "Aluminum-6061-T6"). The
mass report and the drawing's title block showed the UUID. Every lookup is
guarded: without FreeCAD, Agent Link or the library, the next one is tried,
and the id itself is the last answer."""

import re

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def is_uuid(mid):
    return bool(UUID.match(str(mid or "").strip()))


def _filament(mid):
    try:
        from workshop_make import materials

        c = materials.card(mid)
        return c["name"].split(" (")[0] if c else None
    except Exception:  # noqa: BLE001
        return None


def _agentlink(doc, mid):
    try:
        from agentlink.families import material as matfam

        c = matfam.card(doc, mid)
        return str(c["name"]) if c and c.get("name") else None
    except Exception:  # noqa: BLE001
        return None


def _library(mid):
    try:
        import Materials

        m = Materials.MaterialManager().getMaterial(str(mid))
        return str(m.Name) if m is not None and getattr(m, "Name", None) else None
    except Exception:  # noqa: BLE001
        return None


def name_of(mid, doc=None):
    """The material's name, or None when no lookup knows the id."""
    if mid is None or str(mid).strip() == "":
        return None
    mid = str(mid).strip()
    return _filament(mid) or _agentlink(doc, mid) or (_library(mid) if is_uuid(mid) else None)


def shown(mid, doc=None):
    """The name, else the id as written (a short key upper-cased, PLA); a
    library id nothing knows is said as such rather than shown bare."""
    n = name_of(mid, doc)
    if n:
        return n
    t = str(mid or "").strip()
    if not t:
        return "not set"
    if is_uuid(t):
        return f"a FreeCAD material card ({t[:8]}…)"
    return t.upper() if len(t) <= 5 and t.replace("-", "").isalnum() else t
