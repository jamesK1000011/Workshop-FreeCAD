# SPDX-License-Identifier: LGPL-2.1-or-later
# slicer_presets list: counts, the person's own marked and in full, the
# first names of the rest (limit), how many more, and the preset folders
# said once a session (window review round 3: every list answered 60 names
# a kind and the four folders, about 10 000 characters, on every call).
import unittest

from _stubs import run

FAKE = r'''
import types
from workshop_make.handlers import slicing as H
names = {"machine": ["Bambu Lab X1 Carbon 0.4 nozzle", "Bambu Lab P1S 0.4 nozzle"] + [f"Printer {i}" for i in range(70)],
         "process": [f"0.{i:02d}mm Standard" for i in range(80)],
         "filament": [f"Generic PLA {i}" for i in range(90)]}
own = {"filament": ["My PETG"], "process": ["My 0.20mm"]}
asked = []
class SP:
    class PresetError(Exception):
        pass
    KINDS = ("machine", "process", "filament")
    ROOTS = {"bambustudio": None, "orcaslicer": None}
    @staticmethod
    def roots(slicer): return ["/presets/system", "/presets/user"]
    @staticmethod
    def listing(slicer, kind=None, query=None, limit=60):
        asked.append(limit)
        out = {}
        for k in ([kind] if kind else SP.KINDS):
            rows = [{"name": n, "own": True} for n in own.get(k, [])] + [{"name": n} for n in names[k]]
            rows = [r for r in rows if all(w in r["name"].lower() for w in (query or "").lower().split())]
            out[k] = {"count": len(rows), "presets": rows[:limit]}
        return out
    @staticmethod
    def saved(out_dir): return []
    @staticmethod
    def packed_only(slicer): return False
H.SP = SP
class S:
    out_dir = "/tmp/out"
'''


class List(unittest.TestCase):
    def test_counts_own_first_and_the_rest_reachable(self):
        out = run(FAKE + r'''
s = S()
first = H.slicer_presets(s, {"action": "list"})
again = H.slicer_presets(s, {})
fil = H.slicer_presets(s, {"kind": "filament"})
q = H.slicer_presets(s, {"query": "x1"})
none = H.slicer_presets(s, {"limit": 0})
allp = H.slicer_presets(s, {"kind": "process", "limit": 500})
OUT.update(first=first, again=again, fil=fil, q=q, none=none, allp=allp, asked=asked)
try:
    H.slicer_presets(s, {"limit": 501})
except Exception as e:
    OUT["bad"] = [getattr(e, "code", None), getattr(e, "message", str(e))]
OUT["size"] = len(json.dumps(first))
''')
        f = out["first"]
        self.assertEqual(f["from"], ["/presets/system", "/presets/user"])
        self.assertIn("next", f)
        self.assertEqual(f["filament"]["count"], 91)
        self.assertEqual(f["filament"]["own"], 1)
        self.assertEqual(f["filament"]["presets"][0], {"name": "My PETG", "own": True})
        self.assertEqual(len(f["filament"]["presets"]), 1 + 10)
        self.assertEqual(f["filament"]["more"], 80)
        self.assertEqual(f["machine"]["own"], 0)
        self.assertTrue(all(isinstance(x, str) for x in f["machine"]["presets"]))
        self.assertLess(out["size"], 2500)          # was about 10 000 characters
        # said once: the folders and next are not repeated
        self.assertNotIn("from", out["again"])
        self.assertNotIn("next", out["again"])
        self.assertEqual(out["again"]["saidBefore"], ["from", "next"])
        # a kind or a query shows more; limit up to 500 shows everything
        self.assertEqual(len(out["fil"]["filament"]["presets"]), 1 + 50)
        self.assertEqual(list(k for k in out["fil"] if k in ("machine", "process", "filament")), ["filament"])
        self.assertEqual(out["q"]["machine"]["presets"], ["Bambu Lab X1 Carbon 0.4 nozzle"])
        self.assertEqual(out["none"]["process"], {"count": 81, "own": 1, "presets": [{"name": "My 0.20mm", "own": True}], "more": 80})
        self.assertEqual(len(out["allp"]["process"]["presets"]), 81)
        self.assertNotIn("more", out["allp"]["process"])
        self.assertTrue(all(n > 500 for n in out["asked"]))   # every match read, so counts and more are whole
        self.assertEqual(out["bad"][0], "invalid_input")

    def test_an_orcalink_without_limit(self):
        out = run(FAKE + r'''
def old(slicer, kind=None, query=None):
    return {"filament": {"count": 91, "presets": [{"name": "My PETG", "own": True}] + [{"name": f"Generic PLA {i}"} for i in range(59)]}}
SP.listing = staticmethod(old)
OUT["got"] = H.slicer_presets(S(), {"kind": "filament", "limit": 500})["filament"]
''')
        self.assertEqual(out["got"]["count"], 91)
        self.assertEqual(len(out["got"]["presets"]), 60)
        self.assertEqual(out["got"]["more"], 31)


if __name__ == "__main__":
    unittest.main()
