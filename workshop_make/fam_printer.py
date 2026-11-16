# SPDX-License-Identifier: LGPL-2.1-or-later
# Printers on the network: kept by name (the key or password in a file
# beside the session's, never given back), their state, a G-code file sent
# to one, and a job paused or stopped. Starting, pausing and stopping a
# print are the person's to decide: each needs a confirm string that says
# so, word for word.
# Agent Link's binding: the handlers in handlers/printer.py (no Agent Link
# import there) bound to the session. Loaded by Agent Link only.

from agentlink.protocol import ToolError

from . import tooldefs
from . import handlers
from .handlers import printer as H

GROUP = "printer"
WORKBENCHES = {"printer_status": "WorkshopMakeWorkbench", "printer_send": "WorkshopMakeWorkbench"}  # the Make bench, where their buttons are
COMMANDS = {"printer_status": "Workshop_Make_PrinterStatus", "printer_send": "Workshop_Make_PrinterSend"}  # the button that does the same
INFO = "Printers on the network (OctoPrint, Moonraker/Klipper, PrusaLink): add, list, status, send G-code; start, pause and stop only on the person's word."

handlers.lend(H, ToolError=ToolError)


def tools(session):
    return tooldefs.build("printer", handlers.bound(session, H.HANDLERS))
