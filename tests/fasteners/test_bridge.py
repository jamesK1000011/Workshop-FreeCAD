# SPDX-License-Identifier: LGPL-2.1-or-later
# The Fasteners bridge. Absent: no tools, no group, no guide, no Agent Link
# import, one debug line, nothing on stderr. Present (the reference clone of
# Fasteners Workbench, FASTENERS_SRC or /tmp/fwb; skipped without it): found
# cheaply (lowercase Mod/fasteners too), loaded without a window through its
# own modules, its types, sizes, lengths, insert table; fasteners added on
# round edges and loose, changed, counted; the screw for a hole; the echo
# declarations against Fasteners' own workbench and commands.
import ast
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _fwb import ROOT, SRC, have_fasteners, run  # noqa: E402

sys.path.insert(0, ROOT)
HAVE = have_fasteners()

# Agent Link stood in for: ToolError, the hooks the bridge uses.
AGENTLINK = r'''
import types
al = types.ModuleType("agentlink"); al.__path__ = []
prot = types.ModuleType("agentlink.protocol")
class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message); self.code, self.message = code, message
prot.ToolError = ToolError
hooks = types.ModuleType("agentlink.hooks")
EXT = []
hooks.extend_tool = lambda name, properties=None, before=None, after=None, describe=None: EXT.append((name, properties, after, describe))
hooks.tools_from_data = lambda folder, group, handlers, who: [(n, group, folder) for n in handlers]
al.protocol, al.hooks = prot, hooks
sys.modules.update({"agentlink": al, "agentlink.protocol": prot, "agentlink.hooks": hooks})
'''


class Absent(unittest.TestCase):
    def test_dormant(self):
        out = run(r'''
from workshop_fasteners import detect, families
OUT["present"] = detect.present()
OUT["families"] = families.FAMILIES
OUT["loaded"] = sorted(m for m in sys.modules if m.startswith(("workshop_fasteners.fam_", "workshop_fasteners.api", "workshop_fasteners.fs", "agentlink", "FastenerBase", "ScrewMaker")))
OUT["again"] = detect.find() is None
''', fasteners="off")
        self.assertFalse(out["present"])
        self.assertEqual(out["families"], [])
        self.assertEqual(out["loaded"], [])
        self.assertTrue(out["again"])
        self.assertEqual(len(out["logs"]), 1, out["logs"])  # one debug line, once
        self.assertIn("Fasteners Workbench not installed", out["logs"][0])
        self.assertEqual(out["errs"], [])
        self.assertEqual(out["stderr"], "")

    def test_a_folder_without_its_code_is_not_it(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "package.xml"), "w") as f:
            f.write("<package><content><workbench><classname>FastenersWorkbench</classname></workbench></content></package>")
        out = run('from workshop_fasteners import detect\nOUT["found"] = detect.find()\n', fasteners=d)
        self.assertIsNone(out["found"])

    def test_others_refuse_or_fall_back(self):
        out = run(r'''
from workshop_fasteners import api, fs
try:
    api.types(query="cap")
except fs.Missing as e:
    OUT["refused"] = [e.code, e.message]
OUT["insert"] = api.insert_figures("M3")
OUT["comp"] = api.thread_compensation(3.0)
''', fasteners="off")
        self.assertEqual(out["refused"][0], "unavailable")
        self.assertIn("Addon Manager", out["refused"][1])
        self.assertIsNone(out["insert"])
        self.assertIsNone(out["comp"])

    def test_is_fastener_needs_no_fasteners(self):
        from workshop_fasteners import detect

        Proxy = type("FSScrewObject", (), {"__module__": "FastenersCmd"})
        screw = type("O", (), {"Proxy": Proxy(), "PropertiesList": []})()
        saved = type("O", (), {"Proxy": None, "PropertiesList": ["Type", "Diameter", "Invert", "BaseObject", "Length"]})()
        csk = type("O", (), {"Proxy": None, "PropertiesList": ["Type", "Diameter", "Invert", "BaseObject", "diameters"]})()
        box = type("O", (), {"Proxy": None, "PropertiesList": ["Length", "Width", "Height"]})()
        self.assertEqual([detect.is_fastener(o) for o in (screw, saved, csk, box)], [True, True, False, False])


