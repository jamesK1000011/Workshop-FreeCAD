# SPDX-License-Identifier: LGPL-2.1-or-later
# The records format is Agent Link's own (agentlink/store.py), so each reads
# what the other wrote: the two files stay the same, byte for byte, wherever
# Agent Link is checked out beside this (AGENTLINK_DIR, or on the path).
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


def agentlink_store():
    for d in [os.environ.get("AGENTLINK_DIR")] + sys.path:
        if d and os.path.isfile(os.path.join(d, "agentlink", "store.py")):
            return os.path.join(d, "agentlink", "store.py")
    return None


class Records(unittest.TestCase):
    def test_same_format_as_agent_link(self):
        p = agentlink_store()
        if not p:
            self.skipTest("Agent Link is not checked out beside this")
        with open(p, "rb") as a, open(os.path.join(HERE, "..", "workshop_common", "records.py"), "rb") as b:
            self.assertEqual(a.read(), b.read(), "workshop_common/records.py and Agent Link's store.py differ: copy one over the other")

    def test_refused_carries_a_code(self):
        from workshop_common import Refused

        e = Refused("x: 1 to 10.")
        self.assertEqual((e.code, e.message, str(e)), ("invalid_input", "x: 1 to 10.", "x: 1 to 10."))


if __name__ == "__main__":
    unittest.main()
