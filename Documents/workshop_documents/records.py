# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Documents' own copy of Agent Link for FreeCAD's store.py (records format: Agent Link docs/records.md), trimmed to what Documents uses; 14 Nov 2026.
# What the agent records about the parts, kept in the document itself so it
# is saved with the .FCStd: how each part is made (setups), what it is made
# of, the limits it must meet (the spec), and the findings accepted on
# purpose (waivers). Each record is JSON under its own name.
#
# The records live in one hidden object, AgentLinkRecords (a string property
# a record), so writing one happens inside the tool's undo step and undo
# takes it back with the rest (unattended use, B). Files from before kept
# them in the document's Meta, which is outside undo: those are read from
# there until the first write copies them over. Meta is left as it was — the
# state before the records object, which is what undoing its creation goes
# back to.

import json
import re

# The names below are the file format's (documents written since Agent Link's
# first records carry them), not a reference to any add-on; keep them.
KEY = "AgentLink."
HOLDER = "AgentLinkRecords"


def _prop(name):
    return "R_" + re.sub(r"\W", "_", name)


def _objects(doc):
    # A document without objects of its own (a test double): Meta only.
    return hasattr(doc, "getObject") and hasattr(doc, "addObject")


def _raw(doc, name):
    o = doc.getObject(HOLDER) if _objects(doc) else None
    if o is not None:
        p = _prop(name)
        if p in o.PropertiesList:
            return getattr(o, p)
        return None
    return (doc.Meta or {}).get(KEY + name)


def read(doc, name, default):
    raw = _raw(doc, name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


# ---- setups: how each part is made --------------------------------------------------------
# One setup is one process and the bodies made by it, with that process's
# settings — as a setup is in Fusion's Manufacture workspace. A body is in
# one setup of a kind at most. Nothing chooses a process for a part: the
# person decides, and a setup records it.


def setups(doc):
    return read(doc, "setups", [])


def setup_of(doc, body, kind=None):
    for s in setups(doc):
        if body in s["bodies"] and (kind is None or s["type"] == kind):
            return s
    return None


# ---- per-part records ---------------------------------------------------------------------


def materials(doc):
    return read(doc, "materials", {})
