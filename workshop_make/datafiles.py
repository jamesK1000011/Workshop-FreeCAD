# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make's own copy of Agent Link for FreeCAD's datafiles.py, trimmed to what Make uses (check_folder is kept for Make's data-file tests); 14 Nov 2026.
"""Versioned, schema-checked data files: tables (fits, threads, printers,
materials, presets) and tool definitions kept out of the code.

A data file is JSON:

    {"$schema": "<name>.schema.json", "dataVersion": "1.2.0",
     "licence": "CC-BY-4.0", "freecad": ">=1.1",            # optional
     "entries": {"<key>": {..., "source": "...", "date": "YYYY-MM-DD"}}}

- Every entry says where it came from (source) and when (date).
- dataVersion is the data's own version; the code says which it accepts,
  and a file too new for it is refused with the reason, never half read.
- Side by side: <name>.json plus <name>@<tag>.json for versions of FreeCAD
  or another program that differ; select(tag) picks the right one.
- The person's own entries live in a folder updates never touch
  (ADDON_OVERRIDES, else ~/.config/<package>/<name>.json) and
  win over ours, key by key; each carries source "user".

The schema check is a small subset of JSON Schema (type, properties,
required, additionalProperties, items, enum, minimum, maximum, minLength,
pattern, oneOf of types) so nothing beyond Python is needed.
"""

import json
import os
import re

from .refusal import Refused, satisfies


class DataError(Refused):
    def __init__(self, message):
        super().__init__(message, "invalid_state")


TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _is(value, t):
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


def validate(value, schema, where="$"):
    """A list of problems, empty when value fits schema."""
    out = []
    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(_is(value, x) for x in ts):
            return [f"{where}: expected {' or '.join(ts)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{where}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(f"{where}: {value} is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            out.append(f"{where}: {value} is above {schema['maximum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(f"{where}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            out.append(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                out.append(f"{where}: missing {k}")
        extra = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                out += validate(v, props[k], f"{where}.{k}")
            elif extra is False:
                out.append(f"{where}: unexpected {k}")
            elif isinstance(extra, dict):
                out += validate(v, extra, f"{where}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += validate(v, schema["items"], f"{where}[{i}]")
    return out


# Every data file's outer shape; the file's own schema covers each entry.
ENVELOPE = {
    "type": "object",
    "required": ["dataVersion", "entries"],
    "properties": {
        "$schema": {"type": "string"},
        "dataVersion": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "licence": {"type": "string"},
        "freecad": {"type": "string"},
        "about": {"type": "string"},
        "entries": {"type": "object"},
    },
    "additionalProperties": False,
}


def overrides_dir(package):
    root = os.environ.get("ADDON_OVERRIDES") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(root, package)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise DataError(f"{os.path.basename(path)} cannot be read ({e}); reinstall the add-on, or fix the file if it is one of yours.")


def check(path, schema_path=None):
    """Problems with one data file (envelope, provenance, entry schema)."""
    doc = _read(path)
    out = validate(doc, ENVELOPE)
    if out:
        return out
    if schema_path is None:
        sp = doc.get("$schema")
        schema_path = os.path.join(os.path.dirname(path), sp) if sp else None
    entry = _read(schema_path) if schema_path and os.path.isfile(schema_path) else None
    for k, v in doc["entries"].items():
        if entry is not None:
            out += validate(v, entry, f"entries.{k}")
        if isinstance(v, dict) and not (v.get("source") and v.get("date")):
            out.append(f"entries.{k}: every entry says its source and date")
    return out


def load(folder, name, accepts=">=1.0,<2", package=None, tag=None, user=True):
    """The entries of folder/<name>.json (or <name>@<tag>.json when there is
    one), checked, with the person's overrides laid over them.

    Returns {"dataVersion", "entries", "overridden": [keys]}."""
    path = os.path.join(folder, f"{name}@{tag}.json") if tag else None
    if not path or not os.path.isfile(path):
        path = os.path.join(folder, f"{name}.json")
    doc = _read(path)
    problems = validate(doc, ENVELOPE)
    if problems:
        raise DataError(f"{os.path.basename(path)}: {problems[0]}")
    if not satisfies(accepts, doc["dataVersion"]):
        raise DataError(f"{os.path.basename(path)} is data version {doc['dataVersion']}; this code reads {accepts}. Update the add-on.")
    sp = doc.get("$schema")
    entry_schema = _read(os.path.join(folder, sp)) if sp and os.path.isfile(os.path.join(folder, sp)) else None
    entries = dict(doc["entries"])
    overridden = []
    if user and package:
        mine = os.path.join(overrides_dir(package), f"{name}.json")
        if os.path.isfile(mine):
            extra = _read(mine)
            for k, v in (extra.get("entries") or {}).items():
                if isinstance(v, dict):
                    v = {**v, "source": v.get("source", "user")}
                if entry_schema is not None:
                    p = validate(v, entry_schema, f"{name}.{k}")
                    if p:
                        raise DataError(f"Your {mine}: {p[0]}. Fix or remove that entry.")
                entries[k] = v
                overridden.append(k)
    return {"dataVersion": doc["dataVersion"], "entries": entries, "overridden": overridden}


def check_folder(folder):
    """Problems across every data file in a folder (for CI)."""
    out = []
    for n in sorted(os.listdir(folder)):
        if n.endswith(".json") and not n.endswith(".schema.json"):
            out += [f"{n}: {p}" for p in check(os.path.join(folder, n))]
    return out
