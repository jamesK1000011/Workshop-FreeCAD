# SPDX-License-Identifier: LGPL-2.1-or-later
# Runs code in a fresh Python with stand-ins for FreeCAD (no window: no
# FreeCADGui at all, so the bridge's own stand-in is the one used), Part
# and DraftVecUtils, a document whose FeaturePython objects keep
# properties the way FreeCAD's do (an enumeration takes a list as its
# choices and a string as its value), and this add-on on the path.
# Fasteners Workbench itself is the reference clone (FASTENERS_SRC, else
# /tmp/fwb), loaded through the bridge, never copied. run(code, fasteners)
# -> what the code put in OUT; fasteners: the folder, or "off".
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.environ.get("FASTENERS_SRC") or "/tmp/fwb"


def have_fasteners():
    return all(os.path.isfile(os.path.join(SRC, f)) for f in ("FastenerBase.py", "ScrewMaker.py", "FastenersCmd.py"))


PRELUDE = r'''
import json, sys, types

logs, errs = [], []
class Param:
    def __init__(self): self.d = {}
    def GetInt(self, k, d=0): return self.d.get(k, d)
    def GetBool(self, k, d=False): return self.d.get(k, d)
    def GetFloat(self, k, d=0.0): return self.d.get(k, d)
    def GetUnsigned(self, k, d=0): return self.d.get(k, d)
    def GetString(self, k, d=""): return self.d.get(k, d)
    def SetInt(self, k, v): self.d[k] = v
    def SetBool(self, k, v): self.d[k] = v
    def SetFloat(self, k, v): self.d[k] = v
PARAMS = {}

class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0): self.x, self.y, self.z = float(x), float(y), float(z)
    def __add__(self, o): return Vec(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o): return Vec(self.x - o.x, self.y - o.y, self.z - o.z)
    def __mul__(self, k): return Vec(self.x * k, self.y * k, self.z * k)
    def dot(self, o): return self.x * o.x + self.y * o.y + self.z * o.z
    def cross(self, o): return Vec(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)
    @property
    def Length(self): return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
    def normalize(self):
        n = self.Length
        self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
        return self

class Placement:
    def __init__(self, *a): self.Base = Vec()

class Quantity(float):
    @property
    def Value(self): return float(self)

FreeCAD = types.ModuleType("FreeCAD")
FreeCAD.GuiUp = False
FreeCAD.Version = lambda: ["1", "1", "3", "", "", "FreeCAD"]
FreeCAD.Qt = types.SimpleNamespace(translate=lambda ctx, t, *a: t)
FreeCAD.ParamGet = lambda path: PARAMS.setdefault(path, Param())
FreeCAD.Console = types.SimpleNamespace(PrintLog=logs.append, PrintMessage=logs.append, PrintWarning=errs.append, PrintError=errs.append)
FreeCAD.Vector = Vec
FreeCAD.Placement = Placement
FreeCAD.Base = types.SimpleNamespace(Vector=Vec)
FreeCAD.Units = types.SimpleNamespace(Quantity=Quantity)
FreeCAD.listDocuments = lambda: {}
sys.modules["FreeCAD"] = FreeCAD
class Lax(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return type(k, (), {})
for n in ("Part", "DraftVecUtils"):
    sys.modules[n] = Lax(n)

ENUM = "App::PropertyEnumeration"

class FP:
    """A Part::FeaturePython as far as Fasteners' FSScrewObject uses one."""
    def __init__(self, name):
        object.__setattr__(self, "_p", {})
        object.__setattr__(self, "_enum", {})
        object.__setattr__(self, "Name", name)
        object.__setattr__(self, "Label", name)
        object.__setattr__(self, "Placement", Placement())
        object.__setattr__(self, "Visibility", True)
        object.__setattr__(self, "InList", [])
        object.__setattr__(self, "TypeId", "Part::FeaturePython")
    def addProperty(self, t, name, group="", doc=""):
        self._p[name] = t
        object.__setattr__(self, name, [] if t == ENUM else (False if t == "App::PropertyBool" else (0.0 if "Distance" in t or "Length" in t or "Angle" in t else None)))
        return self
    def __setattr__(self, k, v):
        if self._p.get(k) == ENUM:
            if isinstance(v, list):
                self._enum[k] = [str(x) for x in v]
                v = self._enum[k][0] if self._enum[k] else ""
            elif str(v) not in self._enum.get(k, []):
                raise ValueError(f"{k}: {v!r} is not one of {self._enum.get(k)}")
        object.__setattr__(self, k, v)
    @property
    def PropertiesList(self): return list(self._p)
    def getTypeIdOfProperty(self, k): return self._p.get(k)
    def removeProperty(self, k): self._p.pop(k, None)
    def getEnumerationsOfProperty(self, k): return list(self._enum.get(k, []))
    def setEditorMode(self, *a): pass
    def recompute(self): pass

class Circle:
    def __init__(self, c, ax, r): self.Center, self.Axis, self.Radius = c, ax, r

class Edge:
    def __init__(self, c, ax, r): self.Curve = Circle(c, ax, r)

class Solid:
    def __init__(self, edges): self.Edges = edges

class Plate:
    """A solid with round edges: Edge1 (top of a hole at 0,0,10, r 1.7) …"""
    def __init__(self, name, edges):
        self.Name = self.Label = name
        self.Shape = Solid(edges)
        self.Visibility, self.InList, self.TypeId = True, [], "Part::Feature"
        self.PropertiesList = ["Placement", "Shape"]
    def getSubObject(self, sub):
        i = int(sub[4:]) - 1
        return self.Shape.Edges[i] if sub.startswith("Edge") and 0 <= i < len(self.Shape.Edges) else None
    def getParentGeoFeatureGroup(self): return None

class Doc:
    def __init__(self):
        self.Objects, self.Name, self.recomputes = [], "Doc", 0
    def addObject(self, t, name):
        n, k = name, 1
        while any(o.Name == n for o in self.Objects):
            k += 1; n = f"{name}{k:03d}"
        o = FP(n)
        self.Objects.append(o)
        return o
    def recompute(self):
        """What a recompute does to a fastener's choices (FSScrewObject.execute
        refills Length for the diameter; the shape itself is not made here)."""
        self.recomputes += 1
        import ScrewMaker
        for o in self.Objects:
            if isinstance(o, FP) and "Length" in o._enum and o.Diameter not in ("Auto", "Custom"):
                lens = [str(x) for x in ScrewMaker.Instance.GetAllLengths(o.Type, o.Diameter, "LengthCustom" in o._p)]
                if lens != o._enum["Length"]:
                    old = o.Length
                    o.Length = lens
                    if old in lens:
                        o.Length = old
    def getObjectsByLabel(self, l): return [o for o in self.Objects if o.Label == l]

sys.path.insert(0, sys.argv[1])
OUT = {}
'''


def run(code, fasteners=None):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "HOME": "/nonexistent-home",
           "WORKSHOP_FASTENERS": fasteners if fasteners else SRC}
    src = PRELUDE + code + "\nOUT['logs'] = [str(x) for x in logs]\nOUT['errs'] = [str(x) for x in errs]\nprint(json.dumps(OUT, default=str))\n"
    r = subprocess.run([sys.executable, "-I", "-c", src, ROOT], capture_output=True, text=True, env=env, cwd="/")
    if r.returncode:
        raise AssertionError(r.stderr[-4000:])
    out = json.loads(r.stdout.strip().splitlines()[-1])
    out["stderr"] = r.stderr
    return out