@unittest.skipUnless(HAVE, f"no Fasteners Workbench reference clone at {SRC}")
class Detect(unittest.TestCase):
    def setUp(self):
        from workshop_fasteners import detect

        self.detect = detect
        self.env = os.environ.pop(detect.ENV, None)
        self.dirs = detect._mod_dirs
        detect.reset()

    def tearDown(self):
        self.detect._mod_dirs = self.dirs
        if self.env is not None:
            os.environ[self.detect.ENV] = self.env
        self.detect.reset()

    def test_lowercase_mod_folder(self):
        mod = tempfile.mkdtemp()
        os.mkdir(os.path.join(mod, "AgentLink-FreeCAD"))
        os.symlink(SRC, os.path.join(mod, "fasteners"))  # as the Addon Manager installs it
        self.detect._mod_dirs = lambda: [mod]
        before = set(sys.modules)
        info = self.detect.find()
        self.assertEqual(info["path"], os.path.join(mod, "fasteners"))
        # The reference clone's own version (upstream moves: 0.6.00, then 0.6.01).
        want = re.search(r"<version>\s*([^<\s]+)\s*</version>", open(os.path.join(SRC, "package.xml"), encoding="utf-8").read()).group(1)
        self.assertEqual(info["version"], want)
        self.assertTrue(info["packageXml"])
        self.assertFalse({"FastenerBase", "ScrewMaker", "FreeCAD"} & (set(sys.modules) - before), "detection imported something")

    def test_workbench_class_is_fasteners_own(self):
        tree = ast.parse(open(os.path.join(SRC, "InitGui.py"), encoding="utf-8").read())
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef) and any("Workbench" in ast.unparse(b) for b in n.bases)]
        self.assertEqual(classes, [self.detect.CLASSNAME])


