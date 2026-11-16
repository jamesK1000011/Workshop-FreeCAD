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


    def test_documents_tool_unlisted_while_the_service_is_offered(self):
        out = run(SETUP + r'''
class Tool:
    def __init__(self, name, fn):
        self.name, self.fn, self.group = name, fn, "share"
calls = []
hooks.tools_from_data = lambda folder, group, handlers, who: [Tool(n, f) for n, f in handlers.items()]
proto = types.ModuleType("agentlink.protocol")
class ToolError(Exception):
    def __init__(self, code, message):
        super().__init__(message); self.code, self.message = code, message
proto.ToolError = ToolError
al.protocol = proto
sys.modules["agentlink.protocol"] = proto
from workshop_documents import fam_share as F
ts = F.tools(types.SimpleNamespace())
lp = next(t for t in ts if t.name == "library_pack")
listed = lambda: [t.name for t in ts if not getattr(t, "alias_of", None)]  # Agent Link's Server.listed
OUT["offered"] = listed()
OUT["alias"] = lp.alias_of
OUT["called"] = lp.fn({"license": "CC0-1.0"})  # still callable by name, routed to the service
svc["v"] = None
OUT["alone"] = listed()
lp.alias_of = "kept"  # Agent Link may still set an alias of its own
OUT["set"] = lp.alias_of
OUT["cls"] = type(lp).__name__
''')
        self.assertEqual(out["offered"], [])
        self.assertEqual(out["alias"], "pack_write")
        self.assertEqual(out["called"]["by"], "ScanRuler-FreeCAD")
        self.assertEqual(out["alone"], ["library_pack"])
        self.assertEqual(out["set"], "kept")
        self.assertEqual(out["cls"], "Tool")


if __name__ == "__main__":
    unittest.main()
