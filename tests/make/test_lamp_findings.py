# SPDX-License-Identifier: LGPL-2.1-or-later
# The desk-lamp test drive's findings on Make (20 Nov 2026): slice_with takes
# a mesh (a Textured result) as it is and refuses an object that is neither
# a solid nor a mesh (5); slice_with with several bodies or orient says which
# hw_embed pauses it dropped and how to keep them (10); dfm_check reads a
# body in its own frame, not in an assembly's pose (7); a ceiling over an
# hw_embed pocket is carried by the part after the pause, not a bridge (8).
# Stand-ins first (no FreeCAD), then the same on FreeCAD with Agent Link.
import json
import os
import sys
import tempfile
import unittest

from _stubs import run

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False
try:
    import agentlink.tools  # noqa: F401

    AGENT = HAVE
except ImportError:
    AGENT = False

PLATE = r'''
import os, tempfile, types
from workshop_make.handlers import slicing as SW
from workshop_make import records as store
setups = {"Knob": {"id": "S1", "name": "Print", "type": "print", "bodies": ["Knob", "Base"], "layerHeight": 0.2}}
setups["Base"] = setups["Knob"]
store.setup_of = lambda doc, label, kind=None: setups.get(label)
store.materials = lambda doc: {}
written = []
class MeshData:
    def write(self, path):
        written.append(("mesh", path))
        open(path, "w").write("solid t\nendsolid t\n")
class Body:
    def __init__(self, label):
        self.Label, self.Name, self.TypeId, self.Shape = label, label, "PartDesign::Body", object()
knob, base = Body("Knob"), Body("Base")
tex = types.SimpleNamespace(Label="Knob Textured", Name="Textured", TypeId="Mesh::FeaturePython", Mesh=MeshData(), Source=knob, SourceBody="Knob")
sheet = types.SimpleNamespace(Label="Params", Name="Spreadsheet", TypeId="Spreadsheet::Sheet")
class Doc:
    Objects = [knob, base, tex, sheet]
    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)
class S:
    doc = Doc()
    meta = {}
    out_dir = tempfile.mkdtemp()
    def body(self, ref):
        for o in (knob, base):
            if ref in (o.Label, o.Name):
                return o
        if ref is None:
            raise SW.ToolError("invalid_input", "body: say which")
        raise SW.ToolError("not_found", f"body {ref!r}: not here")
import MeshPart
def mesh_from_shape(**k):
    class M:
        def write(self, path):
            written.append(("body", path))
    return M()
MeshPart.meshFromShape = mesh_from_shape
used = {}
class Cli:
    NAMES = ("prusaslicer", "orcaslicer", "bambustudio")
    PAUSE = {"prusaslicer": "M601", "orcaslicer": "M601", "bambustudio": "M400 U1"}
    LAST = {}
    def slice_with(self, name, stl, gcode, settings, profiles, options=None):
        used["stl"], used["options"] = stl, options
        open(gcode, "w").write(";LAYER_CHANGE\n")
        return "/bin/" + name, "written"
    def read_gcode(self, gcode):
        return {"layers": 60}
    def insert_pauses(self, gcode, want, cmd):
        return list(want)
SW.slicers = Cli()
# Base has one encased steel plate; Knob (and so its Textured mesh) one magnet.
PAUSES = {"Base": [{"z": 11.4, "note": "Insert the steel plate", "afterLayer": 57}], "Knob": [{"z": 3.2, "note": "Insert the magnet", "afterLayer": 16}]}
SW.pauses_for = lambda s, o, setup: list(PAUSES.get(o.Label, []))
def call(a):
    try:
        return {"ok": SW.slice_with(S(), a)}
    except Exception as e:  # noqa: BLE001
        return {"err": [getattr(e, "code", type(e).__name__), str(e)]}
'''


