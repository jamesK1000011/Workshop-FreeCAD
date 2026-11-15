# SPDX-License-Identifier: LGPL-2.1-or-later
# Release readiness of the repository itself, without FreeCAD: the root
# package.xml (the Addon Manager's one install of all the add-ons) names each
# add-on's workbench as its InitGui registers it, the repository's own files
# state their licence (each add-on folder checks its own in its
# tests/test_release.py), the README links every add-on, and no bytecode is
# tracked.
import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = [d for d in sorted(os.listdir(ROOT)) if os.path.isfile(os.path.join(ROOT, d, "package.xml"))]
MAIN = "LGPL-2.1-or-later"
SOURCE = (".py", ".js", ".mjs", ".sh")
NS = {"p": "https://wiki.freecad.org/Package_Metadata"}


def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return [f for f in out.splitlines() if os.path.exists(os.path.join(ROOT, f))]


def reuse_annotations():
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


class RootPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import xml.etree.ElementTree as ET

        cls.root = ET.parse(os.path.join(ROOT, "package.xml")).getroot()

    def one(self, tag, under=None):
        el = (under if under is not None else self.root).find("p:" + tag, NS)
        self.assertIsNotNone(el, tag)
        self.assertTrue((el.text or "").strip(), tag)
        return el

    def test_required(self):
        self.assertEqual(self.root.tag, "{%s}package" % NS["p"])
        self.assertEqual(self.root.get("format"), "1")
        for tag in ("name", "description", "version", "date", "maintainer", "license", "icon", "freecadmin"):
            self.one(tag)
        self.assertRegex(self.one("version").text, r"^\d+\.\d+\.\d+$")
        self.assertTrue(self.one("maintainer").get("email"))
        lics = self.root.findall("p:license", NS)
        self.assertEqual(lics[0].text.strip(), MAIN)
        for lic in lics:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, lic.get("file"))), lic.get("file"))
        urls = {u.get("type"): (u.text or "").strip() for u in self.root.findall("p:url", NS)}
        for kind in ("repository", "bugtracker", "readme"):
            self.assertTrue(urls.get(kind, "").startswith("https://"), kind)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("icon").text.strip())))
        self.assertGreaterEqual(len(self.root.findall("p:tag", NS)), 1)

    def test_each_workbench_is_its_addons(self):
        """One workbench per add-on that registers one, each in its folder,
        the same classname and freecadmin as the add-on's own package.xml."""
        import xml.etree.ElementTree as ET

        wbs = {self.one("subdirectory", wb).text.strip(): wb for wb in self.root.findall("p:content/p:workbench", NS)}
        want = []
        for d in ADDONS:
            own = ET.parse(os.path.join(ROOT, d, "package.xml")).getroot()
            for w in own.findall("p:content/p:workbench", NS):
                want.append(d)
                self.assertIn(d, wbs, d)
                cls = self.one("classname", wbs[d]).text.strip()
                self.assertEqual(cls, w.find("p:classname", NS).text.strip(), d)
                # InitGui.py only calls its package's workbench.add(); the class
                # lives in that module (FreeCAD's exec() hides InitGui's names).
                initgui = open(os.path.join(ROOT, d, "InitGui.py"), encoding="utf-8").read()
                pkg = re.search(r"(?m)^from (\w+) import workbench as _\1_workbench$", initgui).group(1)
                self.assertRegex(initgui, r"(?m)^_%s_workbench\.add\(FreeCADGui\)" % pkg)
                built = open(os.path.join(ROOT, d, pkg, "workbench.py"), encoding="utf-8").read()
                self.assertRegex(built, r"(?m)^    class %s\(Gui\.Workbench\)" % re.escape(cls))
                self.assertTrue(os.path.isfile(os.path.join(ROOT, self.one("icon", wbs[d]).text.strip())), d)
                self.assertEqual(own.find("p:freecadmin", NS).text, self.one("freecadmin").text)
        self.assertEqual(sorted(wbs), sorted(want))
        self.assertGreaterEqual(len(want), 4)


class Files(unittest.TestCase):
    def test_root_files_have_a_licence(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        notes = reuse_annotations()
        missing = []
        for f in files:
            if f.split("/", 1)[0] in ADDONS or re.fullmatch(r"LICEN[CS]E([-.].*)?", f) or f.startswith("LICENSES/"):
                continue
            with open(os.path.join(ROOT, f), "rb") as fh:
                head = fh.read(600).decode("utf-8", "replace")
            if re.search(r"SPDX-License-Identifier:\s*" + re.escape(MAIN), head):
                continue
            if f.endswith(SOURCE) or not any(lic == MAIN and any(_match(f, g) for g in globs) for globs, lic in notes):
                missing.append(f)
        self.assertEqual(missing, [], "no SPDX header or REUSE.toml entry")

    def test_each_addon_has_release_files(self):
        for d in ADDONS:
            for f in ("README.md", "CHANGELOG.md", "LICENSE", "REUSE.toml", "tests/test_release.py"):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, d, f)), f"{d}/{f}")

    def test_readme_links_every_addon(self):
        text = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        for d in ADDONS:
            self.assertIn(f"({d}/README.md)", text)

    def test_no_bytecode_tracked(self):
        files = tracked()
        if files is None:
            self.skipTest("not a git checkout")
        self.assertEqual([f for f in files if "__pycache__" in f or f.endswith(".pyc")], [])


if __name__ == "__main__":
    unittest.main()