@unittest.skipUnless(HAVE, f"no Fasteners Workbench reference clone at {SRC}")
class Present(unittest.TestCase):
    def test_loads_without_a_window(self):
        out = run(r'''
from workshop_fasteners import fs
F = fs.load()
OUT["mods"] = [m for m in ("FastenerBase", "ScrewMaker", "FastenersCmd") if m in sys.modules]
OUT["gui_left"] = "FreeCADGui" in sys.modules
OUT["path"] = F.path
''')
        self.assertEqual(out["mods"], ["FastenerBase", "ScrewMaker", "FastenersCmd"])
        self.assertFalse(out["gui_left"], "the stand-in FreeCADGui stayed in sys.modules")
        self.assertEqual(out["path"], SRC)

    def test_types_sizes_lengths(self):
        out = run(r'''
from workshop_fasteners import api
OUT["q"] = api.types(query="socket cap")
OUT["nuts"] = api.types(standard="ISO", kind="nut")
OUT["sizes"] = api.types(ftype="ISO4762")
OUT["m3"] = api.types(ftype="iso4762", size="M3")
OUT["ins"] = api.types(ftype="IUTHeatInsert", size="M3")
''')
        self.assertIn("ISO4762", [t["type"] for t in out["q"]["types"]])
        self.assertTrue(all(t["kind"] == "Nut" for t in out["nuts"]["types"]))
        self.assertIn("M3", out["sizes"]["sizes"])
        self.assertIn("10", out["m3"]["lengths"])
        self.assertEqual(out["m3"]["hole"]["tapHole"], 2.5)
        self.assertIn("Shai Seger", out["m3"]["source"])
        self.assertEqual(out["ins"]["insert"]["hole"], 4)

    def test_insert_figures_from_its_table_only(self):
        out = run(r'''
from workshop_fasteners import api
OUT["m3"] = api.insert_figures("M3")
OUT["m8"] = api.insert_figures("M8")
OUT["heavy"] = [m for m in ("FastenerBase", "ScrewMaker") if m in sys.modules]
''')
        self.assertEqual((out["m3"]["hole"], out["m3"]["depth"]), (4, 5.74))
        self.assertIn("Fasteners Workbench", out["m3"]["source"])
        self.assertIsNone(out["m8"])
        self.assertEqual(out["heavy"], [])

    def test_add_change_list(self):
        out = run(r'''
from workshop_fasteners import api, fs
doc = Doc()
doc.Objects.append(Plate("Plate", [Edge(Vec(0, 0, 10), Vec(0, 0, 1), 1.7), Edge(Vec(0, 0, 0), Vec(0, 0, 1), 1.7)]))
s = api.add(doc, "ISO4762", "M3", 11, edges=["Plate.Edge1", "Plate:Edge2"])
n = api.add(doc, "ISO4032", "M4", at=[5, 5, 0])
OUT["made"] = [api.describe(o) for o in s + n]
api.change(doc, [s[0].Name], length=19, invert=True)
OUT["changed"] = api.describe(s[0])
OUT["list"] = api.listing(doc)
for bad in (lambda: api.add(doc, "ISO4762", "M3", edges=["Plate.Edge9"]), lambda: api.add(doc, "ISO476", "M3"),
            lambda: api.add(doc, "ISO4762", "M99"), lambda: api.change(doc, ["Plate"], length=5)):
    try:
        bad()
    except fs.Missing as e:
        OUT.setdefault("refused", []).append(e.code)
''')
        m = out["made"]
        self.assertEqual([x["attachedTo"] for x in m[:2]], ["Plate.Edge1", "Plate.Edge2"])
        self.assertEqual((m[0]["type"], m[0]["size"], m[0]["length"], m[0]["thread"]), ("ISO4762", "M3", "10", "simple"))
        self.assertEqual(m[2]["at"], [5, 5, 0])
        self.assertNotIn("attachedTo", m[2])
        self.assertEqual((out["changed"]["length"], out["changed"]["invert"]), ("20", True))
        self.assertEqual(out["list"]["bom"], [{"item": "ISO4032 Nut M4", "qty": 1}, {"item": "ISO4762 Screw M3x10", "qty": 1}, {"item": "ISO4762 Screw M3x20", "qty": 1}])
        self.assertEqual(out["refused"], ["invalid_input", "not_found", "not_found", "invalid_input"])

    def test_screw_for_a_hole(self):
        out = run(r'''
from workshop_fasteners import api
doc = Doc()
# A 10 mm plate, M3 clearance through it down from z=10; a counterbore 3.3 deep.
doc.Objects.append(Plate("Plate", [Edge(Vec(0, 0, 10), Vec(0, 0, 1), 1.7), Edge(Vec(0, 0, 0), Vec(0, 0, 1), 1.7),
                                   Edge(Vec(20, 0, 10), Vec(0, 0, 1), 3.0), Edge(Vec(20, 0, 6.7), Vec(0, 0, 1), 3.0), Edge(Vec(20, 0, 6.7), Vec(0, 0, -1), 1.7)]))
OUT["clear"] = api.hole_screw(doc, {"kind": "clearance", "size": "M3", "at": [0, 0, 10], "dir": "-z"}, {"body": "Plate", "through": 10, "sizes": {}}, True)
OUT["cb"] = api.hole_screw(doc, {"kind": "counterbore", "size": "M3", "at": [20, 0, 10], "dir": "-z"}, {"body": "Plate", "through": 10, "sizes": {"cutDepth": 3.3}}, {"type": "ISO4762"})
OUT["nut"] = api.hole_screw(doc, {"kind": "nut_trap", "size": "M3", "at": [0, 0, 10], "dir": "-z"}, {"body": "Plate", "through": 10, "sizes": {}}, True)
OUT["magnet"] = api.hole_screw(doc, {"kind": "magnet", "size": "6x2", "at": [0, 0, 10]}, {"body": "Plate"}, True)
OUT["sketch"] = api.hole_screw(doc, {"kind": "clearance", "size": "M3", "sketch": "S"}, {"body": "Plate"}, True)
OUT["miss"] = api.hole_screw(doc, {"kind": "clearance", "size": "M3", "at": [50, 0, 10]}, {"body": "Plate", "through": 10}, True)
''')
        c = out["clear"]["screw"]
        self.assertEqual((c["attachedTo"], c["size"], c["length"], c["match"], c["invert"]), ("Plate.Edge1", "M3", "10", "outer", False))
        self.assertIn("Shai Seger", c["credit"])
        cb = out["cb"]["screw"]
        self.assertEqual((cb["attachedTo"], cb["lengthNeeded"]), ("Plate.Edge5", 6.7))  # the counterbore's floor, the smaller circle
        n = out["nut"]["screw"]
        self.assertEqual((n["attachedTo"], n["invert"]), ("Plate.Edge2", True))  # from the far side, pointing up
        for k in ("magnet", "sketch", "miss"):
            self.assertIn("screwNote", out[k])

    def test_print_settings_and_compensation(self):
        out = run(r'''
from workshop_fasteners import api
OUT["read"] = api.read_print_settings()
OUT["off"] = api.thread_compensation(6.0)
OUT["set"] = api.print_settings("3dprint", nut=[1.05, 0.1])
OUT["comp"] = api.thread_compensation(6.0)
''')
        self.assertEqual(out["read"]["mode"], "standard")
        self.assertEqual(out["read"]["nut"], [1.03, 0.1])
        self.assertIsNone(out["off"])
        self.assertEqual((out["set"]["mode"], out["set"]["nut"]), ("3dprint", [1.05, 0.1]))
        self.assertEqual(out["comp"][0], 0.4)
        self.assertIn("Fasteners Workbench", out["comp"][1])


