# SPDX-License-Identifier: LGPL-2.1-or-later
# Make with no agent: its data files, its API in a fresh Python (no Agent
# Link imported), and the tool definitions every handler binds to.
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401

    HAVE = True
except ImportError:
    HAVE = False

from workshop_make import datafiles as data  # noqa: E402


def card_text(e):
    """All the words of an entry's card (the hub's reading); the hub is not
    needed: without it the lines are joined here the same way."""
    try:
        from agentlink.tooldata import card_text as hub_card_text
        return hub_card_text(e)
    except ImportError:
        pass
    c = e.get("card")
    if not isinstance(c, dict):
        return e.get("description", "")
    out = [c.get("does", "")]
    for k, n in (c.get("inputNotes") or {}).items():
        out += [f"{k}: {n.get('means', '')}"] + [f"{k}: {f}" for f in n.get("forms") or []]
    out += [x.get("line", "") for x in c.get("links") or []] + list(c.get("effects") or [])
    out += [f"{k}: {r.get('means', '')}" for k, r in (c.get("returns") or {}).items()]
    out += list(c.get("refusalNotes") or []) + list(c.get("hints") or [])
    return " ".join(x for x in out if x)

DATA = os.path.join(ROOT, "workshop_make", "data")


class Data(unittest.TestCase):
    def test_every_file_checks(self):
        self.assertEqual(data.check_folder(DATA), [])

    def test_threads_without_freecad(self):
        sys.path.insert(0, HERE)
        import _threadtable

        threads = _threadtable.install()
        try:
            m6 = threads.lookup("M6")
            self.assertEqual((m6["pitch"], m6["tapDrill"]), (1.0, 5.0))
            self.assertEqual(threads.lookup("1/4-20")["series"], "unc")
            self.assertEqual(len(threads.table("metric")), 17)
        finally:
            threads.use(None)

    def test_tool_definitions(self):
        with open(os.path.join(DATA, "tools.json"), encoding="utf-8") as f:
            tools = json.load(f)["entries"]
        self.assertEqual(sorted({v["group"] for v in tools.values()}), ["cut", "embed", "fits", "make", "mass", "mill", "printer", "slice", "strength", "thread"])
        for name, t in tools.items():
            # No length budget on a description (the owner's ruling of 16 Nov
            # 2026: quality and correctness first); it says what the tool
            # does, its inputs, its traps and what the reply means.
            # Since 28 Nov 2026 the words are a card of records: its lines
            # joined are what the length is read from.
            self.assertGreaterEqual(len(card_text(t)), 200, name)
            self.assertFalse(t["inputSchema"].get("additionalProperties", False), name)
            # The optional fields Agent Link's format takes: the FreeCAD
            # workbench the tool belongs to, the commands it does the work of.
            self.assertIsInstance(t.get("workbench", ""), str, name)
            self.assertTrue(all(isinstance(c, str) and c for c in t.get("commands", [])), name)


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class Api(unittest.TestCase):
    def test_no_agent_link_needed(self):
        code = ("import sys; sys.path[:0] = %r; import FreeCAD; from workshop_make import api; "
                "print(sorted(m for m in sys.modules if m.split('.')[0] == 'agentlink'))") % (sys.path[:],)
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "[]")

    def test_fit_and_hole(self):
        import Part

        from workshop_make import api

        doc = FreeCAD.newDocument("make_api")
        try:
            got = api.fit_size(8.0, "hole", "slide", doc=doc)
            self.assertAlmostEqual(got["model"]["slide"], 8.4)
            api.calibrate(doc, 0.15, 0.05)
            self.assertAlmostEqual(api.fit_size(8.0, "hole", "slide", doc=doc)["model"]["slide"], 8.35)
            o = doc.addObject("Part::Feature", "Plate")
            o.Shape = Part.makeBox(30, 30, 6)
            doc.recompute()
            out = api.hole(doc, "Plate", "counterbore", "M3", at=[15, 15, 6])
            self.assertTrue(out["sound"])
            self.assertGreater(out["removed"], 40)
        finally:
            FreeCAD.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()
