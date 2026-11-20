# SPDX-License-Identifier: LGPL-2.1-or-later
# drawing_make on the desk lamp's base (live, 20 Nov 2026): the M5 pin hole
# (⌀5.5 along Y) goes through a forked round post, one face in each tine.
# Its rim on the post's round face is a 3D curve, not a circle: HLR draws it
# as a B-spline, so no circle was found and the front view's callout was
# left off ("no circle of ⌀5.5 drawn where the hole is"). Now a round edge
# that is not a circle in the model is taken as the circle its points lie
# on (views.fit_circle). The fit anywhere; the forked post on FreeCAD.
import json
import math
import os
import sys
import tempfile
import unittest

from _stubs import run

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..")]
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401
    import TechDraw  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False
try:
    import agentlink.tools  # noqa: F401

    AGENT = HAVE
except ImportError:
    AGENT = False


class FitCircle(unittest.TestCase):
    def test_points_on_a_circle(self):
        out = run(r'''
import math
from workshop_documents import views
ring = [(-40 + 2.75 * math.cos(a / 40 * 2 * math.pi), 48 + 2.75 * math.sin(a / 40 * 2 * math.pi)) for a in range(40)]
arc = [(5 + 3 * math.cos(a / 20 * math.pi), 2 + 3 * math.sin(a / 20 * math.pi)) for a in range(21)]
line = [(x * 1.0, 0.5 * x) for x in range(10)]
wave = [(x * 0.5, math.sin(x)) for x in range(20)]
OUT["ring"] = views.fit_circle(ring)
OUT["arc"] = views.fit_circle(arc)
OUT["line"] = views.fit_circle(line)
OUT["wave"] = views.fit_circle(wave)
OUT["few"] = views.fit_circle(ring[:4])
''')
        cx, cy, r, turn = out["ring"]
        self.assertAlmostEqual(cx, -40, places=6)
        self.assertAlmostEqual(cy, 48, places=6)
        self.assertAlmostEqual(r, 2.75, places=6)
        self.assertAlmostEqual(turn, 2 * math.pi, places=6)
        cx, cy, r, turn = out["arc"]
        self.assertAlmostEqual(r, 3, places=6)
        self.assertAlmostEqual(turn, math.pi, places=3)
        for k in ("line", "wave", "few"):
            self.assertIsNone(out[k], k)


def forked_base():
    """The lamp base as the live run described it: a 120 x 90 x 16 slab, a
    ⌀26 post at x = -40 up to z = 56, a fork gap 8.6 wide across Y, the
    tines trimmed flat at x < -50 and x > -30 above z = 36, and a ⌀5.5 pin
    hole along Y at (x = -40, z = 48)."""
    import Part

    V = FreeCAD.Vector
    sh = Part.makeBox(120, 90, 16, V(-60, -45, 0)).fuse(Part.makeCylinder(13, 56, V(-40, 0, 0)))
    sh = sh.cut(Part.makeBox(40, 8.6, 30, V(-60, -4.3, 36)))
    sh = sh.cut(Part.makeBox(10, 40, 30, V(-60, -20, 36))).cut(Part.makeBox(10, 40, 30, V(-30, -20, 36)))
    sh = sh.cut(Part.makeCylinder(2.75, 60, V(-40, -30, 48), V(0, 1, 0)))
    return sh.removeSplitter()


@unittest.skipUnless(HAVE, "FreeCAD with TechDraw is not importable here")
class ForkedPost(unittest.TestCase):
    def test_the_pin_hole_has_its_circle_in_the_front_view(self):
        from workshop_documents import views
        from workshop_documents.handlers import drawing as D

        sh = forked_base()
        self.assertEqual(len(sh.Solids), 1)

        class O:
            Shape = sh
            Label = "Base"

        holes = dict((round(d, 2), cs) for d, cs in D._holes([O()], "front"))
        self.assertIn(5.5, holes, holes)
        drawn = views.project([sh], "front")
        on = D.hole_circle(drawn["circles"], [views.point(c, "front") for c in holes[5.5]], 2.75)
        self.assertIsNotNone(on, drawn["circles"])
        cx, cy, r = on[1]
        self.assertAlmostEqual(cx, -40, delta=0.05)
        self.assertAlmostEqual(cy, 48, delta=0.05)


@unittest.skipUnless(AGENT, "FreeCAD with TechDraw and Agent Link are not importable here")
class ForkedPostCalledOut(unittest.TestCase):
    def test_drawing_make_calls_it_out(self):
        from agentlink.tools import Session, build_server

        session = Session(out_dir=tempfile.mkdtemp())
        server = build_server(session, lean=False)
        o = session.doc.addObject("Part::Feature", "Base")
        o.Label = "Base"
        o.Shape = forked_base()
        session.doc.recompute()
        r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "drawing_make", "arguments": {
            "bodies": ["Base"], "views": ["front", "top", "right", "iso"], "holes": True, "page": False}}})["result"]
        d = json.loads(r["content"][0]["text"])
        self.assertFalse(r.get("isError"), d)
        print("\nforked post holes:", json.dumps({k: d.get(k) for k in ("holes", "calloutsOff")}))
        pin = [h for h in d["holes"] if abs(h["diameter"] - 5.5) < 0.01]
        self.assertEqual(len(pin), 1, d["holes"])
        self.assertEqual(pin[0]["view"], "front")
        self.assertNotIn("calloutOff", pin[0])
        self.assertFalse([c for c in d.get("calloutsOff") or [] if "5.5" in c.get("label", "")], d.get("calloutsOff"))


if __name__ == "__main__":
    unittest.main()
