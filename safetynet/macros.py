# SPDX-License-Identifier: LGPL-2.1-or-later
# Macros on FreeCAD's own macro tools: the macros are the files in FreeCAD's
# macro folder (Preferences ▸ Macro ▸ MacroPath, what Macro ▸ Macros… lists:
# .FCMacro and .py), run as FreeCAD runs one (the file executed with
# __main__'s globals, __name__ "__main__" and __file__ set, the macro folder
# on sys.path). What SafetyNet adds is what FreeCAD lacks: an approval list
# (a macro is Python with the run of the Mac, so it runs here only once the
# person approved it, its SHA-256 recorded in ~/AgentLink/macros-approved.json;
# changed code needs approving again; an agent never approves) and a
# checkpoint before each run. A session's agent calls can be saved as a
# .FCMacro too, its key sizes named at the top, replayed through
# agentlink.run(tool, args) — those need Agent Link to run.
#
# Plain FreeCAD, imported where it is used: writing and reading a macro's
# text needs neither.

import ast
import hashlib
import os
import re
import time

from .files import _load, _save, path


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def approvals():
    return _load(path("macros-approved.json"), {})


def approve(name, p):
    a = approvals()
    a[name] = {"sha256": sha256_file(p), "path": p, "t": time.time()}
    _save(path("macros-approved.json"), a)
    return a[name]


def unapprove(name):
    a = approvals()
    gone = a.pop(name, None)
    _save(path("macros-approved.json"), a)
    return gone


def approval_state(name, p):
    """approved | changed (its code moved since the OK) | no."""
    e = approvals().get(name)
    if not e:
        return "no"
    try:
        return "approved" if sha256_file(p) == e["sha256"] else "changed"
    except OSError:
        return "no"


# The files FreeCAD's Macro dialog lists.
EXTS = (".FCMacro", ".py")


def macro_name_ok(name):
    """A macro's name: its file name without .FCMacro (a .py macro keeps
    its .py); no folders."""
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,60}(\.py)?", str(name or "")))


def uses_agentlink(text):
    """True for a macro made of Agent Link calls (it imports agentlink):
    it runs only where Agent Link serves them."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] == "agentlink" for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "agentlink":
            return True
    return False


def freecad_globals(p):
    """The globals FreeCAD runs a macro file with (Interpreter::runFile with
    local: a copy of __main__'s, as the Python console has them), __name__
    "__main__" and __file__ the macro's path; FreeCAD, App, FreeCADGui and
    Gui there when they import."""
    import __main__

    g = dict(vars(__main__))
    for k in ("__builtins__",):
        g.setdefault(k, __builtins__)
    for name, alias in (("FreeCAD", "App"), ("FreeCADGui", "Gui")):
        try:
            mod = __import__(name)
        except ImportError:
            continue
        g.setdefault(name, mod)
        g.setdefault(alias, mod)
    g.update({"__name__": "__main__", "__file__": p})
    return g


def run_file(code, p, around=None):
    """A macro run as FreeCAD's macro execution runs one: its code (source
    text or a parsed tree) executed with freecad_globals, the macro folder on
    sys.path for its own imports while it runs. around: a context manager to
    run it in (Agent Link serving its calls)."""
    import contextlib
    import sys

    compiled = compile(code, p, "exec")
    folder = os.path.dirname(os.path.abspath(p))
    added = folder not in sys.path
    if added:
        sys.path.insert(0, folder)
    try:
        with (around or contextlib.nullcontext()):
            exec(compiled, freecad_globals(p))
    finally:
        if added:
            try:
                sys.path.remove(folder)
            except ValueError:
                pass


def _ident(k):
    s = re.sub(r"\W+", "_", str(k)).strip("_").upper() or "P"
    return s if not s[0].isdigit() else "P_" + s


def _one_line(text, cap=300):
    t = "".join(" " if ord(c) < 32 or ord(c) == 0x7f or c in "\x85\u2028\u2029" else c for c in str(text))
    return t[:cap]


def macro_text(name, calls, params, header):
    """A .FCMacro replaying agent calls in order, with the listed sizes as
    named constants at the top: each place a listed value appears in the
    calls' arguments is replaced by its name."""
    consts = {_ident(k): v for k, v in (params or {}).items()}
    by_value = {}
    for k, v in consts.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            by_value.setdefault(float(v), k)
        elif isinstance(v, str):
            by_value.setdefault(v, k)

    def lit(x):
        if isinstance(x, bool) or x is None:
            return repr(x)
        if isinstance(x, (int, float)):
            k = by_value.get(float(x))
            return k if k else repr(x)
        if isinstance(x, str):
            k = by_value.get(x)
            return k if k else repr(x)
        if isinstance(x, list):
            return "[" + ", ".join(lit(y) for y in x) + "]"
        if isinstance(x, dict):
            return "{" + ", ".join(f"{k!r}: {lit(v)}" for k, v in x.items()) + "}"
        return repr(x)

    # A header line holds labels (a document's, a body's) that anyone may
    # set: a line break in one would end the comment and start code (red
    # team, 2026-11-18). Each header line is one comment line.
    lines = ["# -*- coding: utf-8 -*-"] + [f"# {_one_line(h)}" for h in header] + ["", "# Key sizes: change them here."]
    for k, v in consts.items():
        lines.append(f"{k} = {v!r}")
    lines += ["", "import agentlink", ""]
    for c in calls:
        lines.append(f"agentlink.run({c['tool']!r}, {lit(c.get('args') or {})})")
    return "\n".join(lines) + "\n"


