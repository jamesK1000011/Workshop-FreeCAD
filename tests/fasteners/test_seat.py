# SPDX-License-Identifier: LGPL-2.1-or-later
# A fastener on a hole's round edge sits with its head on the open side
# (window review round 4, 5011-5015: the screw stood outside the body).
# Fasteners puts the head where the edge's circle axis points
# (FastenerBase.FSMoveToObject), and OpenCASCADE may point a hole's circle
# into the plate. api.seat() tells the open side from the shape itself;
# fastener_add and fastener_set (edge, invert) set Fasteners' Invert from
# it, as hw_hole's screw always did. Stand-ins only: a plate with a through
# hole that answers isInside, and a stand-in for Fasteners' screw object
# whose execute places the part as FSMoveToObject does.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from workshop_fasteners import api, fs, keep  # noqa: E402


class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __add__(self, o):
        return Vec(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o):
        return Vec(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k):
        return Vec(self.x * k, self.y * k, self.z * k)

    def dot(self, o):
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o):
        return Vec(self.y * o.z - self.z * o.y, self.z * o.x - self.x * o.z, self.x * o.y - self.y * o.x)

    @property
    def Length(self):  # noqa: N802 (FreeCAD)
        return self.dot(self) ** 0.5

    def normalize(self):
        n = self.Length
        self.x, self.y, self.z = self.x / n, self.y / n, self.z / n
        return self


class Circle:
    def __init__(self, c, ax, r):
        self.Center, self.Axis, self.Radius = c, ax, r


class Edge:
    def __init__(self, c, ax, r):
        self.Curve = Circle(c, ax, r)


class PlateShape:
    """80 x 40 x 10 (z 0 to 10), a 6.6 mm hole through it at (10, 20)."""

    def __init__(self, edges, inside=True):
        self.Edges = edges
        if inside:
            self.isInside = self._inside

    @staticmethod
    def _inside(p, tol, face):
        in_box = 0 <= p.x <= 80 and 0 <= p.y <= 40 and 0 <= p.z <= 10
        in_hole = ((p.x - 10) ** 2 + (p.y - 20) ** 2) ** 0.5 < 3.3
        return in_box and not in_hole


class Plate:
    def __init__(self, axis_z=-1.0, inside=True):
        az = Vec(0, 0, axis_z)
        self.Name = self.Label = "Bracket"
        self.Shape = PlateShape([Edge(Vec(10, 20, 10), az, 3.3), Edge(Vec(10, 20, 0), az, 3.3)], inside)

    def getSubObject(self, sub):  # noqa: N802 (FreeCAD)
        return self.Shape.Edges[int(sub[4:]) - 1]


class Screw:
    """Fasteners' screw object as far as add / change / describe use it.
    recompute() places it as FSMoveToObject does: Base on the edge's
    centre, the head toward the axis (or away when Invert), offset along
    that way."""

    def __init__(self, name):
        self.Name, self.Label, self.PropertiesList = name, name, ["Type", "Invert", "Offset", "BaseObject", "Length", "Diameter"]
        self.Invert, self.Offset, self.BaseObject, self.Length, self.Diameter, self.Type = False, 0.0, None, "16", "M6", "ISO4762"
        self.Visibility, self.MatchOuter, self.State = True, True, []
        self.Placement = types.SimpleNamespace(Base=Vec())
        self.head = None   # +1: the head toward +z

    def place(self):
        if not self.BaseObject:
            return
        c = self.BaseObject[0].getSubObject(self.BaseObject[1][0]).Curve
        ax = c.Axis * (-1.0 if self.Invert else 1.0)
        self.Placement.Base = c.Center + ax * float(self.Offset)
        self.head = 1 if ax.z > 0 else -1

    def shank_z(self):
        """The z the shank's tip reaches (16 or 20 mm from the head's seat)."""
        return self.Placement.Base.z - self.head * float(self.Length)


class Doc:
    Name = "FastenersModel"

    def __init__(self, plate):
        self.Objects = [plate]

    def addObject(self, kind, name):  # noqa: N802 (FreeCAD)
        o = Screw(name)
        o.Document = self
        self.Objects.append(o)
        return o

    def recompute(self):
        for o in self.Objects:
            if isinstance(o, Screw):
                o.place()

    def getObject(self, name):  # noqa: N802 (FreeCAD)
        return next((o for o in self.Objects if o.Name == name), None)


