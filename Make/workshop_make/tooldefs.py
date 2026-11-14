# SPDX-License-Identifier: LGPL-2.1-or-later
# Make's tools for agents are data (data/tools.json); the binding is Workshop
# Common's, shared by every Workshop add-on.
from workshop_common import tooldefs as _td

DATA = _td.here(__file__)
ACCEPTS = _td.ACCEPTS


def defs():
    return _td.defs(DATA)


def build(group, handlers):
    return _td.build(DATA, group, handlers, "Make")


_agent = _td.agent
