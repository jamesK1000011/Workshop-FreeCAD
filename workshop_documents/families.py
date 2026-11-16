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
    from . import layout

    # The Manual is Documents' own dock beside Model and Tasks (its clicks
    # run through Agent Link); only an Agent Link that cannot place it
    # hosts it in its panel.
    if hasattr(hooks, "register_tab") and layout.hosted_tabs(hooks):
        from . import panel

        for title, cls, order in panel.HOSTED:
            if not any(t.get("title") == title for t in getattr(hooks, "TABS", [])):
                make = panel.factory(cls, lambda: hooks.service("manual_maker"))
                try:  # the tab only while Documents is the workbench in front
                    hooks.register_tab(title, make, order, workbench=panel.WORKBENCH)
                except TypeError:  # an Agent Link before tabs per workbench
                    hooks.register_tab(title, make, order)


def _health():
    """The drawing pages' state in Agent Link's shared health check
    (td_wait.py holds the reading and imports no Agent Link)."""
    from agentlink import health

    from . import td_wait

    health.register(td_wait.HEALTH_OWNER, td_wait.page_reading)


try:
    _health()
except Exception:  # noqa: BLE001 — an Agent Link before the shared health check: the tools still load
    pass
try:
    _host()
except Exception:  # noqa: BLE001 — no Qt (a headless Agent Link): the tools still load
    import workshop_documents

    workshop_documents._hosted = True
