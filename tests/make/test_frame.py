# SPDX-License-Identifier: LGPL-2.1-or-later
# fea_frame: a frame of straight members by beam elements, against beam
# theory (needs CalculiX's ccx, FreeCAD and Agent Link).
import json
import unittest

from _fc import AGENT, caller, server


@unittest.skipUnless(AGENT, "FreeCAD and Agent Link are not both importable here")
class Frame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session, srv = server()
        cls.server = srv
        cls.call = staticmethod(caller(srv))

    def ok(self, name, args=None):
        err, r = self.call(name, args)
        self.assertFalse(err, r)
        return r

    def have(self, tool):
        r = self.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})["result"]
        if tool not in {t["name"] for t in r["tools"]}:
            self.skipTest(f"{tool} is not in this build")

    def test_fea_frame(self):
        self.have("fea_frame")
        import shutil

        if not shutil.which("ccx"):
            self.skipTest("ccx is not installed")
        r = self.ok("fea_frame", {"members": [{"name": "Fr beam", "from": [0, 0, 0], "to": [4000, 0, 0], "section": {"kind": "rect", "b": 38, "d": 184}}], "material": "pla",
                                  "supports": [{"at": [0, 0, 0]}, {"at": [4000, 0, 0], "kind": "roller"}], "loads": [{"member": "Fr beam", "w": 1}], "name": "fr ss"})
        m = r["members"][0]
        I = 38 * 184 ** 3 / 12
        self.assertAlmostEqual(m["deflectionMm"], 5 * 4000 ** 4 / (384 * 3500 * I), delta=1.5)
        self.assertAlmostEqual(m["axialBendingMPa"][1], 2e6 / (38 * 184 ** 2 / 6), delta=0.3)
        self.assertAlmostEqual(r["supports"][0]["reactionN"][2], 2000, delta=40)
        p = self.ok("fea_frame", {"members": [{"name": "L", "from": [0, 0, 0], "to": [0, 0, 3000], "section": {"kind": "box", "b": 100, "d": 100, "t": 5}},
                                              {"name": "R", "from": [4000, 0, 0], "to": [4000, 0, 3000], "section": {"kind": "box", "b": 100, "d": 100, "t": 5}},
                                              {"name": "T", "from": [0, 0, 3000], "to": [4000, 0, 3000], "section": {"kind": "box", "b": 100, "d": 150, "t": 5}}],
                                  "material": "pla", "supports": [{"at": [0, 0, 0], "kind": "fixed"}, {"at": [4000, 0, 0], "kind": "fixed"}],
                                  "loads": [{"at": [0, 0, 3000], "force": [1000, 0, 0]}, {"member": "T", "w": 2}], "name": "fr portal"})
        self.assertEqual(len(p["members"]), 3)
        self.assertEqual(p["loadTotalN"][2], -8000.0)



if __name__ == "__main__":
    unittest.main()