class SliceAMesh(unittest.TestCase):
    """Finding 5: a mesh goes on the plate as it is; a non-shape is refused."""

    def test_mesh_as_it_is(self):
        out = run(PLATE + r'''
OUT["r"] = call({"body": "Knob Textured"})
OUT["written"] = written
''')
        r = out["r"]["ok"]
        self.assertEqual(r["body"], "Knob Textured")
        self.assertTrue(r["mesh"])
        # Written by the mesh itself, not meshed again from a shape.
        self.assertEqual([k for k, _ in out["written"]], ["mesh"])
        # Its setup and its pauses are those of the body it was made from.
        self.assertEqual(r["setup"], "Print (S1)")
        self.assertEqual([p["z"] for p in r["pauses"]], [3.2])
        self.assertNotIn("pausesDropped", r)

    def test_mesh_beside_a_body(self):
        out = run(PLATE + r'''
OUT["r"] = call({"bodies": ["Base", "Knob Textured"], "slicer": "orcaslicer"})
OUT["written"] = sorted(k for k, _ in written)
''')
        r = out["r"]["ok"]
        self.assertEqual(r["bodies"], ["Base", "Knob Textured"])
        self.assertEqual(out["written"], ["body", "mesh"])

    def test_not_a_shape_is_refused_by_its_type(self):
        out = run(PLATE + r'''
OUT["sheet"] = call({"body": "Params"})
OUT["none"] = call({"body": "Lamp shade"})
''')
        code, msg = out["sheet"]["err"]
        self.assertEqual(code, "invalid_input")
        self.assertIn("Spreadsheet::Sheet", msg)
        self.assertIn("not a solid or a mesh", msg)
        code, msg = out["none"]["err"]
        self.assertEqual(code, "not_found")


class DroppedPauses(unittest.TestCase):
    """Finding 10: several bodies (or orient) drop the hw_embed pauses: the
    answer says which and how to keep them."""

    def test_several_bodies(self):
        out = run(PLATE + r'''
OUT["r"] = call({"bodies": ["Base", "Knob"], "slicer": "orcaslicer"})
''')
        r = out["r"]["ok"]
        self.assertEqual(r["pauses"], [])
        w = r["pausesDropped"]
        self.assertEqual(w["reason"], "severalBodies")
        self.assertIn({"body": "Base", "count": 1, "z": [11.4]}, w["bodies"])
        self.assertIn({"body": "Knob", "count": 1, "z": [3.2]}, w["bodies"])

    def test_orient(self):
        out = run(PLATE + r'''
OUT["r"] = call({"body": "Base", "slicer": "orcaslicer", "orient": True})
''')
        r = out["r"]["ok"]
        self.assertEqual(r["pausesDropped"]["reason"], "orient")
        self.assertEqual(r["pausesDropped"]["bodies"][0]["body"], "Base")

    def test_alone_keeps_them_without_a_warning(self):
        out = run(PLATE + r'''
OUT["r"] = call({"body": "Base"})
OUT["plain"] = call({"bodies": ["Knob Textured", "Base"], "slicer": "orcaslicer"})
PAUSES.clear()
OUT["none"] = call({"bodies": ["Base", "Knob"], "slicer": "orcaslicer"})
''')
        self.assertEqual([p["z"] for p in out["r"]["ok"]["pauses"]], [11.4])
        self.assertNotIn("pausesDropped", out["r"]["ok"])
        self.assertIn("pausesDropped", out["plain"]["ok"])
        self.assertNotIn("pausesDropped", out["none"]["ok"])


class CarriedCeiling(unittest.TestCase):
    """Finding 8, the matching alone: a ceiling at the pocket's top, inside
    its reach and no larger than it, is carried; one beside it or larger is not."""

    def test_carried_by(self):
        out = run(r'''
from workshop_make import printability as P
top = [{"id": "E1", "what": "80x60x8 weight", "at": [60.0, 45.0, 11.4], "reach": 50.1, "area": 80.4 * 60.4}]
OUT["over"] = (P.carried_by({"at": [60.0, 45.0, 11.4], "area": 4850.0}, top) or {}).get("id")
OUT["higher"] = P.carried_by({"at": [60.0, 45.0, 13.0], "area": 4850.0}, top)
OUT["beside"] = P.carried_by({"at": [140.0, 45.0, 11.4], "area": 400.0}, top)
OUT["larger"] = P.carried_by({"at": [60.0, 45.0, 11.4], "area": 9000.0}, top)
OUT["none"] = P.carried_by({"at": [60.0, 45.0, 11.4], "area": 4850.0}, ())
''')
        self.assertEqual(out["over"], "E1")
        for k in ("higher", "beside", "larger", "none"):
            self.assertIsNone(out[k], k)


