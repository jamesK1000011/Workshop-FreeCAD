# SPDX-License-Identifier: LGPL-2.1-or-later
# Printers on the network: kept by name (the key or password in
# ~/AgentLink/printers.json, never given back), their state, a G-code file
# sent to one, and a job paused or stopped. Starting, pausing and stopping a
# print need the person's approval through the client (approve_file, Agent
# Link's hooks.person_ok), never a typed confirm.
# Agent Link's binding: the handlers in handlers/printer.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import printer as H

GROUP = "printer"
WORKBENCHES = {"printer_status": "WorkshopMakeWorkbench", "printer_send": "WorkshopMakeWorkbench"}  # the Make bench, where their buttons are
COMMANDS = {"printer_status": "Workshop_Make_PrinterStatus", "printer_send": "Workshop_Make_PrinterSend"}  # the button that does the same
INFO = "Printers on the network (OctoPrint, Moonraker/Klipper, PrusaLink): add, list, status, send G-code; start, pause and stop only with the person's approval (approve_file)."

handlers.lend(H, ToolError=ToolError, HUB=True)
try:
    from agentlink import hooks, paths

    for _n in ("printer_send", "printer_pause", "printer_stop"):
        getattr(hooks, "keep_unextended", lambda _x: None)(_n)  # no other add-on wraps these
    handlers.lend(H, PERSON_OK=getattr(hooks, "person_ok", None), IN_FILE=getattr(paths, "in_file", None))
except ImportError:
    pass


def tools(session):
    return tooldefs.build("printer", handlers.bound(session, H.HANDLERS))
