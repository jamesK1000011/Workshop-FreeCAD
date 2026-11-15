# SPDX-License-Identifier: LGPL-2.1-or-later
# Release readiness without FreeCAD: the README's tool list is current, the
# licence of every file in this add-on is stated (a REUSE-style check, for
# when the `reuse` tool is not installed), package.xml is what the Addon
# Manager needs, and the changelog has an Unreleased section. This add-on's
# own copy (Workshop add-ons share no library); ROOT is this add-on's folder.
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PKG = "workshop_parts"
WORKBENCH = "WorkshopPartsWorkbench"  # None: registers no workbench
TOOLS = True  # README carries a generated tool list
DATA = True  # data/ files under CC-BY-4.0

MAIN = "LGPL-2.1-or-later"
SOURCE = (".py", ".js", ".mjs", ".sh")
URLS = ("repository", "bugtracker", "readme")
NS = {"p": "https://wiki.freecad.org/Package_Metadata"}


def tracked():
    """This add-on's tracked files, relative to its folder."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [f for f in out.splitlines() if os.path.exists(os.path.join(ROOT, f))]


def reuse_annotations():
    """(globs, licence) pairs from REUSE.toml, read without tomllib."""
    out, globs = [], None
    for line in open(os.path.join(ROOT, "REUSE.toml"), encoding="utf-8"):
        m = re.match(r"\s*path\s*=\s*(.+)", line)
        if m:
            globs = re.findall(r'"([^"]+)"', m.group(1))
        m = re.match(r'\s*SPDX-License-Identifier\s*=\s*"([^"]+)"', line)
        if m and globs is not None:
            out.append((globs, m.group(1)))
            globs = None
    return out


def _match(path, glob):
    rx = re.escape(glob).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.fullmatch(rx, path) is not None


def _licence_file(f):
    return re.fullmatch(r"LICEN[CS]E([-.].*)?", f) is not None or f.startswith("LICENSES/")


class Readme(unittest.TestCase):
    def setUp(self):
        self.text = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()

    def test_tool_list_is_current(self):
        if not TOOLS:
            self.skipTest("no tools")
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import gen_readme_tools
        finally:
            sys.path.pop(0)
        self.assertEqual(gen_readme_tools.render(self.text), self.text, "run python3 tools/gen_readme_tools.py")
        self.assertGreater(gen_readme_tools.block().count("\n| `"), 0)

    def test_licence_and_credits(self):
        self.assertRegex(self.text, r"(?m)^## Licence")
        self.assertIn(MAIN, self.text)


class Licences(unittest.TestCase):
    def test_every_file_has_a_licence(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        notes = reuse_annotations()
        missing, wrong = [], []
        for f in files:
            if _licence_file(f):
                continue
            with open(os.path.join(ROOT, f), "rb") as fh:
                head = fh.read(600).decode("utf-8", "replace")
            m = re.search(r"SPDX-License-Identifier:\s*([^\s*>-][^\s>]*)", head)
            if m:
                ids = [m.group(1)]
            else:
                ids = [lic for globs, lic in notes if any(_match(f, g) for g in globs)]
                if f.endswith(SOURCE) or not ids:
                    missing.append(f)
                    continue
            for i in ids:
                for part in re.split(r"\s+(?:AND|OR|WITH)\s+", i):
                    if part != MAIN and not os.path.exists(os.path.join(ROOT, "LICENSES", part + ".txt")):
                        wrong.append(f"{f}: {part}")
        self.assertEqual(missing, [], "no SPDX header or REUSE.toml entry")
        self.assertEqual(wrong, [], "licence text not in LICENSES/")

    def test_main_licence_is_lgpl(self):
        head = open(os.path.join(ROOT, "LICENSE"), encoding="utf-8").read(400)
        self.assertIn("LESSER GENERAL PUBLIC LICENSE", head)
        self.assertIn("Version 2.1", head)

    def test_data_licence(self):
        if not DATA:
            self.skipTest("no data files")
        text = open(os.path.join(ROOT, "LICENSES", "CC-BY-4.0.txt"), encoding="utf-8").read()
        self.assertIn("Attribution 4.0 International", text)
        self.assertIn("CC BY 4.0", open(os.path.join(ROOT, "LICENSE-DATA"), encoding="utf-8").read())

    def test_no_bytecode_tracked(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if "__pycache__" in f or f.endswith(".pyc")], [])


class Changelog(unittest.TestCase):
    def test_unreleased_section(self):
        text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
        self.assertRegex(text, r"(?m)^## \[?Unreleased\]?")


class PackageXml(unittest.TestCase):
    """package.xml as FreeCAD's Addon Manager reads it."""

    @classmethod
    def setUpClass(cls):
        import xml.etree.ElementTree as ET

        cls.root = ET.parse(os.path.join(ROOT, "package.xml")).getroot()

    def one(self, tag, under=None):
        el = (under if under is not None else self.root).find("p:" + tag, NS)
        self.assertIsNotNone(el, tag)
        self.assertTrue((el.text or "").strip(), tag)
        return el

    def test_format_and_required(self):
        self.assertEqual(self.root.tag, "{%s}package" % NS["p"])
        self.assertEqual(self.root.get("format"), "1")
        for tag in ("name", "description", "version", "date", "maintainer", "license", "freecadmin"):
            self.one(tag)
        if WORKBENCH:
            self.one("icon")
        self.assertRegex(self.one("version").text, r"^\d+\.\d+\.\d+$")
        self.assertRegex(self.one("date").text, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(self.one("freecadmin").text, r"^\d+\.\d+(\.\d+)?$")

    def test_version_matches_package(self):
        src = open(os.path.join(ROOT, PKG, "__init__.py"), encoding="utf-8").read()
        m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), self.one("version").text.strip())

    def test_maintainer_and_licence(self):
        self.assertTrue(self.one("maintainer").get("email"), "the format needs an email attribute")
        lics = self.root.findall("p:license", NS)
        self.assertEqual(lics[0].text.strip(), MAIN)
        for lic in lics:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, lic.get("file"))), lic.get("file"))
        if DATA:
            self.assertIn("CC-BY-4.0", [lic.text.strip() for lic in lics])

    def test_urls(self):
        urls = {u.get("type"): (u.text or "").strip() for u in self.root.findall("p:url", NS)}
        for kind in URLS:
            self.assertTrue(urls.get(kind, "").startswith("https://"), kind)
        self.assertTrue(urls["readme"].endswith("/" + os.path.basename(ROOT) + "/README.md"), urls["readme"])

    def test_icons_exist(self):
        icon = self.root.find("p:icon", NS)
        if icon is not None:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, icon.text.strip())))
        for wb in self.root.findall("p:content/p:workbench", NS):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("icon", wb).text.strip())))

    def test_workbench_matches_initgui(self):
        wbs = self.root.findall("p:content/p:workbench", NS)
        initgui = open(os.path.join(ROOT, "InitGui.py"), encoding="utf-8").read()
        if not WORKBENCH:
            self.assertEqual(wbs, [])
            self.assertNotIn("addWorkbench", initgui)
            return
        self.assertEqual(len(wbs), 1)
        for wb in wbs:
            cls = self.one("classname", wb).text.strip()
            self.assertEqual(cls, WORKBENCH)
            self.assertRegex(initgui, r"(?m)^class %s\(FreeCADGui\.Workbench\)" % re.escape(cls))
            self.assertRegex(initgui, r"addWorkbench\(%s\(\)\)" % re.escape(cls))
            sub = self.one("subdirectory", wb).text.strip()
            self.assertTrue(os.path.isfile(os.path.join(ROOT, sub, "InitGui.py")))
            self.one("name", wb)

    def test_tags(self):
        self.assertGreaterEqual(len(self.root.findall("p:tag", NS)), 1)


if __name__ == "__main__":
    unittest.main()
