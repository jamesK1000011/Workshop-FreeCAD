# SPDX-License-Identifier: LGPL-2.1-or-later
# This part has no workbench of its own since it joined Workshop: its
# commands are registered and placed by workshop/workbench.py. add() is left
# for an old WorkshopParts folder's InitGui.py still beside Workshop, so that it
# does nothing instead of failing (workshop/stale.py says the folder is
# there, in one line).


def add(Gui=None):
    return None
