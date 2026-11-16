# SPDX-License-Identifier: LGPL-2.1-or-later
# Library Pack by ScanRuler's pack through Agent Link's library_pack service
# when it is offered; Documents' own pack only as the fallback.
import unittest

from _stubs import run

SETUP = r'''
import types
from workshop_documents.handlers import share as S
asked = []
class Svc:
    NAME = "ScanRuler-FreeCAD"
    def pack(self, session, args):
        asked.append(args)
        if args.get("license") == "bad":
            e = Exception("no"); e.code, e.message = "invalid_input", "license: ScanRuler's words"; raise e
        if args.get("license") == "boom":
            raise RuntimeError("disk full")
        return {"pack": "/o/p.zip"}
svc = {"v": Svc()}
hooks = types.ModuleType("agentlink.hooks")
hooks.service = lambda n: svc["v"] if n == "library_pack" else None
al = types.ModuleType("agentlink"); al.hooks = hooks
sys.modules.update({"agentlink": al, "agentlink.hooks": hooks})
S.own_pack = lambda s, a: {"pack": "/o/own.zip"}
'''


class Pack(unittest.TestCase):
    def test_scanruler_first_documents_after(self):
        out = run(SETUP + r'''
OUT["svc"] = S.library_pack(None, {"license": "CC0-1.0", "provider": "auto"})
OUT["asked"] = asked
OUT["mine"] = S.library_pack(None, {"license": "CC0-1.0", "provider": "documents"})
OUT["boom"] = S.library_pack(None, {"license": "boom"})
try:
    S.library_pack(None, {"license": "bad"})
except Exception as e:
    OUT["refused"] = e.message
svc["v"] = None
OUT["none"] = S.library_pack(None, {"license": "CC0-1.0"})
''')
        self.assertEqual(out["svc"], {"pack": "/o/p.zip", "by": "ScanRuler-FreeCAD"})
        self.assertEqual(out["asked"][0], {"license": "CC0-1.0"})
        self.assertEqual(out["mine"], {"pack": "/o/own.zip", "by": "Workshop Documents"})
        self.assertEqual(out["boom"]["by"], "Workshop Documents")
        self.assertIn("disk full", out["boom"]["serviceNote"])
        self.assertEqual(out["refused"], "license: ScanRuler's words")
        self.assertEqual(out["none"], {"pack": "/o/own.zip", "by": "Workshop Documents"})


if __name__ == "__main__":
    unittest.main()