@unittest.skipUnless(HAVE, f"no Fasteners Workbench reference clone at {SRC}")
class AgentLinkSide(unittest.TestCase):
    def test_family_tools_echo_and_hole_extension(self):
        out = run(AGENTLINK + r'''
from workshop_fasteners import families
f = families.FAMILIES[0]
OUT["group"], OUT["lean"] = f.GROUP, getattr(f, "LEAN", False)
OUT["wb"], OUT["cmds"], OUT["areas"] = f.WORKBENCHES, f.COMMANDS, f.AREAS
OUT["tools"] = [t[0] for t in f.tools(None)]
OUT["cf"] = [f.command_for("fastener_add", {"type": "ISO4762"}), f.command_for("fastener_set", {"objects": ["S"], "invert": True}),
             f.command_for("fastener_set", {"objects": ["S"], "edge": "P.Edge1"}), f.command_for("fastener_set", {"restore": True}),
             f.command_for("fastener_set", {"objects": ["S"], "length": 12}), f.command_for("fastener_list", {}), f.command_for("fastener_list", {"sheet": True})]
OUT["ext"] = [(e[0], sorted(e[1]), bool(e[3])) for e in EXT]
OUT["credit"] = f.INFO
''')
        self.assertEqual(out["group"], "fasteners")
        self.assertFalse(out["lean"])
        self.assertEqual(out["wb"], {"fastener_": "FastenersWorkbench"})
        self.assertEqual(out["areas"], {"fastener_": "Fasteners"})
        self.assertEqual(out["tools"], ["fastener_types", "fastener_add", "fastener_set", "fastener_list", "fastener_print"])
        self.assertEqual(out["cf"], ["FSISO4762", "Fasteners_Flip", "Fasteners_Move", "Fasteners_RestoreProperties", "Fasteners_ChangeParameters", None, "Fasteners_BOM"])
        self.assertEqual(out["ext"], [["hw_hole", ["screw"], True]])
        self.assertIn("Shai Seger", out["credit"])
        self.assertIn("Ulrich Brammer", out["credit"])
        cmds = fasteners_commands()
        for c in list(out["cmds"].values()) + [x for x in out["cf"] if x]:
            self.assertTrue(c in cmds["named"] or (c.startswith("FS") and c[2:] in cmds["types"]), c)

    def test_hole_after(self):
        out = run(AGENTLINK + r'''
from workshop_fasteners import families
f = families.FAMILIES[0]
doc = Doc()
doc.Objects.append(Plate("Plate", [Edge(Vec(0, 0, 10), Vec(0, 0, 1), 1.7)]))
s = types.SimpleNamespace(doc=doc)
OUT["none"] = f.hole_after({"kind": "clearance"}, {"body": "Plate"}, s)
OUT["with"] = f.hole_after({"kind": "clearance", "size": "M3", "at": [0, 0, 10], "dir": "-z", "screw": True}, {"body": "Plate", "through": 10}, s)
OUT["bad"] = f.hole_after({"kind": "clearance", "size": "M3", "at": [0, 0, 10], "screw": {"type": "NOPE1"}}, {"body": "Plate", "through": 10}, s)
''')
        self.assertIsNone(out["none"])
        self.assertEqual(out["with"]["screw"]["type"], "ISO4762")
        self.assertIn("NOPE1", out["bad"]["screwNote"]["error"])


