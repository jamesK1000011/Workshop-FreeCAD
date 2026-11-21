# SPDX-License-Identifier: LGPL-2.1-or-later
# fea_frame's results (bicycle runs, 21 Nov 2026, finding 4), pure Python on a
# hand-made .frd (no CalculiX needed):
#   a  each member reads the nodes of its own expanded elements only: a
#      neighbour's stress no longer lands on a short member at a joint
#      (von Mises 214 MPa against -9.9 ... 5.4 MPa along it);
#   b  CalculiX's section lines: CIRC the diameter, PIPE the outer radius (the
#      circle was made half size); a radius is refused;
#   c  yieldMPa in the call judges safety where the card has no yield.
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from workshop_make import frame as FR  # noqa: E402

P, L, D = 100.0, 500.0, 20.0  # N at the free end, mm long, mm across (circ)
I = math.pi * D ** 4 / 64
C = D / 2
SIGMA = P * L * C / I  # 63.66 MPa at the fixed end, top and bottom
TAU = 4 * P / (3 * math.pi * D ** 2 / 4)  # 0.42 MPa at the neutral axis


def _num(v):
    return f"{v:12.5E}"


def frd_of(book, extra_post=True):
    """A .frd as CalculiX writes it for expanded beams: each beam element a
    solid under its own number (12 nodes here, 20 in CalculiX's), stresses by beam theory on the
    cantilever, and a post loaded 200 MPa along its own axis (z)."""
    nodes, elems, stress, disp = {}, {}, {}, {}
    nid = [10000]

    def node(p, s):
        nid[0] += 1
        nodes[nid[0]] = p
        stress[nid[0]] = s
        disp[nid[0]] = (0.0, 0.0, 0.0)
        return nid[0]

    cant, post = book["members"][0], book["members"][1]
    for k, e in enumerate(cant["elements"]):
        le = cant["L"] / len(cant["elements"])
        ids = []
        for x in (k * le, (k + 0.5) * le, (k + 1) * le):
            for ang in (0, 90, 180, 270):
                y, z = C * math.cos(math.radians(ang)), C * math.sin(math.radians(ang))
                m = P * (L - x)
                sx = m * z / I
                txz = TAU if abs(z) < 1e-9 and x > L - le else 0.0  # the shear at the loaded free end
                ids.append(node((x, y, z), (sx, 0.0, 0.0, 0.0, 0.0, txz)))
        elems[e] = ids
    for k, e in enumerate(post["elements"]):
        le = post["L"] / len(post["elements"])
        ids = []
        for zc in (-k * le, -(k + 0.5) * le, -(k + 1) * le):
            for ang in (0, 90, 180, 270):
                r = 20.0
                ids.append(node((r * math.cos(math.radians(ang)), r * math.sin(math.radians(ang)), zc), (0.0, 0.0, 200.0, 0.0, 0.0, 0.0)))
        elems[e] = ids
    for m in book["members"]:
        for n_ in (m["nodes"][0], m["nodes"][-1]):
            disp.setdefault(n_, (0.0, 0.0, 0.0))
    out = ["    2C" + " " * 18 + f"{len(nodes):12d}" + " " * 37 + "1"]
    out += [" -1" + f"{n_:10d}" + "".join(_num(c) for c in p) for n_, p in sorted(nodes.items())]
    out += [" -3", "    3C" + " " * 18 + f"{len(elems):12d}" + " " * 37 + "1"]
    for e, ids in sorted(elems.items()):
        out.append(" -1" + f"{e:10d}" + "    4    0    1")
        for j in range(0, len(ids), 10):
            out.append(" -2" + "".join(f"{x:10d}" for x in ids[j:j + 10]))
    out.append(" -3")
    out += ["  100CL  101 0.00000E+00", " -4  DISP        4    1"]
    out += [" -1" + f"{n_:10d}" + "".join(_num(c) for c in v) for n_, v in sorted(disp.items())]
    out += [" -3", "  100CL  102 0.00000E+00", " -4  STRESS      6    1"]
    out += [" -1" + f"{n_:10d}" + "".join(_num(c) for c in v) for n_, v in sorted(stress.items())]
    out += [" -3", "9999"]
    return "\n".join(out)


