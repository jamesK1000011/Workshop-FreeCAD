# SPDX-License-Identifier: LGPL-2.1-or-later
# Documents with no agent: a macro or a command calls these. Never imports
# Agent Link.
import addonkit

from . import libpack

addonkit.require(">=1.5,<2", "Workshop Documents")

LICENSES = libpack.LICENSES
check_credits = libpack.check_credits
clean_step = libpack.clean_step
clean_stl = libpack.clean_stl
readme = libpack.readme
license_text = libpack.license_text
private_strings = libpack.private_strings
write_zip = libpack.write_zip


def views():
    """The standard views a sheet can show (front, top, right, iso …)."""
    from . import views as V

    return list(V.VIEWS)


def project(shapes, view, hidden=False):
    """The shapes' lines seen from a standard view, in the view's plane, mm
    (FreeCAD's hidden-line removal)."""
    from . import views as V

    if view not in V.VIEWS:
        raise addonkit.Refused(f"view: one of {', '.join(V.VIEWS)}.")
    return V.project(shapes, view, hidden=hidden)
