# SPDX-License-Identifier: LGPL-2.1-or-later
# One agentlink_families module for the whole add-on (workshop's), joining
# each part's families module; tool names unchanged, so Agent Link and the
# prompts that name them keep working. Read with ast: no FreeCAD, no Agent
# Link needed.
import ast
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = ("workshop_parts", "workshop_make", "workshop_electronics", "workshop_documents", "safetynet")
# Every tool name the five add-ons offered before the combine.
BEFORE = {
    "gen_make", "gen_part", "fit", "hw_hole", "thread_lookup", "thread_identify", "thread_cut", "hw_embed", "hw_embed_list", "hw_unembed",
    "hw_pauses", "setup", "part_spec", "dfm_check", "part_review", "slice", "mass_calibrate", "mass_properties", "mass_target",
    "mass_ballast", "slicer_presets", "slice_with", "slice_read", "slice_open", "printer_add", "printer_list", "printer_status",
    "printer_send", "printer_pause", "printer_stop", "cut_check", "cut_export", "mill_check", "mill_export", "fea_frame", "kicad_import",
    "board_enclosure", "pcb_order_package", "printed_channel", "drawing_make", "drawing_exploded", "patent_figures", "patent_draft",
    "library_pack", "history_checkpoint", "history_restore", "macro_save", "macro_list", "macro_show", "macro_approve",
    "macro_unapprove", "macro_run", "app_recover", "pref_history", "pref_rollback",
}


def tool_names():
    names = set()
    for p in PARTS:
        d = os.path.join(ROOT, p)
        data = os.path.join(d, "data", "tools.json")
        if os.path.isfile(data):
            names |= set(json.load(open(data, encoding="utf-8"))["entries"])
        for f in os.listdir(d):
            if f.startswith("fam_") and f.endswith(".py"):
                tree = ast.parse(open(os.path.join(d, f), encoding="utf-8").read())
                for n in ast.walk(tree):
                    if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "Tool" and n.args \
                            and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                        names.add(n.args[0].value)
    return names


class Families(unittest.TestCase):
    def test_one_family_module(self):
        found = []
        for d, dirs, files in os.walk(ROOT):
            dirs[:] = [x for x in dirs if x not in {".git", "__pycache__", "tests", "agentlink-addon", "orcalink-addon"}]
            if "agentlink_families.py" in files:
                found.append(os.path.relpath(d, ROOT))
        self.assertEqual(found, ["workshop"], "Agent Link would find a part's families twice")

    def test_it_joins_every_part(self):
        tree = ast.parse(open(os.path.join(ROOT, "workshop", "__init__.py"), encoding="utf-8").read())
        parts = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PARTS")
        self.assertEqual(parts, PARTS)
        for p in PARTS:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, p, "families.py")), p)
            self.assertTrue(os.path.isdir(os.path.join(ROOT, p, "guides")), p)

    def test_tool_names_unchanged(self):
        self.assertEqual(tool_names(), BEFORE)


if __name__ == "__main__":
    unittest.main()
