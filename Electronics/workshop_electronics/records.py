# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Electronics' own copy of Agent Link for FreeCAD's store.py (records format: Agent Link docs/records.md), trimmed to what Electronics uses; 14 Nov 2026.
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


def holder(doc, make=False):
    if not _objects(doc):
        return None
    o = doc.getObject(HOLDER)
    if o is None and make:
        o = doc.addObject("App::FeaturePython", HOLDER)
        o.Label = "Agent Link records"
        try:
            o.setPropertyStatus("Label", "ReadOnly")
        except Exception:
            pass
        try:
            o.Visibility = False
        except Exception:
            pass
        vo = getattr(o, "ViewObject", None)
        if vo is not None and hasattr(vo, "ShowInTree"):
            vo.ShowInTree = False
        for k, v in (doc.Meta or {}).items():
            if k.startswith(KEY):
                _set(o, k[len(KEY):], v)
    return o


def _set(o, name, raw):
    p = _prop(name)
    if p not in o.PropertiesList:
        o.addProperty("App::PropertyString", p, "AgentLink", f"Agent Link record: {name} (JSON)")
        try:
            o.setEditorMode(p, 2)
        except Exception:
            pass
    setattr(o, p, raw)


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


def write(doc, name, value):
    raw = json.dumps(value, separators=(",", ":"))
    o = holder(doc, make=True)
    if o is None:
        m = dict(doc.Meta or {})
        m[KEY + name] = raw
        doc.Meta = m
        return
    _set(o, name, raw)


# ---- setups: how each part is made --------------------------------------------------------
# One setup is one process and the bodies made by it, with that process's
# settings — as a setup is in Fusion's Manufacture workspace. A body is in
# one setup of a kind at most. Nothing chooses a process for a part: the
# person decides, and a setup records it.
