# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop's tools for agents, all of them, through Agent Link for FreeCAD:
# Agent Link finds this module by convention (a package on the path holding
# agentlink_families) and never names it; without Agent Link it is never
# loaded. Each part's own families module (workshop_parts.families,
# workshop_make.families, workshop_electronics.families,
# workshop_documents.families, safetynet.families) is joined here, with its
# services, hooks, hosted tabs and guides as before; tool names are the ones
# they have always had. A part that fails to load is said and left out; the
# others still load.
import importlib
import os
import sys

from . import PARTS

AGENTLINK_API = ">=1,<2"
CREDIT = None
LICENSE = "LGPL-2.1-or-later"

FAMILIES = []
LOADED = []
# part -> why it was left out
LEFT_OUT = {}


def _guides(mod):
    """The part's guides/ folder registered for guide_read (Agent Link
    registers only the one beside this module on its own)."""
    try:
        from agentlink import tools

        tools.register_guides(os.path.join(os.path.dirname(os.path.abspath(mod.__file__)), "guides"))
    except Exception:  # noqa: BLE001 — an Agent Link without the hook: the tools still load
        pass


def _load():
    try:  # this add-on's packages ahead of old copies beside it (said once)
        from . import stale

        stale.prefer_own()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"Workshop: start-up check skipped ({e})\n")
    for part in PARTS:
        try:
            mod = importlib.import_module(part + ".families")
            fams = list(getattr(mod, "FAMILIES", []))
        except Exception as e:  # noqa: BLE001
            LEFT_OUT[part] = f"{type(e).__name__}: {e}"
            sys.stderr.write(f"Workshop: {part}'s tools left out — {LEFT_OUT[part]}\n")
            continue
        FAMILIES.extend(fams)
        LOADED.append(part)
        _guides(mod)


_load()
