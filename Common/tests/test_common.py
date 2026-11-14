# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Common is the Workshop workbench over AddonKit: its records,
# shapes, fits and form are AddonKit's own modules, so every add-on and
# Agent Link read and write the same records.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


class Common(unittest.TestCase):
    def test_records_are_addonkits(self):
        import addonkit.records
        from workshop_common import records

        self.assertIs(records, addonkit.records)

    def test_refused_carries_a_code(self):
        from workshop_common import Refused

        import addonkit

        e = Refused("x: 1 to 10.")
        self.assertIs(Refused, addonkit.Refused)
        self.assertEqual((e.code, e.message, str(e)), ("invalid_input", "x: 1 to 10.", "x: 1 to 10."))


if __name__ == "__main__":
    unittest.main()
