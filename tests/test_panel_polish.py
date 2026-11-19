# SPDX-License-Identifier: LGPL-2.1-or-later
# The panels, read as code (no Qt, no FreeCAD): every button, field, box and
# list that a person uses has a tooltip, and the panel code has no fixed
# "#rrggbb" colour. Colours come from the theme module (palette, theme
# accents) so that text reads in a light and a dark theme. Data colour maps
# and marks stay in their own modules (ALLOWED below).
import ast
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The modules that build panels and dialogs.
PANELS = ("safetynet/panel.py", "safetynet/commands.py", "safetynet/startup.py", "workshop_documents/panel.py",
          "workshop_documents/taskpanels.py", "workshop_parts/form.py", "workshop_make/panel.py",
          "workshop_make/taskpanels.py", "workshop_electronics/taskpanels.py", "workshop/layout.py")
# Interactive widgets that must have a tooltip.
CONTROLS = {"QPushButton", "QToolButton", "QLineEdit", "QSpinBox", "QDoubleSpinBox", "QComboBox",
            "QCheckBox", "QRadioButton", "QSlider", "QPlainTextEdit", "QTextEdit"}
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
# True: a named constant at module level (a status lamp, a mark colour, a
# 3D grip) may hold "#rrggbb"; only code inside a function may not.
CONSTANTS_OK = True


def _name(f):
    return getattr(f, "attr", None) or getattr(f, "id", None)


def _made(value):
    """The control class a value makes: QPushButton(...) or a wrapper
    around one (narrow.grow(QLineEdit()))."""
    if isinstance(value, ast.Call):
        if _name(value.func) in CONTROLS:
            return _name(value.func)
        for a in value.args:
            got = _made(a)
            if got:
                return got
    return None


def untipped(path):
    """[(line, class, target)] of controls made in path with no setToolTip
    on the same target in the same function (or, for self.x, the class)."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    scopes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    class_tips = {}
    for c in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        class_tips[id(c)] = {ast.unparse(n.func.value) for n in ast.walk(c)
                             if isinstance(n, ast.Call) and _name(n.func) == "setToolTip" and isinstance(n.func, ast.Attribute)}
    owner = {}
    for c in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for n in ast.walk(c):
            owner.setdefault(id(n), c)
    seen = set()
    for fn in scopes:
        if not isinstance(fn, ast.FunctionDef):
            continue
        tips = {ast.unparse(n.func.value) for n in ast.walk(fn)
                if isinstance(n, ast.Call) and _name(n.func) == "setToolTip" and isinstance(n.func, ast.Attribute)}
        cls = owner.get(id(fn))
        if cls is not None:
            tips |= class_tips[id(cls)]
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and _made(n.value):
                for t in n.targets:
                    targets = t.elts if isinstance(t, ast.Tuple) else [t]
                    vals = n.value.elts if isinstance(n.value, ast.Tuple) else [n.value] * len(targets)
                    for tt, vv in zip(targets, vals):
                        k = ast.unparse(tt)
                        if _made(vv) and k not in tips and (n.lineno, k) not in seen:
                            seen.add((n.lineno, k))
                            out.append((n.lineno, _made(vv), k))
    return out


class PanelTooltips(unittest.TestCase):
    def test_every_control_has_a_tooltip(self):
        missing = []
        for rel in PANELS:
            missing += [f"{rel}:{line} {cls} {name}" for line, cls, name in untipped(os.path.join(ROOT, rel))]
        self.assertEqual(missing, [])

    def test_the_check_finds_a_control_with_no_tooltip(self):
        import tempfile

        src = "def f(Q):\n    a = Q.QPushButton('A')\n    a.setToolTip('Do A.')\n    b = Q.QLineEdit()\n"
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(src)
        try:
            self.assertEqual(untipped(fh.name), [(4, "QLineEdit", "b")])
        finally:
            os.unlink(fh.name)


class PanelColours(unittest.TestCase):
    def test_no_fixed_hex_colour_in_panel_code(self):
        found = []
        for rel in PANELS:
            tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
            roots = [f for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.Lambda))] if CONSTANTS_OK else [tree]
            for n in (x for r in roots for x in ast.walk(r)):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and HEX.search(n.value):
                    found.append(f"{rel}:{n.lineno} {HEX.search(n.value).group(0)}")
        self.assertEqual(sorted(set(found)), [])


if __name__ == "__main__":
    unittest.main()