def fasteners_commands():
    """Every command Fasteners registers, read from its source: the names
    given to (FreeCAD)Gui.addCommand as literals, and its per-type Add
    commands ('FS' + each key of FastenersCmd.FSScrewCommandTable)."""
    named, types_ = set(), set()
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(SRC, fn), encoding="utf-8").read())
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "addCommand" and n.args:
                if isinstance(n.args[0], ast.Constant):
                    named.add(n.args[0].value)
            if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FSScrewCommandTable":
                types_ |= {k.value for k in n.value.keys}
    return {"named": named, "types": types_}


@unittest.skipUnless(HAVE, f"no Fasteners Workbench reference clone at {SRC}")
class Coverage(unittest.TestCase):
    def setUp(self):
        import json

        self.map = json.load(open(os.path.join(ROOT, "workshop_fasteners", "data", "coverage.json"), encoding="utf-8"))
        self.cmds = fasteners_commands()

    def test_every_command_judged(self):
        judged = set(self.map["commands"])
        self.assertEqual(self.cmds["named"] - judged, set(), "a Fasteners command the coverage map does not judge")
        self.assertEqual(judged - self.cmds["named"], set(), "the map judges a command Fasteners no longer has")
        self.assertGreater(len(self.cmds["types"]), 200)
        self.assertEqual(self.map["patterns"]["FS<type>"]["judged"], "tool")
        for v in list(self.map["commands"].values()) + list(self.map["patterns"].values()):
            self.assertIn(v["judged"], ("tool", "window", "n/a"))

    def test_tools_named_exist(self):
        import json

        ours = set(json.load(open(os.path.join(ROOT, "workshop_fasteners", "data", "tools.json"), encoding="utf-8"))["entries"])
        for v in self.map["commands"].values():
            if v["judged"] == "tool" and v["by"].startswith("fastener_"):
                for t in v["by"].split()[0].split("/"):
                    self.assertIn(t, ours, v["by"])


class Joined(unittest.TestCase):
    def test_guide_only_with_families(self):
        src = open(os.path.join(ROOT, "workshop", "agentlink_families.py"), encoding="utf-8").read()
        self.assertIn("if fams:", src)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "workshop_fasteners", "guides", "fasteners.md")))

    def test_bridge_never_imports_agent_link_outside_its_family(self):
        for fn in ("__init__.py", "detect.py", "fs.py", "api.py", "handlers.py", "families.py", "commands.py"):
            tree = ast.parse(open(os.path.join(ROOT, "workshop_fasteners", fn), encoding="utf-8").read())
            names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
            names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse([x for x in names if x.startswith("agentlink")], fn)

    def test_no_copy_of_fasteners(self):
        # Nothing of Fasteners vendored: none of its files or data here.
        theirs = {"FastenerBase.py", "ScrewMaker.py", "FastenersCmd.py", "screw_maker.py", "FSutils.py", "HeatInserts.csv"}
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in {".git", "tests", "agentlink-addon", "orcalink-addon", "fasteners-ref", "__pycache__"}]
            self.assertFalse(theirs & set(files), d)