def book_of():
    E = 70000.0
    members = [{"name": "Arm", "from": [0, 0, 0], "to": [L, 0, 0], "section": {"kind": "circ", "d": D}, "E": E},
               {"name": "Post", "from": [0, 0, 0], "to": [0, 0, -300], "section": {"kind": "circ", "d": 40}, "E": E}]
    _text, book = FR.build(members, [{"at": [0, 0, -300], "kind": "fixed"}], [{"at": [L, 0, 0], "force": [0, 0, -P]}], None, 8, 1.0)
    return _text, book


class OwnNodes(unittest.TestCase):
    def test_a_hand_checked_cantilever_beside_a_loaded_post(self):
        _text, book = book_of()
        res = FR.read_results(book, frd_of(book), "")
        arm = next(r for r in res["members"] if r["member"] == "Arm")
        lo, hi = arm["axialBendingMPa"]
        self.assertAlmostEqual(hi, SIGMA, delta=0.01 * SIGMA)
        self.assertAlmostEqual(lo, -SIGMA, delta=0.01 * SIGMA)
        # von Mises agrees with the stress along the member (the post's 200 MPa is not the arm's)
        self.assertAlmostEqual(arm["vonMisesMPa"], SIGMA, delta=0.01 * SIGMA)
        self.assertLessEqual(arm["vonMisesMPa"], max(abs(lo), abs(hi)) * 1.05)
        post = next(r for r in res["members"] if r["member"] == "Post")
        self.assertAlmostEqual(post["vonMisesMPa"], 200.0, places=3)

    def test_the_old_reach_took_the_neighbours_nodes(self):
        _text, book = book_of()
        frd = frd_of(book)
        without = frd[:frd.index("    3C")] + frd[frd.index("  100CL  101"):]  # no element block: the old way
        arm = next(r for r in FR.read_results(book, without, "")["members"] if r["member"] == "Arm")
        self.assertGreater(arm["vonMisesMPa"], 150)  # the post's stress, as the runs saw it
        self.assertLess(arm["axialBendingMPa"][1], SIGMA * 1.01)

    def test_elements_read(self):
        _text, book = book_of()
        els = FR.read_elements(frd_of(book))
        self.assertEqual(sorted(els), list(range(1, 17)))
        self.assertTrue(all(len(v) in (12, 20) for v in els.values()))


class Sections(unittest.TestCase):
    def test_calculix_lines_as_freecad_writes_them(self):
        self.assertEqual(FR.section_props({"kind": "circ", "d": 26})[3], ("CIRC", "26, 26"))
        self.assertEqual(FR.section_props({"kind": "pipe", "d": 28.6, "t": 2})[3], ("PIPE", "14.3, 2"))
        self.assertEqual(FR.section_props({"kind": "rect", "b": 38, "d": 184})[3], ("RECT", "38, 184"))
        self.assertEqual(FR.section_props({"kind": "box", "b": 100, "d": 150, "t": 5})[3], ("BOX", "100, 150, 5, 5, 5, 5"))

    def test_every_kind_against_its_hand_figures(self):
        a, i, c, _ = FR.section_props({"kind": "circ", "d": 26})
        self.assertAlmostEqual(a, math.pi * 13 ** 2)
        self.assertAlmostEqual(i, math.pi * 26 ** 4 / 64)
        self.assertEqual(c, 13)
        a, i, c, _ = FR.section_props({"kind": "pipe", "d": 28.6, "t": 2})
        self.assertAlmostEqual(a, math.pi / 4 * (28.6 ** 2 - 24.6 ** 2))
        self.assertAlmostEqual(i, math.pi / 64 * (28.6 ** 4 - 24.6 ** 4))
        self.assertAlmostEqual(c, 14.3)
        a, i, c, _ = FR.section_props({"kind": "rect", "b": 38, "d": 184})
        self.assertEqual((a, c), (38 * 184, 92))
        a, i, c, _ = FR.section_props({"kind": "box", "b": 100, "d": 150, "t": 5})
        self.assertEqual(a, 100 * 150 - 90 * 140)
        self.assertEqual(c, 75)

    def test_radius_and_bad_sizes_refused(self):
        for sec, words in (({"kind": "circ", "r": 13}, "not a radius"), ({"kind": "circ", "d": 26, "radius": 13}, "not a radius"),
                           ({"kind": "pipe", "d": 20, "t": 10}, "less than half of d"), ({"kind": "box", "b": 10, "d": 40, "t": 5}, "less than half"),
                           ({"kind": "circ", "d": 0}, "more than 0"), ({"kind": "pipe", "d": 20}, "section.t")):
            with self.assertRaises(ValueError) as e:
                FR.section_props(sec)
            self.assertIn(words, str(e.exception), sec)


