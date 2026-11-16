# SPDX-License-Identifier: LGPL-2.1-or-later
"""Is Fasteners Workbench (Shai Seger's, shaise/FreeCAD_FastenersWB) installed?

Cheap on purpose: folder listings and three file checks, no FreeCAD module
imported, nothing of Fasteners imported. Asked once, remembered. Fasteners
is a separate add-on the person may or may not have; Workshop never copies
its code or data, it calls it at run time (workshop_fasteners.fs).

A folder is Fasteners when it holds FastenerBase.py, ScrewMaker.py and
FastenersCmd.py (what we import), or its package.xml names the workbench
class FastenersWorkbench and those files are there. Looked for, in order:

1. WORKSHOP_FASTENERS: a folder to use, or "off" (tests; a person who
   wants the bridge off);
2. a folder on sys.path (FreeCAD puts each Mod folder there);
3. every folder of the Mod folders: the one Workshop is installed in, and
   FreeCAD's user Mod folders (any name: the Addon Manager installs it as
   Mod/fasteners, a git clone may be FreeCAD_FastenersWB).

Absent: one debug line (FreeCAD's log level) and nothing else."""
import os
import re
import sys

NEEDED = ("FastenerBase.py", "ScrewMaker.py", "FastenersCmd.py")
CLASSNAME = "FastenersWorkbench"
ENV = "WORKSHOP_FASTENERS"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The credit wherever Fasteners' parts are used.
CREDIT = "Fasteners Workbench by Shai Seger (shaise), screw_maker by Ulrich Brammer (LGPL-2.1-or-later)"

_UNSET = object()
_found = _UNSET


def _has_code(d):
    return all(os.path.isfile(os.path.join(d, f)) for f in NEEDED)


def _package(d):
    """(names its workbench class, version, date) from d/package.xml."""
    p = os.path.join(d, "package.xml")
    try:
        with open(p, encoding="utf-8") as f:
            text = f.read(20000)
    except OSError:
        return False, None, None
    v = re.search(r"<version>\s*([^<\s]+)\s*</version>", text)
    dt = re.search(r"<date>\s*([^<\s]+)\s*</date>", text)
    return (f"<classname>{CLASSNAME}</classname>" in text), (v.group(1) if v else None), (dt.group(1) if dt else None)


def is_fasteners(d):
    """d is Fasteners Workbench's folder and its code is there."""
    if not d or not os.path.isdir(d) or not _has_code(d):
        return False
    return True


def _mod_dirs():
    out = [os.path.dirname(ROOT)]
    fc = sys.modules.get("FreeCAD")  # only when FreeCAD is loaded already
    for name in ("getUserAppDataDir", "getUserModDir"):
        fn = getattr(fc, name, None) if fc is not None else None
        try:
            p = fn() if callable(fn) else None
        except Exception:  # noqa: BLE001
            p = None
        if isinstance(p, str) and p:
            out += [p if name == "getUserModDir" else os.path.join(p, "Mod"), os.path.join(os.path.dirname(p.rstrip("/\\")), "Mod")]
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "Library", "Application Support", "FreeCAD"), os.path.join(home, ".local", "share", "FreeCAD"),
                 os.path.join(home, ".FreeCAD"), os.path.join(os.environ.get("APPDATA", ""), "FreeCAD") if os.environ.get("APPDATA") else None):
        if not base or not os.path.isdir(base):
            continue
        out.append(os.path.join(base, "Mod"))
        try:  # FreeCAD 1.1's versioned folders (v1-1/Mod)
            out += [os.path.join(base, v, "Mod") for v in sorted(os.listdir(base), reverse=True) if v.startswith("v")]
        except OSError:
            pass
    seen, uniq = set(), []
    for d in out:
        k = os.path.normcase(os.path.abspath(d))
        if k not in seen and os.path.isdir(d):
            seen.add(k)
            uniq.append(d)
    return uniq


def _info(d):
    names, version, date = _package(d)
    return {"path": os.path.abspath(d), "version": version, "date": date, "packageXml": names}


def _search():
    env = os.environ.get(ENV, "").strip()
    if env.lower() in ("off", "0", "no", "none"):
        return None
    if env:
        return _info(env) if is_fasteners(env) else None
    for d in list(sys.path):
        if d and is_fasteners(d):
            return _info(d)
    for m in _mod_dirs():
        try:
            names = os.listdir(m)
        except OSError:
            continue
        # The likely names first: Mod/fasteners (Addon Manager), then any folder.
        for n in sorted(names, key=lambda n: ("fastener" not in n.lower(), n.lower())):
            d = os.path.join(m, n)
            if is_fasteners(d):
                return _info(d)
    return None


def _debug(text):
    fc = sys.modules.get("FreeCAD")
    try:
        fc.Console.PrintLog(text)
    except Exception:  # noqa: BLE001 — no FreeCAD: say nothing
        pass


def find(refresh=False):
    """{path, version, date, packageXml} of the Fasteners Workbench found, or
    None. Remembered after the first ask (refresh=True asks again)."""
    global _found
    if _found is _UNSET or refresh:
        try:
            _found = _search()
        except Exception:  # noqa: BLE001 — never in the way
            _found = None
        if _found is None:
            _debug("Workshop: Fasteners Workbench not installed; the fasteners bridge stays off.\n")
    return _found


def present():
    return find() is not None


def reset():
    global _found
    _found = _UNSET


# ---- a Fasteners object, told without loading Fasteners ---------------------------------

FS_MODULES = ("FastenersCmd", "PEMInserts", "FastenerBase")


def is_fastener(obj):
    """A Fasteners Workbench part (screw, nut, washer, insert, pin …): its
    proxy is one of Fasteners' classes, or (a document saved where Fasteners
    was not loaded) it has their properties. Its countersunk-hole object is
    a cut part, not hardware."""
    p = getattr(obj, "Proxy", None)
    mod = getattr(type(p), "__module__", "") if p is not None else ""
    if mod in FS_MODULES:
        return True
    try:
        props = set(getattr(obj, "PropertiesList", ()) or ())
    except Exception:  # noqa: BLE001
        return False
    return {"Type", "Diameter", "Invert", "BaseObject"} <= props and "diameters" not in props
