# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make's own copy of Agent Link for FreeCAD's ccx_io.py, trimmed to what Make uses; 14 Nov 2026.
# CalculiX's files, as much as a linear static solve needs: the mesh part
# of an Abaqus/CalculiX input deck (as FreeCAD's FemMesh.writeABAQUS writes
# it), the loads and supports added to it, and the nodal results read back
# from the .frd. Plain Python, no FreeCAD, so it is tested anywhere.
# Units: mm, N, MPa, tonne/mm³ (CalculiX takes any consistent set).

import math


def _rows(ids, per=12):
    ids = list(ids)
    return "\n".join(", ".join(str(i) for i in ids[j:j + per]) for j in range(0, len(ids), per))


def read_frd(text):
    """The last step's nodal DISP {node: (ux,uy,uz)} and STRESS
    {node: (sxx,syy,szz,sxy,syz,szx)} from an ASCII .frd."""
    disp, stress = {}, {}
    block = None
    for line in text.splitlines():
        if line.startswith(" -4"):
            name = line[5:13].strip()
            block = {"DISP": disp, "STRESS": stress}.get(name)
            if block is not None:
                block.clear()
            continue
        if line.startswith(" -3"):
            block = None
            continue
        if block is not None and line[1:3] == "-1":
            nid = int(line[3:13])
            s = line.rstrip("\r\n")
            block[nid] = tuple(float(s[p:p + 12]) for p in range(13, len(s), 12) if s[p:p + 12].strip())
    return disp, stress


def von_mises(s):
    sxx, syy, szz, sxy, syz, szx = s[:6]
    return math.sqrt(0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3.0 * (sxy ** 2 + syz ** 2 + szx ** 2))


def normal_stress(s, n):
    """The normal stress along the unit direction n."""
    sxx, syy, szz, sxy, syz, szx = s[:6]
    x, y, z = n
    return sxx * x * x + syy * y * y + szz * z * z + 2 * (sxy * x * y + syz * y * z + szx * z * x)




# ---- several parts: each its own material, tied or in contact -------------------------


def find_binary(name, pref_group, pref_key, env):
    """A solver's command line: the environment variable env, else FreeCAD's
    FEM preference (Mod/Fem/<pref_group> <pref_key>), else name on the PATH;
    None when none is found."""
    import os
    import shutil

    p = os.environ.get(env)
    if p and shutil.which(p):
        return shutil.which(p)
    try:
        import FreeCAD

        q = FreeCAD.ParamGet(f"User parameter:BaseApp/Preferences/Mod/Fem/{pref_group}").GetString(pref_key, "")
        if q and shutil.which(q):
            return shutil.which(q)
    except Exception:  # noqa: BLE001 — no FreeCAD here, or no such preference
        pass
    return shutil.which(name)
