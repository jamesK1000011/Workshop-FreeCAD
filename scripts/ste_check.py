#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""ASD-STE100 check of the tool descriptions (test arm "new B", branch
explore/full-ste). The rules are the hub's (agentlink-freecad
scripts/ste_check.py), so the add-ons and the hub are judged alike; plain
Python, no FreeCAD.

lint          each sentence has at most 20 words. Not counted: text in quotes
              or backticks and {...} / [...] literals; a list of three or more
              names (input names, tool names, snake_case or camelCase code
              words) counts as one word. Passive "is/are + -ed" is a warning
              count only.
preservation  against scripts/ste_originals.json (the text on main before the
              rewrite): every number, unit token, guard word (copy, undo,
              refuse, never, only, must, approval, restart, sign-off,
              feasibility), input name of the tool's schema (nested ones too)
              and tool name of the original is still in the new text. Two
              more checks of the add-ons: every number with its unit ("4 GB",
              "0.2 mm") and every code name (snake_case, camelCase,
              dotted.key: answer keys) of the original stay too.

A waiver is explicit, with a reason, in WAIVERS below; nothing else passes.

    python3 scripts/ste_check.py                         # report; exit 1 on a fault
    python3 scripts/ste_check.py --save --root=<main checkout> --names=<names.json>
                                                         # write ste_originals.json from main
"""
import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINALS = os.path.join(ROOT, "scripts", "ste_originals.json")
LIMIT = 20
# Tools defined in Python (a Tool(name, description, ...) call), beside the
# data/tools.json files found on their own.
PY_SOURCES = ("workshop_parts/fam_parts.py", "safetynet/fam_history.py", "safetynet/fam_safety.py")
# A stem of the original that the new text must keep (the hub's list and patterns).
GUARDS = {"copy": r"\bcop(?:y|ies|ied)\b", "undo": r"\bundo", "refuse": r"\brefus", "never": r"\bnever\b", "only": r"\bonly\b",
          "must": r"\bmust\b", "approval": r"\bapprov", "restart": r"\brestart", "sign-off": r"\bsign[- ]?off", "feasibility": r"\bfeasib"}
UNITS = r"(?:mm³|mm²|mm/s|mm|cm|µm|um|m|in|deg|°C|°|N·m|Nm|N|MPa|GPa|kPa|Pa|ms|s|min|h|%|px|kB|KB|MB|GB|kg|g|W|V|A|Hz|K)"
# A card whose long part went to a guide section (guide_read): the facts of
# the original may be in the card or in that section, and the card must name
# the section. {tool: (guide file, section name)}.
GUIDE_SECTIONS = {"drawing_make": ("workshop_documents/guides/drawing.md", "drawing_make in full")}
# (tool, kind, item): reason. kind is "number", "unit", "unitword", "input",
# "tool", "code", "guard" or "sentence" (item: the sentence's first words).
WAIVERS = {}


# --- reading the descriptions ------------------------------------------------

def _static(node, names):
    """The literal text of a description expression; a call (a table made
    from data at run time) is shown as " … "."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _static(node.left, names) + _static(node.right, names)
    if isinstance(node, ast.Name):
        return names.get(node.id, " … ")
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else " … " for v in node.values)
    return " … "


def _read_py(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    names, out = {}, {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            names[n.targets[0].id] = _static(n.value, names)
    # a second pass: names that use names assigned after them in the walk
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            names[n.targets[0].id] = _static(n.value, names)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "Tool" and len(n.args) >= 3:
            name = n.args[0].value if isinstance(n.args[0], ast.Constant) else None
            if not name:
                continue
            props = []
            schema = n.args[2]
            for sub in ast.walk(schema):
                if isinstance(sub, ast.Dict):
                    for k, v in zip(sub.keys, sub.values):
                        if isinstance(k, ast.Constant) and k.value == "properties" and isinstance(v, ast.Dict):
                            props += [kk.value for kk in v.keys if isinstance(kk, ast.Constant)]
                if isinstance(sub, ast.Call) and getattr(sub.func, "id", None) == "obj" and sub.args and isinstance(sub.args[0], ast.Dict):
                    props += [kk.value for kk in sub.args[0].keys if isinstance(kk, ast.Constant)]
            out[name] = {"src": os.path.relpath(path, ROOT), "description": _static(n.args[1], names), "inputs": sorted(set(props))}
    return out


def _json_names(schema):
    """Every input name of a schema, nested ones too (as the hub's check)."""
    out = []
    if isinstance(schema, dict):
        for k, v in (schema.get("properties") or {}).items():
            out.append(k)
            out += _json_names(v)
        for k in ("items", "additionalProperties"):
            out += _json_names(schema.get(k))
        for k in ("anyOf", "oneOf", "allOf"):
            for v in schema.get(k) or ():
                out += _json_names(v)
    elif isinstance(schema, list):
        for v in schema:
            out += _json_names(v)
    return out


def current():
    """{tool: {src, description, inputs}} as the files hold them now."""
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "**", "data", "tools.json"), recursive=True)):
        if "/tests/" in path or "/.git/" in path:
            continue
        with open(path, encoding="utf-8") as f:
            for name, e in json.load(f)["entries"].items():
                out[name] = {"src": os.path.relpath(path, ROOT), "description": e.get("description", ""),
                             "inputs": sorted(set(_json_names(e.get("inputSchema") or {})))}
    for rel in PY_SOURCES:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            out.update(_read_py(path))
    return out


