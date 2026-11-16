# SPDX-License-Identifier: LGPL-2.1-or-later
# Each part's tools for agents are data (its data/tools.json, in Agent
# Link for FreeCAD's tool-data format). Agent Link binds them; only the
# agentlink_families side calls build(), so the API never imports Agent Link.
import json
import os

ACCEPTS = ">=1.0,<2"


def here(module_file):
    """The data folder beside a package's module."""
    return os.path.join(os.path.dirname(os.path.abspath(module_file)), "data")


def defs(folder):
    """The tool definitions in folder/tools.json, in the file's order."""
    with open(os.path.join(folder, "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def build(folder, group, handlers, who="this add-on"):
    """Agent Link Tools for one group, each bound to its handler by name."""
    from agentlink import hooks

    return hooks.tools_from_data(folder, group, handlers, who)


def agent(fn):
    """fn as a handler called outside build() (a tool extension): this
    add-on's Refused reaches the agent as a refusal."""

    def run(*a):
        from agentlink.tooldata import refusing

        return refusing(fn)(*a)

    return run
