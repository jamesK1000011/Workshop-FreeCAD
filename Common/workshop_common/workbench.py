# SPDX-License-Identifier: LGPL-2.1-or-later
# One "Workshop" workbench for every Workshop add-on installed: each adds
# its commands with add(menu, [command names]) from its InitGui.py, and the
# workbench shows them in a toolbar and a menu of their own.

MENUS = {}


def add(menu, names):
    MENUS.setdefault(menu, [])
    for n in names:
        if n not in MENUS[menu]:
            MENUS[menu].append(n)
