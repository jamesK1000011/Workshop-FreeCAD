# SPDX-License-Identifier: LGPL-2.1-or-later
# A Workshop add-on's tools for agents are data: its data/tools.json holds
# each tool's name, description, arguments, group and whether it changes the
# document; the add-on binds a handler to each name. Agent Link reads the
# same file to list them, and the README's tool table is made from it.
import os

from addonkit import data

ACCEPTS = ">=1.0,<2"


def defs(folder):
    """The tool definitions in folder/tools.json, in the file's order."""
    return data.load(folder, "tools", accepts=ACCEPTS, user=False)["entries"]


def build(folder, group, handlers, who="this add-on"):
    """Agent Link Tools for one group, in the file's order: every tool of the
    group needs a handler and every handler a tool."""
    from agentlink.protocol import Tool

    mine = {k: v for k, v in defs(folder).items() if v["group"] == group}
    missing, extra = set(mine) - set(handlers), set(handlers) - set(mine)
    if missing or extra:
        raise RuntimeError(f"{who}'s {group} tools: no handler for {sorted(missing)}, no definition for {sorted(extra)}")
    return [Tool(k, v["description"], v["inputSchema"], agent(handlers[k]), changes=v.get("changes", False)) for k, v in mine.items()]


def agent(fn):
    """A handler whose addonkit.Refused reaches the agent as a refusal."""
    from addonkit import Refused
    from agentlink.protocol import ToolError

    def run(*a):
        try:
            return fn(*a)
        except Refused as e:
            raise ToolError(e.code, e.message)

    return run


def here(module_file):
    """The data folder beside a package's module."""
    return os.path.join(os.path.dirname(os.path.abspath(module_file)), "data")
