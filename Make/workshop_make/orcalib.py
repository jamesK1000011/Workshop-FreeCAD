# SPDX-License-Identifier: LGPL-2.1-or-later
# The slicers' command lines and presets live in Agent Link for OrcaSlicer's
# orcalink package (plain Python, no FreeCAD): one copy, which Make slices
# through. In FreeCAD its Mod folder (OrcaLink) is on the path; elsewhere
# ORCALINK_DIR (or AGENTLINK_ORCALINK) names its checkout.
import importlib
import os
import sys

from workshop_make.refusal import Refused

HOW = ("Slicing needs Agent Link for OrcaSlicer (github.com/jamesK1000011/AgentLink-OrcaSlicer, the slicers' "
       "command lines): install it beside this add-on, or set ORCALINK_DIR to its folder.")


def module(name):
    """orcalink.<name>, or Refused saying how to get it."""
    try:
        return importlib.import_module(f"orcalink.{name}")
    except ImportError:
        pass
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for d in (os.environ.get("ORCALINK_DIR"), os.environ.get("AGENTLINK_ORCALINK"), os.path.join(here, "OrcaLink")):
        if d and os.path.isfile(os.path.join(d, "orcalink", "__init__.py")) and d not in sys.path:
            sys.path.append(d)
            try:
                return importlib.import_module(f"orcalink.{name}")
            except ImportError:
                continue
    raise Refused(HOW, "unavailable")
