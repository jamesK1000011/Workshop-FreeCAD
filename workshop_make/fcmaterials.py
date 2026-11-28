# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD's own material library (the Material workbench's cards) as
Make's Materials tab uses it. Browsing and editing the library is FreeCAD's
(its Material editor, Material_Edit, and Std_SetMaterial on a part); Make
keeps only what FreeCAD lacks, its printing filaments as printed and the
materials each process assumes, and here:

- reads a metal's Young's modulus and yield strength from FreeCAD's card
  for it (none are written in Make: no card, no figure);
- gives a part FreeCAD's material (its ShapeMaterial) when Make gives it a
  filament, so FreeCAD's Inspect Material names the same material Make
  does;
- reads a part's ShapeMaterial back, so a material set with FreeCAD's own
  command is the one Make weighs the part with.

Everything is guarded: without the Materials module (an older FreeCAD, or
no FreeCAD) each answers None and Make goes on with its own data. The
matching and unit reading are pure Python (tested without FreeCAD)."""

import re

# A filament's FreeCAD card: the person's own card named as the filament is
# (made in the Material editor), else FreeCAD's card for the same plastic
# (bulk, not printed: Make keeps the printed figures). None for a plastic
# FreeCAD has no card for.
FILAMENT_CARDS = {"pla": ("PLA-Generic",), "abs": ("ABS-Generic",)}

PA_PER = {"pa": 1e-6, "kpa": 1e-3, "mpa": 1.0, "gpa": 1000.0, "n/mm^2": 1.0, "n/mm2": 1.0}
DENSITY_PER = {"kg/m^3": 1e-3, "kg/m3": 1e-3, "g/cm^3": 1.0, "g/cm3": 1.0, "kg/mm^3": 1e6, "g/mm^3": 1e3, "t/mm^3": 1e9}


def _manager():
    try:
        import Materials

        return Materials.MaterialManager()
    except Exception:  # noqa: BLE001
        return None


def cards():
    """{name: material} of FreeCAD's library, or {} without it."""
    mm = _manager()
    if mm is None:
        return {}
    try:
        mats = mm.Materials
        vals = mats.values() if hasattr(mats, "values") else mats
        return {str(m.Name): m for m in vals if getattr(m, "Name", None)}
    except Exception:  # noqa: BLE001
        return {}


def match(names, wants):
    """The first of wants found among names: an exact name, then a name
    holding it (case alike), sorted so the pick is stable. None if none."""
    names = sorted(str(n) for n in names)
    low = {n.lower(): n for n in names}
    for w in wants or ():
        if str(w).lower() in low:
            return low[str(w).lower()]
    for w in wants or ():
        hit = next((n for n in names if str(w).lower() in n.lower()), None)
        if hit:
            return hit
    return None


def quantity(text, per):
    """A card's value as a number in Make's unit: "200 GPa" -> 200000.0
    with PA_PER (MPa), "7900 kg/m^3" -> 7.9 with DENSITY_PER (g/cm³).
    None when the unit is not one of per's."""
    if text is None:
        return None
    if hasattr(text, "getValueAs"):  # a FreeCAD Quantity
        try:
            q = text.getValueAs("MPa" if per is PA_PER else "g/cm^3")
            return float(getattr(q, "Value", q))
        except Exception:  # noqa: BLE001
            text = getattr(text, "UserString", str(text))
    m = re.match(r"^\s*([-+0-9.eE]+)\s*(.*?)\s*$", str(text))
    if not m:
        return None
    try:
        v = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).replace(" ", "").replace("³", "^3").replace("²", "^2").lower()
    f = per.get(unit)
    return None if f is None else v * f


def _prop(mat, name):
    try:
        if hasattr(mat, "hasPhysicalProperty") and not mat.hasPhysicalProperty(name):
            return None
    except Exception:  # noqa: BLE001
        pass
    try:
        if hasattr(mat, "getPhysicalValue"):
            v = mat.getPhysicalValue(name)
            if v not in (None, ""):
                return v
    except Exception:  # noqa: BLE001
        pass
    try:
        return (getattr(mat, "PhysicalProperties", None) or {}).get(name)
    except Exception:  # noqa: BLE001
        return None