# --- lint (the hub's rules, agentlink-freecad scripts/ste_check.py) -------

_ABBR = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|incl|no)$", re.I)
_LIT = re.compile(r'"[^"]*"|`[^`]*`|“[^”]*”')
_PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:not\s+)?\w+ed\b", re.I)


def sentences(text):
    """Sentences, split at . ! ? before a space (never in a decimal, e.g. or
    a literal: a full stop inside quotes or a {...} / [...] literal is not an end)."""
    t = " ".join(str(text or "").split())
    masked = list(t)
    depth, quote = 0, None
    for i, c in enumerate(t):
        if quote:
            if c == quote:
                quote = None
            masked[i] = "x" if c in ".!?" else c
            continue
        if c in "\"`":
            quote = c
        elif c in "{[":
            depth += 1
        elif c in "}]" and depth:
            depth -= 1
        elif depth and c in ".!?":
            masked[i] = "x"
    m_text = "".join(masked)
    out, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+\S|$)", m_text):
        if _ABBR.search(t[start:m.start()]):
            continue
        out.append(t[start:m.end()].strip())
        start = m.end()
    if t[start:].strip():
        out.append(t[start:].strip())
    return [s for s in out if s]


def _strip_literals(s):
    s = _LIT.sub(" ", s)
    out, depth = [], 0
    for c in s:
        if c in "{[":
            depth += 1
            continue
        if c in "}]" and depth:
            depth -= 1
            continue
        if not depth:
            out.append(c)
    return "".join(out)


def words(s, names=()):
    """Words of a sentence that count: literals left out, and a list of three
    or more names (inputs, tools, code words) counted as one word."""
    names = set(names)

    def is_name(w):
        w = w.strip(",;:()?.!")
        return w in names or bool(re.fullmatch(r"[a-z][a-z0-9]*_[a-z0-9_]*|[a-z]+[A-Z]\w*", w))

    out, run, glue = 0, 0, 0
    for w in [w for w in _strip_literals(s).split() if re.search(r"[A-Za-z0-9]", w)] + ["."]:
        if w != "." and is_name(w):
            run += 1
            continue
        if run and w in ("or", "and"):
            glue += 1
            continue
        out += 1 if run >= 3 else run + glue
        run = glue = 0
        if w != ".":
            out += 1
    return out


def lint(descs, tool_names=()):
    faults = []
    for name, d in sorted(descs.items()):
        names = set(d.get("inputs", ())) | set(descs) | set(tool_names)
        for s in sentences(d["description"]):
            n = words(s, names)
            if n > LIMIT and not _waived(name, "sentence", " ".join(s.split()[:6])):
                faults.append((name, "sentence", f"{n} words: {s[:90]}"))
    return faults


def passive(descs):
    return sum(len(_PASSIVE.findall(d["description"])) for d in descs.values())


# --- preservation ------------------------------------------------------------
# The hub's checks (numbers, unit tokens, guard words, input names, tool
# names), and two more of this add-on's: every number with its unit, and
# every code name (snake_case, camelCase, dotted.key: answer keys).

HUB_UNITS = ("mm", "cm", "m", "µm", "um", "in", "deg", "°", "°C", "C", "K", "N", "kN", "Nm", "N·m", "MPa", "GPa", "Pa", "kPa", "s", "ms",
             "min", "h", "px", "dpi", "%", "kg", "g", "g/cm³", "mm²", "mm³", "rpm", "W", "V", "A", "Hz", "MB", "GB", "KB", "kB", "bytes")
_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def _digits_only(text):
    # "3MF", "2D", "x2" keep their digits: a number is a digit run not inside a word of letters around it.
    return re.sub(r"(?<=[A-Za-z_])\d+|\d+(?=[A-Za-z_]{2,}\w*\b(?<!mm)(?<!ms)(?<!deg))", " ", text)


def _numbers(t):
    return set(_NUM.findall(_digits_only(t)))