@unittest.skipUnless(AGENT, "FreeCAD and Agent Link are not both importable here")
class OnFreeCAD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agentlink.tools import Session, build_server

        cls.dir = tempfile.mkdtemp()
        cls.session = Session(out_dir=cls.dir)
        cls.server = build_server(cls.session, lean=False)

    def call(self, name, args=None):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})["result"]
        return r.get("isError", False), json.loads(r["content"][0]["text"])

    def add(self, label, shape, placement=None):
        o = self.session.doc.addObject("Part::Feature", "Body")
        o.Label = label
        o.Shape = shape
        if placement is not None:
            o.Placement = placement
        self.session.doc.recompute()
        return o

    def test_1_own_frame_not_the_assembled_pose(self):
        # Finding 7: an arm 100 x 10 x 10 lying flat, stood on end by its
        # Placement (as an assembly's joint turns it): read in its own frame.
        import Part

        V = FreeCAD.Vector
        self.add("Arm flat", Part.makeBox(100, 10, 10))
        self.add("Arm stood", Part.makeBox(100, 10, 10), FreeCAD.Placement(V(30, 0, 0), FreeCAD.Rotation(V(0, 1, 0), -90)))
        self.assertGreater(self.session.body("Arm stood").Shape.BoundBox.ZLength, 99)
        err, flat = self.call("dfm_check", {"body": "Arm flat"})
        self.assertFalse(err, flat)
        err, stood = self.call("dfm_check", {"body": "Arm stood"})
        self.assertFalse(err, stood)
        print("\ndfm_check stood:", json.dumps({k: stood[k] for k in ("frame", "verdict", "findings")}))
        rules = lambda d: sorted(f["rule"] for f in d["findings"])  # noqa: E731
        self.assertNotIn("tall-thin", rules(stood))
        self.assertNotIn("bed-contact", rules(stood))
        self.assertEqual(rules(stood), rules(flat))
        self.assertIn("own frame", stood["frame"])
        self.assertIn("Placement", stood["frame"])
        self.assertNotIn("Placement", flat["frame"])
        err, rv = self.call("part_review", {"body": "Arm stood"})
        self.assertFalse(err, rv)
        self.assertIn("own frame", rv["frame"])
        self.assertFalse(any(f.get("rule") == "tall-thin" for f in rv.get("ifPrinted", []) + rv["findings"]), rv)

    def test_2_ceiling_over_an_embed_is_carried(self):
        # Finding 8: a steel plate encased in a base: the pocket's flat
        # ceiling (40 mm across) is carried by the plate after the pause.
        import Part

        self.add("Plate base", Part.makeBox(80, 60, 14))
        err, a = self.call("setup", {"action": "add", "type": "print", "bodies": ["Plate base"], "settings": {"layerHeight": 0.2, "firstLayer": 0.2}})
        self.assertFalse(err, a)
        err, e = self.call("hw_embed", {"body": "Plate base", "kind": "weight", "size": "50x40x4", "at": [40, 30, 3]})
        self.assertFalse(err, e)
        err, d = self.call("dfm_check", {"body": "Plate base"})
        self.assertFalse(err, d)
        print("\ndfm_check embed:", json.dumps({k: d.get(k) for k in ("verdict", "findings", "carried")}))
        self.assertFalse(any(f["rule"] == "bridge" for f in d["findings"]), d["findings"])
        self.assertEqual([c["by"] for c in d["carried"]], [e["id"]])
        self.assertEqual(e["id"], d["carried"][0]["by"])
        # The record gone (the pocket kept open, the part pressed in after):
        # the same ceiling is a bridge again.
        err, u = self.call("hw_unembed", {"body": "Plate base", "id": e["id"], "keepPocket": True})
        self.assertFalse(err, u)
        err, d2 = self.call("dfm_check", {"body": "Plate base"})
        self.assertTrue(any(f["rule"] == "bridge" for f in d2["findings"]), d2["findings"])
        self.assertNotIn("carried", d2)

    def test_3_mesh_on_the_plate_as_it_is(self):
        # Finding 5: a Mesh::Feature made from a body (as texture_apply's
        # Textured) is sliced as it is: same triangles, in its placement.
        import Mesh
        import MeshPart
        import Part

        from workshop_make.handlers import slicing as SW

        V = FreeCAD.Vector
        knob = self.add("Knob", Part.makeCylinder(14, 12))
        err, a = self.call("setup", {"action": "add", "type": "print", "bodies": ["Knob"], "settings": {"layerHeight": 0.2}})
        self.assertFalse(err, a)
        doc = self.session.doc
        tex = doc.addObject("Mesh::Feature", "Textured")
        tex.Label = "Knob Textured"
        tex.Mesh = MeshPart.meshFromShape(Shape=knob.Shape, LinearDeflection=0.5)
        tex.addProperty("App::PropertyLink", "Source")
        tex.Source = knob
        lone = doc.addObject("Mesh::Feature", "Lone")
        lone.Label = "Lone mesh"
        lone.Mesh = MeshPart.meshFromShape(Shape=Part.makeBox(20, 20, 4), LinearDeflection=0.5)
        lone.Placement = FreeCAD.Placement(V(0, 0, 5), FreeCAD.Rotation())
        sheet = doc.addObject("Spreadsheet::Sheet", "Params")
        doc.recompute()
        got = {}

        class Cli:
            NAMES = ("prusaslicer", "orcaslicer", "bambustudio")
            PAUSE = {"prusaslicer": "M601"}
            LAST = {}

            def slice_with(self, name, stl, gcode, settings, profiles, options=None):
                got["stl"] = stl
                with open(gcode, "w") as f:
                    f.write(";LAYER_CHANGE\n")
                return "/bin/prusa-slicer", "written"

            def read_gcode(self, gcode):
                return {"layers": 1}

            def insert_pauses(self, gcode, want, cmd):
                return list(want)

        keep = SW.slicers
        SW.slicers = Cli()
        try:
            r = SW.slice_with(self.session, {"body": "Knob Textured"})
            written = Mesh.Mesh(got["stl"])
            self.assertEqual(written.CountFacets, tex.Mesh.CountFacets)
            self.assertTrue(r["mesh"])
            self.assertTrue(r["setup"].endswith(f"({a['added']['id']})"), r["setup"])
            # A mesh of its own: no setup until one is added for it, then sliced in its placement.
            with self.assertRaises(Exception) as no:
                SW.slice_with(self.session, {"body": "Lone mesh"})
            self.assertEqual(getattr(no.exception, "code", None), "invalid_state")
            err, a2 = self.call("setup", {"action": "add", "type": "print", "bodies": ["Lone mesh"], "settings": {"layerHeight": 0.2}})
            self.assertFalse(err, a2)
            SW.slice_with(self.session, {"body": "Lone mesh"})
            bb = Mesh.Mesh(got["stl"]).BoundBox
            self.assertAlmostEqual(bb.ZMin, 5.0, places=3)
            self.assertAlmostEqual(bb.ZMax, 9.0, places=3)
            with self.assertRaises(Exception) as bad:
                SW.slice_with(self.session, {"body": sheet.Label})
            self.assertEqual(getattr(bad.exception, "code", None), "invalid_input")
            self.assertIn("not a solid or a mesh", str(bad.exception))
        finally:
            SW.slicers = keep


if __name__ == "__main__":
    unittest.main()