if __name__ == "__main__":
    unittest.main()


class YieldGiven(unittest.TestCase):
    """c: a card with no yield (Steel-Generic) and yieldMPa in the call."""

    def run_frame(self, args):
        import json
        import subprocess

        code = f'''
import json, sys, types
sys.path.insert(0, {ROOT!r})
fc = types.ModuleType("FreeCAD")
fc.Vector = lambda *a: a
sys.modules["FreeCAD"] = fc
sys.modules["Part"] = types.ModuleType("Part")
from workshop_make.handlers import frame as H
from workshop_make.handlers._lent import Refusal
H.ToolError = Refusal
H.ccx_io.find_binary = lambda *a: "ccx"
H.matfam = types.SimpleNamespace(card=lambda doc, mid: {{"name": "Steel-Generic", "E": 210000, "nu": 0.3, "density": 7.8}})
H.FR.solve = lambda *a, **k: {{"members": [{{"member": "A", "vonMisesMPa": 100.0}}, {{"member": "B", "vonMisesMPa": 50.0}}], "supports": [], "files": "x", "loadTotalN": [0, 0, -1]}}
s = types.SimpleNamespace(doc=None, out_dir="/tmp")
try:
    out = H.fea_frame(s, json.loads({json.dumps(json.dumps(args))}))
except Refusal as e:
    out = ["refused", e.code, e.message]
print(json.dumps(out, default=str))
'''
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        if r.returncode:
            raise AssertionError(r.stderr[-3000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    M = [{"name": "A", "from": [0, 0, 0], "to": [100, 0, 0], "section": {"kind": "circ", "d": 20}},
         {"name": "B", "from": [100, 0, 0], "to": [200, 0, 0], "section": {"kind": "circ", "d": 20}, "yieldMPa": 400}]
    S = [{"at": [0, 0, 0], "kind": "fixed"}]

    def test_no_yield_says_so(self):
        out = self.run_frame({"members": self.M[:1], "material": "steel", "supports": self.S})
        self.assertNotIn("safety", out["members"][0])
        self.assertIn("No yield on the card of Steel-Generic", out["yieldNote"])
        self.assertIn("yieldMPa", out["yieldNote"])

    def test_yield_in_the_call_and_on_a_member(self):
        out = self.run_frame({"members": self.M, "material": "steel", "supports": self.S, "yieldMPa": 250})
        a, b = out["members"]
        self.assertEqual((a["safety"], a["yieldFrom"]), (2.5, "the call's yieldMPa"))
        self.assertEqual((b["safety"], b["yieldFrom"]), (8.0, "the member's yieldMPa"))
        self.assertEqual(out["verdict"], "least safety 2.5, A")
        self.assertNotIn("yieldNote", out)

    def test_a_bad_yield_is_refused(self):
        out = self.run_frame({"members": self.M[:1], "material": "steel", "supports": self.S, "yieldMPa": -5})
        self.assertEqual(out[:2], ["refused", "invalid_input"])