def _units(text):
    """Unit tokens: a long unit anywhere as a word, a one-letter unit after a number or as "(u)" / "in u"."""
    out = set()
    for u in HUB_UNITS:
        e = re.escape(u)
        if u == "in":
            rx = r"(?:\d\s?|\(|\| )in(?=\s*[,.;:)\]\"|]|$)"
        elif len(u) >= 2:
            rx = r"(?:(?<=\d)|(?<![\w°/]))" + e + r"(?![\w²³/])"
        else:
            rx = r"\d\s?" + e + r"(?![\w²³/])|\(" + e + r"\)|\bin " + e + r"(?![\w²³/])"
        if re.search(rx, text):
            out.add(u)
    return out


def _with_units(t):
    return {f"{n} {u}" for n, u in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)\s?(%s)(?![\w])" % UNITS, t)}


_CODE = re.compile(r"(?<![\w.])(?:[a-z][a-z0-9]*_[\w]+|[a-z][a-z0-9]*[A-Z]\w*|[a-z]\w*\.[a-z]\w*(?:\.\w+)*)")


def _code(t):
    return set(m.rstrip(".") for m in _CODE.findall(_LIT.sub(" ", t)) if not re.match(r"^(?:e\.g|i\.e)$", m.rstrip(".")))


def _mentioned(text, names):
    return {n for n in names if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", text)}


def _has_word(word, t):
    return re.search(r"(?<![\w])%s(?![\w])" % re.escape(word), t) is not None


def _guards(t):
    return {g for g, rx in GUARDS.items() if re.search(rx, t, re.I)}


def _waived(tool, kind, item):
    return (tool, kind, item) in WAIVERS


def guide_section(name):
    """The text of the guide section a card points to (GUIDE_SECTIONS), or
    None: no section is named, or the guide has no such section."""
    if name not in GUIDE_SECTIONS:
        return None
    rel, sec = GUIDE_SECTIONS[name]
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    for part in re.split(r"(?m)^## ", text)[1:]:
        head, _, body = part.partition("\n")
        if head.strip() == sec:
            return re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    return None


def preservation(descs, originals):
    faults = []
    names = set(originals.get("toolNames", [])) | set(descs)
    for name, o in sorted(originals["tools"].items()):
        if name not in descs:
            faults.append((name, "tool", "the tool is gone"))
            continue
        old, new = o["description"], descs[name]["description"]
        if name in GUIDE_SECTIONS:
            sec = guide_section(name)
            if sec is None:
                faults.append((name, "guide", f"no section {GUIDE_SECTIONS[name][1]!r} in {GUIDE_SECTIONS[name][0]}"))
                continue
            if GUIDE_SECTIONS[name][1] not in new:
                faults.append((name, "guide", f"the card does not name its guide section {GUIDE_SECTIONS[name][1]!r}"))
            new = new + " " + " ".join(sec.split())
        lost = [("number", x) for x in sorted(_numbers(old) - _numbers(new))]
        lost += [("unit", x) for x in sorted(_units(old) - _units(new))]
        lost += [("guard", x) for x in sorted(_guards(old) - _guards(new))]
        lost += [("input", x) for x in sorted(_mentioned(old, o.get("inputs", [])) - _mentioned(new, o.get("inputs", [])))]
        others = names - {name}
        lost += [("tool", x) for x in sorted(_mentioned(old, others) - _mentioned(new, others))]
        new_units = _with_units(new)
        lost += [("unit", x) for x in sorted(_with_units(old) - new_units)
                 if not (x.split()[0] in _numbers(new) and not _with_units(x) - new_units)]
        lost += [("code", x) for x in sorted(_code(old)) if not _has_word(x, new)]
        faults += [(name, k, x) for k, x in lost if not _waived(name, k, x)]
    return faults


def load_originals():
    with open(ORIGINALS, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    global ROOT
    for a in argv:
        if a.startswith("--root="):
            ROOT = os.path.abspath(a[7:])
    if "--save" in argv:
        extra = []
        for a in argv:
            if a.startswith("--names="):
                with open(a[8:], encoding="utf-8") as f:
                    extra = json.load(f)
        descs = current()
        data = {"about": "The tool descriptions as main held them before the ASD-STE100 rewrite (branch explore/full-ste); scripts/ste_check.py compares with them. toolNames: every tool name of this add-on, Agent Link and its other add-ons, to find the ones a text points to.",
                "toolNames": sorted(set(descs) | set(extra)), "tools": descs}
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ste_originals.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"saved {len(descs)} tools")
        return 0
    descs = current()
    originals = load_originals()
    faults = lint(descs, originals.get("toolNames", ())) + preservation(descs, originals)
    for t, k, x in faults:
        print(f"{t}: {k}: {x}")
    print(f"{len(descs)} tools, {len(faults)} faults, passive warnings {passive(descs)}, waivers {len(WAIVERS)}")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
