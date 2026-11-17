# SPDX-License-Identifier: LGPL-2.1-or-later
# The tool descriptions in ASD-STE100 (branch explore/full-ste): at most 20
# words a sentence, and nothing of the original text lost (numbers, units,
# input names, tool names, code names, guard words). scripts/ste_check.py
# does the work; scripts/ste_originals.json is the text main held before.
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import ste_check as S  # noqa: E402


class SteLint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.descs = S.current()
        cls.originals = S.load_originals()

    def test_every_original_tool_is_read(self):
        self.assertEqual(set(self.originals["tools"]) - set(self.descs), set())
        self.assertGreater(len(self.descs), 0)

    def test_sentences_have_at_most_20_words(self):
        faults = S.lint(self.descs, self.originals.get("toolNames", ()))
        self.assertEqual(faults, [], "\n".join(f"{t}: {x}" for t, _, x in faults))

    def test_nothing_of_the_original_is_lost(self):
        faults = S.preservation(self.descs, self.originals)
        self.assertEqual(faults, [], "\n".join(f"{t}: {k}: {x}" for t, k, x in faults))

    def test_every_waiver_has_a_reason(self):
        for key, reason in S.WAIVERS.items():
            self.assertTrue(isinstance(reason, str) and len(reason.split()) >= 3, key)

    def test_the_lint_counts_as_it_says(self):
        # The hub's counting: names in a run of three or more count as one word;
        # quotes, backticks and {...} / [...] literals are not counted.
        self.assertEqual(S.words("Inputs: path, object, units and name.", {"path", "object", "units", "name"}), 2)
        self.assertEqual(S.words("Inputs: path, object, units and name."), 6)
        self.assertEqual(S.words('Give "a quoted literal of many many many words here".'), 1)
        self.assertEqual(S.words("The answer holds { a, b, c, d, e, f }."), 3)
        self.assertEqual(S.words("Tools: scan_open, scan_qa, mesh_densify and maxEdge."), 2)
        self.assertEqual(len(S.sentences("One idea. two: lower case starts a sentence too. For example, e.g. this stays.")), 3)
        self.assertEqual(len(S.sentences("Keys { a. b. c } stay one. 0.5 mm is one.")), 2)

    def test_the_preservation_check_finds_a_loss(self):
        name = sorted(self.originals["tools"])[0]
        old = self.originals["tools"][name]
        cut = {name: dict(old, description="Nothing.")}
        found = S.preservation(cut, {"toolNames": [], "tools": {name: old}})
        if S._numbers(old["description"]) or S._code(old["description"]) or S._guards(old["description"]):
            self.assertTrue(found)
        kept = {name: dict(old)}
        self.assertEqual(S.preservation(kept, {"toolNames": [], "tools": {name: old}}), [])
        self.assertIn((name, "number", "750"), S.preservation({name: dict(old, description="x")}, {"toolNames": [], "tools": {name: dict(old, description="750 000")}}))
        self.assertIn((name, "guard", "never"), S.preservation({name: dict(old, description="x")}, {"toolNames": [], "tools": {name: dict(old, description="It never runs.")}}))


if __name__ == "__main__":
    unittest.main()