def fasteners():
    """A stand-in for the bits of Fasteners Workbench add / change call."""
    def screw_object(o, k, attach):
        o.Type, o.BaseObject = k, attach

    maker = types.SimpleNamespace(GetAllDiams=lambda k: ["M3", "M6"], GetTypeName=lambda k: "Screw",
                                  FindClosest=lambda t, d, ln: (d, ln, None))
    cmd = types.SimpleNamespace(FSScrewCommandTable={"ISO4762": ("socket head cap screw", "screws")}, FSScrewObject=screw_object)
    return types.SimpleNamespace(screwMaker=maker, FastenersCmd=cmd)


class Seat(unittest.TestCase):
    def test_the_open_side_whichever_way_the_axis_points(self):
        down, up = Plate(-1.0), Plate(1.0)
        self.assertEqual(api.seat(down, "Edge1"), -1)   # top rim, axis into the plate: open side against it
        self.assertEqual(api.seat(up, "Edge1"), 1)
        self.assertEqual(api.seat(down, "Edge2"), 1)    # bottom rim: open below
        self.assertTrue(api.seated_invert((down, "Edge1")))
        self.assertFalse(api.seated_invert((up, "Edge1")))
        self.assertFalse(api.seated_invert((down, "Edge1"), flip=True))

    def test_a_shape_that_cannot_tell(self):
        p = Plate(-1.0, inside=False)
        self.assertEqual(api.seat(p, "Edge1"), 0)
        self.assertFalse(api.seated_invert((p, "Edge1")))      # as Fasteners has it
        self.assertTrue(api.seated_invert((p, "Edge1"), True))
        self.assertFalse(api.seated_invert(None))


class AddAndChange(unittest.TestCase):
    def setUp(self):
        self.saved = (fs.load, keep.adopt)
        fs.load = fasteners
        keep.adopt = lambda doc, o, label=None, adopted=False: None
        api.MOVED.clear()

    def tearDown(self):
        fs.load, keep.adopt = self.saved

    def add(self, axis_z, **kw):
        plate = Plate(axis_z)
        doc = Doc(plate)
        o = api.add(doc, "ISO4762", "M6", 16, edges=["Bracket.Edge1"], **kw)[0]
        return doc, plate, o

    def test_add_puts_the_head_on_the_top_face_and_the_shank_in_the_hole(self):
        for axis_z in (-1.0, 1.0):
            doc, plate, o = self.add(axis_z)
            self.assertEqual(o.head, 1, axis_z)                      # head up, out of the plate
            self.assertEqual((o.Placement.Base.z, o.shank_z()), (10.0, -6.0))
            d = api.describe(o)
            self.assertEqual((d["headSide"], d["shankOut"]), ("open side", 6))

    def test_invert_turns_it_end_for_end(self):
        _doc, _plate, o = self.add(-1.0, invert=True)
        self.assertEqual(o.head, -1)
        self.assertEqual(api.describe(o)["headSide"], "in the material")

    def test_set_length_keeps_it_seated(self):
        # fastener_set { length: 20 }: the same edge, the head still on top;
        # a 20 mm screw in a 10 mm plate stands 10 mm out of the far side.
        doc, _plate, o = self.add(-1.0)
        api.change(doc, [o.Name], length=20)
        self.assertEqual((o.head, o.Placement.Base.z, o.shank_z()), (1, 10.0, -10.0))
        self.assertEqual(api.describe(o)["shankOut"], 10)

    def test_set_invert_is_from_seated(self):
        doc, _plate, o = self.add(-1.0)
        api.change(doc, [o.Name], invert=True)
        self.assertEqual(o.head, -1)
        api.change(doc, [o.Name], invert=False)
        self.assertEqual(o.head, 1)

    def test_moved_to_the_bottom_rim_sits_below(self):
        doc, _plate, o = self.add(-1.0)
        api.change(doc, [o.Name], edge="Bracket.Edge2")
        self.assertEqual((o.Placement.Base.z, o.head), (0.0, -1))   # a head (or nut) under the plate, shank up into it


if __name__ == "__main__":
    unittest.main()