if __name__ == "__main__":
    unittest.main()


def make_run(code, fasteners="off"):
    """Make's panels under its own Qt stand-ins (tests/make/_stubs.py), the
    bridge on (the reference clone) or off."""
    sys.path.insert(0, os.path.join(ROOT, "tests", "make"))
    import _stubs

    return _stubs.run(f"import os\nos.environ['WORKSHOP_FASTENERS'] = {fasteners!r}\n" + code)


PANEL = r'''
from workshop_make import taskpanels as T
ran = []
p = T.FormPanel("hole", runner=lambda t, a: (ran.append([t, a]), (True, {}))[1])
OUT["keys"] = sorted(p.values())
OUT["offered"] = T.screw_offered("hole")
OUT["other"] = T.screw_offered("embed")
if getattr(p, "screw", None) is not None:
    OUT["off"] = p.values().get("screw")
    p.screw.setChecked(True)
    OUT["on"] = p.values().get("screw")
    p.accept()
    OUT["sent"] = ran[-1]
'''


class HolePanel(unittest.TestCase):
    def test_hidden_without_fasteners(self):
        out = make_run(PANEL)
        self.assertFalse(out["offered"])
        self.assertEqual(out["keys"], ["at", "body", "depth", "dir", "fit", "kind", "size"])
        self.assertNotIn("on", out)

    @unittest.skipUnless(HAVE, f"no Fasteners Workbench reference clone at {SRC}")
    def test_shown_with_fasteners(self):
        out = make_run(PANEL, SRC)
        self.assertTrue(out["offered"])
        self.assertFalse(out["other"])
        self.assertIn("screw", out["keys"])
        self.assertIsNone(out["off"])
        self.assertTrue(out["on"])
        self.assertEqual(out["sent"][0], "hw_hole")
        self.assertIs(out["sent"][1]["screw"], True)

    def test_screw_arg(self):
        out = make_run('from workshop_make import taskpanels as T\nOUT["a"] = [T.screw_arg(False, "ISO4762"), T.screw_arg(True, ""), T.screw_arg(True, "ISO10642")]\n')
        self.assertEqual(out["a"], [None, True, {"type": "ISO10642"}])


class Hardware(unittest.TestCase):
    def test_bom_and_mass_tell_hardware(self):
        out = make_run(r'''
from workshop_make.handlers import mass
FS = type("FSScrewObject", (), {"__module__": "FastenersCmd"})
class O:
    def __init__(self, label, proxy=None):
        self.Label = self.Name = label
        self.Proxy = proxy
        self.PropertiesList = []
made, hw = mass._split_hardware([O("Box"), O("Screw", FS()), O("Lid")])
OUT["split"] = [[o.Label for o in made], [o.Label for o in hw]]
from workshop_fasteners import api
s = O("Screw001", FS()); s.Type, s.Diameter, s.Length = "ISO4762", "M3", "12"
OUT["bom"] = api.bom_text(s)
''')
        self.assertEqual(out["split"], [["Box", "Lid"], ["Screw"]])
        self.assertEqual(out["bom"], "ISO4762 Screw M3x12")

    def test_hw_hole_screw_without_fasteners_is_a_note(self):
        out = make_run(r'''
from workshop_make.handlers import fits
OUT["note"] = fits._screw(None, {"screw": True}, {"body": "Box"})
''')
        self.assertEqual("notInstalled", out["note"]["screwNote"]["reason"])
