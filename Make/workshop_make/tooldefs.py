# SPDX-License-Identifier: LGPL-2.1-or-later
# Make's tools for agents are data (data/tools.json, Agent Link's tool-data
# format); Agent Link binds them (tooldata.py).
from workshop_make import tooldata as _td

DATA = _td.here(__file__)
ACCEPTS = _td.ACCEPTS


def defs():
    return _td.defs(DATA)


def build(group, handlers):
    return _td.build(DATA, group, handlers, "Make")


_agent = _td.agent