def macro_calls(text):
    """The calls and constants a macro written by macro_text holds, read
    without running it (it is Python: only literals are taken)."""
    tree = ast.parse(text)
    consts, calls = {}, []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                consts[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            if isinstance(f, ast.Attribute) and f.attr == "run" and len(node.value.args) == 2:
                calls.append(node.value)
    return consts, calls


def macro_dir():
    import FreeCAD

    try:
        d = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Macro").GetString("MacroPath", "")
    except Exception:
        d = ""
    if not d:
        try:
            d = FreeCAD.getUserMacroDir(True)
        except Exception:
            d = os.path.join(FreeCAD.getUserAppDataDir(), "Macro")
    return d


def macro_path(name):
    n = str(name)
    return os.path.join(macro_dir(), n if n.endswith(".py") else f"{n}.FCMacro")


def about(text):
    """A macro's line about itself: FreeCAD's macro metadata __Comment__
    when it has one, else its first comment line."""
    m = re.search(r"^__Comment__\s*=\s*(['\"])(.*?)\1", text, re.M)
    if m:
        return m.group(2).strip()
    for line in text.splitlines():
        if line.startswith("# ") and "coding" not in line:
            return line[2:].strip()
    return ""


def with_params(text, params):
    """The macro's source with its named constants set to params (only
    top-level NAME = literal lines; the rest is the approved code as it is)."""
    tree = ast.parse(text)
    known = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            n = node.targets[0].id
            # Only a constant the person wrote as a plain value (a number, a
            # string, a list of them): never an expression, a call or a
            # path built in code, which the approval did not cover as data.
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError, RecursionError):
                continue
            if n in params:
                v = params[n]
                try:
                    ast.literal_eval(repr(v))
                except (ValueError, SyntaxError):
                    continue
                node.value = ast.Constant(params[n]) if not isinstance(params[n], (list, dict)) else ast.parse(repr(params[n]), mode="eval").body
                known.add(n)
    missing = [k for k in params if k not in known]
    return ast.fix_missing_locations(tree), missing


def listing():
    """The macros FreeCAD's Macro dialog lists in its macro folder (.FCMacro
    and .py), each approved, changed or not."""
    d = macro_dir()
    rows = []
    try:
        files = sorted(f for f in os.listdir(d) if f.lower().endswith((".fcmacro", ".py")) and os.path.isfile(os.path.join(d, f)))
    except OSError:
        files = []
    for f in files:
        name = f[: -len(".FCMacro")] if f.lower().endswith(".fcmacro") else f
        if not macro_name_ok(name):
            continue
        p = os.path.join(d, f)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                first = about(fh.read(20000))
        except OSError:
            first = ""
        rows.append({"name": name, "state": approval_state(name, p), **({"about": first[:160]} if first else {})})
    return d, rows
