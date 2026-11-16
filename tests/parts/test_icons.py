# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's icons (design 5): InitGui adds its icons folder, the bench's
# Icon is a file there, every command's Pixmap is one of its SVGs or a FreeCAD
# icon used by name, each SVG is a 64x64 drawing in the Tango palette, and
# CREDITS.md, REUSE.toml, LICENSES/ and package.xml's <icon> go with them.
import glob
import json
import os
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = "workshop_parts"
ICONS = os.path.join(ROOT, PKG, "icons")

# FreeCAD's own icons the commands name, resolved by FreeCAD at runtime.
FREECAD_ICONS = {"document-new", "document-open", "list-add", "list-remove", "media-playback-pause", "Std_Export",
                 "PartDesign_Hole", "PartDesign_Pocket", "TechDraw_PageDefault", "TechDraw_ProjectionGroup",
                 "preferences-system", "edit-undo"}
TANGO = set("""fce94f edd400 c4a000 fcaf3e f57900 ce5c00 e9b96e c17d11 8f5902 8ae234 73d216 4e9a06
729fcf 3465a4 204a87 ad7fa8 75507b 5c3566 ef2929 cc0000 a40000 34e0e2 16d0d2 06989a eeeeec d3d7cf babdb6 888a85 555753 2e3436""".split())

HARNESS = r'''
import json, sys, types

class Stub(types.ModuleType):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        v = Stub(f"{self.__name__}.{k}")
        setattr(self, k, v)
        return v
    def __call__(self, *a, **k):
        return Stub(self.__name__ + "()")

said, commands, benches, paths = [], {}, [], []
FreeCAD = Stub("FreeCAD")
FreeCAD.Console = types.SimpleNamespace(PrintMessage=said.append, PrintWarning=said.append, PrintError=said.append, PrintLog=lambda m: None)
FreeCAD.ActiveDocument = None
Gui = Stub("FreeCADGui")

class Workbench:
    def appendToolbar(self, name, cmds): pass
    def appendMenu(self, name, cmds): pass

Gui.Workbench = Workbench
Gui.addCommand = lambda name, c: commands.__setitem__(name, c)
Gui.addWorkbench = benches.append
Gui.addIconPath = paths.append
sys.modules.update({"FreeCAD": FreeCAD, "FreeCADGui": Gui})
for n in ("Part", "Mesh", "MeshPart", "Sketcher", "TechDraw", "TechDrawGui", "PySide", "PySide.QtGui", "PySide.QtCore"):
    sys.modules[n] = Stub(n)
path = sys.argv[1]
sys.path.insert(0, path)
# As FreeCAD runs it: its globals hold only FreeCAD, FreeCADGui and the
# builtins, and InitGui's own names land in a separate locals dict.
exec(compile(open(path + "/InitGui.py", encoding="utf-8").read(), path + "/InitGui.py", "exec"),
     {"__builtins__": __builtins__, "FreeCAD": FreeCAD, "FreeCADGui": Gui}, {})
print(json.dumps({"said": said, "paths": paths, "icons": [b.Icon for b in benches],
                  "pixmaps": {k: c.GetResources().get("Pixmap") for k, c in commands.items()}}))
'''


def load():
    r = subprocess.run([sys.executable, "-I", "-c", HARNESS, ROOT], capture_output=True, text=True,
                       env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}, cwd=ROOT)
    if r.returncode:
        raise AssertionError(r.stderr[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def svgs():
    return sorted(glob.glob(os.path.join(ICONS, "*.svg")))


class Icons(unittest.TestCase):
    def test_every_pixmap_resolves(self):
        out = load()
        self.assertEqual(out["said"], [])
        self.assertIn(ICONS, out["paths"])  # one folder per part of the add-on
        [icon] = out["icons"]
        self.assertTrue(os.path.isfile(icon), icon)
        self.assertTrue(out["pixmaps"])
        for name, pix in out["pixmaps"].items():
            self.assertTrue(pix, name)
            self.assertTrue(any(os.path.isfile(os.path.join(d, pix + ".svg")) for d in out["paths"]) or pix in FREECAD_ICONS, f"{name}: {pix}")

    def test_svgs_in_freecad_style(self):
        self.assertTrue(svgs())
        for f in svgs():
            s = open(f, encoding="utf-8").read()
            r = ET.fromstring(s)
            self.assertEqual(r.get("viewBox"), "0 0 64 64", f)
            self.assertEqual({h.lower() for h in re.findall(r"#([0-9a-fA-F]{6})\b", s)} - TANGO, set(), f)
            self.assertIsNone(re.search(r"<text|<image|xlink:href|data:", s), f)

    def test_credits_and_licences(self):
        credits = open(os.path.join(ICONS, "CREDITS.md"), encoding="utf-8").read()
        for f in svgs():
            self.assertIn(os.path.basename(f), credits)
        for lic in ("MIT.txt", "Apache-2.0.txt"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "LICENSES", lic)), lic)
        self.assertIn(f'"{PKG}/icons/*.svg"', open(os.path.join(ROOT, "REUSE.toml"), encoding="utf-8").read())
        icons = [e.text for e in ET.parse(os.path.join(ROOT, "package.xml")).iter("{https://wiki.freecad.org/Package_Metadata}icon")]
        self.assertTrue(icons)
        for i in icons:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, i)), i)


if __name__ == "__main__":
    unittest.main()
