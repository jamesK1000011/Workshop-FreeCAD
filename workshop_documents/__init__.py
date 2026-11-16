# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD · Documents: drawing sheets, assembly manuals, patent
figures and library packs of your parts.

    from workshop_documents import api
    api.project(shapes, "front")            # 2D lines of a standard view
    api.readme(...), api.license_text(...)  # a library pack's papers

Plain values in millimetres; a request it cannot carry out is refused
(its refusal.Refused) with what to do instead."""

VERSION = "0.4.0"