def figures(mat):
    """{card, density g/cm³, E MPa, yield MPa} from a FreeCAD card; a
    figure the card does not carry is left out."""
    out = {"card": str(getattr(mat, "Name", ""))}
    for key, prop, per in (("density", "Density", DENSITY_PER), ("E", "YoungsModulus", PA_PER), ("yield", "YieldStrength", PA_PER)):
        v = quantity(_prop(mat, prop), per)
        if v is not None:
            out[key] = round(v, 4 if key == "density" else 1)
    return out


def metal(wants, library=None):
    """FreeCAD's figures for a metal (its card names to try, from
    shop-materials.json's freecadCards), or None when FreeCAD has no such
    card here."""
    lib = cards() if library is None else library
    name = match(lib, wants)
    return figures(lib[name]) if name else None


def filament_card(key, display=None, library=None):
    """The FreeCAD card that stands for a filament, or None."""
    lib = cards() if library is None else library
    own = [display] if display else []
    own += [str(key), str(key).upper()]
    low = {n.lower(): n for n in lib}
    for w in own:
        if w and w.lower() in low:
            return low[w.lower()]
    return match(lib, FILAMENT_CARDS.get(str(key).lower(), ()))


# FreeCAD's own default material ("Default", 1 kg/m³: FreeCAD 1.1 source,
# src/Mod/Material/Resources/Materials/Standard/Default.FCMat), the one
# every new part carries until a person or Make gives it another.
DEFAULT_UUID = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"


def _default_uuid():
    """The UUID of FreeCAD's default material. FreeCAD 1.1's Python
    MaterialManager has no defaultMaterial() (src/Mod/Material/App/
    MaterialManagerPyImp.cpp lists getMaterial, getMaterialByPath,
    inheritMaterial …), so it is read as FreeCAD's own C++ does
    (MaterialManager::defaultMaterialUUID): the preference
    Mod/Material/DefaultMaterial, else DEFAULT_UUID. A manager that does
    have defaultMaterial() is asked first."""
    mm = _manager()
    if mm is None:
        return None
    try:
        return mm.defaultMaterial().UUID
    except Exception:  # noqa: BLE001 — FreeCAD 1.1: no such method
        pass
    try:
        import FreeCAD

        v = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Material").GetString("DefaultMaterial", DEFAULT_UUID)
        return v if isinstance(v, str) and v else DEFAULT_UUID
    except Exception:  # noqa: BLE001
        return DEFAULT_UUID


def _default_material():
    """FreeCAD's default material itself, or None."""
    mm = _manager()
    if mm is None:
        return None
    try:
        return mm.defaultMaterial()
    except Exception:  # noqa: BLE001 — FreeCAD 1.1: by its UUID
        pass
    for uuid in dict.fromkeys((_default_uuid(), DEFAULT_UUID)):
        try:
            m = mm.getMaterial(uuid)
            if m is not None:
                return m
        except Exception:  # noqa: BLE001
            continue
    return None


def give(obj, key, display=None):
    """Set obj's ShapeMaterial to the FreeCAD card for filament key. Answers
    the card's name, or why not (None, {reason, …})."""
    if not hasattr(obj, "ShapeMaterial"):
        return None, {"reason": "noShapeMaterial"}
    lib = cards()
    name = filament_card(key, display, lib)
    if name is None:
        return None, {"reason": "noCard", "card": display or key}
    try:
        obj.ShapeMaterial = lib[name]
    except Exception as e:  # noqa: BLE001
        return None, {"reason": "refused", "error": str(e)}
    return name, None


def clear(obj):
    """obj back to FreeCAD's default material. True when done."""
    m = _default_material() if hasattr(obj, "ShapeMaterial") else None
    if m is None:
        return False
    try:
        obj.ShapeMaterial = m
        return True
    except Exception:  # noqa: BLE001
        return False


def of(obj):
    """The figures of the FreeCAD material a part was given (Std_SetMaterial
    or Make), or None for none or FreeCAD's default."""
    m = getattr(obj, "ShapeMaterial", None)
    if m is None:
        return None
    try:
        uuid = getattr(m, "UUID", None)
        if not uuid or uuid in (_default_uuid(), DEFAULT_UUID):
            return None
    except Exception:  # noqa: BLE001
        return None
    return figures(m)
