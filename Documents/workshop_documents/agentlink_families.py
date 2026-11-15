# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link loads from Documents when both are installed: drawing_make,
# drawing_exploded, patent_figures, patent_draft and library_pack, with their
# guides. Agent Link finds this module by convention and never names it;
# without Agent Link it is never loaded. It also hosts Documents' Manual tab
# in Agent Link's panel over its panel._call (its "Make manual" asks for a
# manual_maker service, if an add-on provides one), and says Documents is
# hosted (so Documents' own dock stays away).
from . import fam_drawing, fam_share

FAMILIES = [fam_drawing, fam_share]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"
AGENTLINK_API = ">=1,<2"


def _host():
    """Documents' Manual tab in Agent Link's panel."""
    import workshop_documents

    from agentlink import hooks

    workshop_documents._hosted = True
    if hasattr(hooks, "register_tab"):
        from . import panel

        for title, cls, order in panel.HOSTED:
            if not any(t.get("title") == title for t in getattr(hooks, "TABS", [])):
                hooks.register_tab(title, panel.factory(cls, lambda: hooks.service("manual_maker")), order)


try:
    _host()
except Exception:  # noqa: BLE001 — no Qt (a headless Agent Link): the tools still load
    import workshop_documents

    workshop_documents._hosted = True
