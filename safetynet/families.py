# SPDX-License-Identifier: LGPL-2.1-or-later
# What Agent Link for FreeCAD loads from SafetyNet when both are installed:
# the checkpoint tools (in Agent Link's core group), the safety tools
# (app_recover, settings history and rollback, macros), the services and
# events that connect them, the Session tab and the guide. Agent Link finds
# this module by convention and never names it; without Agent Link it is
# never loaded.
import os
import sys

from . import fam_history, fam_safety

AGENTLINK_API = ">=1,<2"
FAMILIES = [fam_history, fam_safety]
CREDIT = None
LICENSE = "LGPL-2.1-or-later"


def _reply_written(session):
    """After each reply of a supervised hidden FreeCAD: what it holds, for
    the FreeCAD started again after a crash to recover."""
    if os.environ.get("AGENTLINK_SUPERVISED"):
        from . import recovery

        recovery.write_hidden()


def _register():
    from agentlink import hooks

    from . import autosave, checkpoints, panel, recovery, settings

    hooks.provide("checkpoints", checkpoints.Service)
    hooks.provide("reopen", recovery.Reopen)
    hooks.on("after_change", autosave.after_change)
    hooks.on("after_change", recovery.note_change)
    hooks.on("setting_changing", settings.changing)
    hooks.on("setting_changed", settings.changed)
    hooks.on("reply_written", _reply_written)
    from . import layout

    # The Session panel is SafetyNet's own dock beside Model and Tasks (its
    # clicks run through Agent Link); only an Agent Link that cannot place
    # it hosts it as a tab of its panel.
    if layout.hosted_tabs(hooks):
        try:  # the tab only while Make is the workbench in front
            hooks.register_tab("Session", panel.make, order=90, workbench=panel.WORKBENCH)
        except TypeError:  # an Agent Link before tabs per workbench
            hooks.register_tab("Session", panel.make, order=90)
    # SafetyNet's Panel command raises Agent Link's Session tab from now on.
    sys.modules[__name__.rpartition(".")[0]]._hosted = True


def _guides():
    from agentlink import tools as al_tools

    al_tools.register_guides(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guides"))


_register()
try:
    _guides()
except Exception:  # noqa: BLE001 — an Agent Link without the hook: the tools still load
    pass
