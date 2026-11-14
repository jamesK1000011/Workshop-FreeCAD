# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD's shared pieces: the Workshop workbench every Workshop
add-on adds its commands to. Records, shape helpers, fits, the parameter
form and Refused come from AddonKit for FreeCAD (addonkit), re-exported here
so add-ons written for workshop_common keep working."""

import addonkit
from addonkit import Refused  # noqa: F401

addonkit.require(">=1.0,<2", "Workshop for FreeCAD")

VERSION = "0.2.0"
