# SPDX-License-Identifier: LGPL-2.1-or-later
"""Old copies beside the one add-on: the separate WorkshopParts,
WorkshopMake, WorkshopElectronics, WorkshopDocuments and SafetyNet Mod
folders from before the combine carry packages of the same names
(workshop_make, safetynet, …). FreeCAD puts every Mod folder on the path,
and theirs come first alphabetically, so their old packages would be the
ones imported: no families module, no startup, a second Make workbench.

prefer_own() puts this add-on's folder first on the path, drops any of
those packages already imported from elsewhere, and says once, in one line,
which old folders it found. It never touches the Mod folder: Agent Link's
update sets the old folders aside."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Mod folder -> the <name> in its package.xml, for the add-ons now inside
# this one (the launcher's RETIRED list says the same).
OLD = {
    "WorkshopParts": "Workshop Parts",
    "WorkshopMake": "Workshop Make",
    "WorkshopElectronics": "Workshop Electronics",
    "WorkshopDocuments": "Workshop Documents",
    "SafetyNet": "SafetyNet",
}
PACKAGES = ("workshop_parts", "workshop_make", "workshop_electronics", "workshop_documents", "safetynet")
_said = []


def found(mod_dir=None):
    """The old folders beside this add-on whose package.xml says they are
    the old add-ons."""
    mod_dir = mod_dir or os.path.dirname(ROOT)
    out = []
    for d, name in OLD.items():
        try:
            with open(os.path.join(mod_dir, d, "package.xml"), encoding="utf-8") as f:
                xml = f.read()
        except OSError:
            continue
        i, j = xml.find("<name>"), xml.find("</name>")
        if i >= 0 and name in xml[i + 6:j] and os.path.realpath(os.path.join(mod_dir, d)) != os.path.realpath(ROOT):
            out.append(d)
    return out


def _own(mod):
    f = getattr(mod, "__file__", None) or ""
    return os.path.realpath(f).startswith(os.path.realpath(ROOT) + os.sep)


def prefer_own(mod_dir=None, warn=None):
    """This add-on's packages win over old copies; one line said when there
    are old folders. Returns the old folders found."""
    if ROOT in sys.path:
        sys.path.remove(ROOT)
    sys.path.insert(0, ROOT)
    for name in list(sys.modules):
        if name.split(".")[0] in PACKAGES and not _own(sys.modules[name]):
            del sys.modules[name]
    old = found(mod_dir)
    if old and not _said:
        _said.append(True)
        line = (f"Workshop: old {', '.join(old)} folder{'s' if len(old) > 1 else ''} found beside Workshop in "
                f"{mod_dir or os.path.dirname(ROOT)}; they are now inside Workshop. Run Agent Link's update "
                f"(agentlink_update) to set them aside, or remove them, then restart FreeCAD.\n")
        (warn or _warn)(line)
    return old


def _warn(text):
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(text)
    except Exception:  # noqa: BLE001
        sys.stderr.write(text)
