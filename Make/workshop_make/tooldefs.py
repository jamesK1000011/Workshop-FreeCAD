# SPDX-License-Identifier: LGPL-2.1-or-later
# Make's tools for agents are data: data/tools.json holds each tool's name,
# description, arguments, group and whether it changes the document; the
# families bind a handler to each name. Agent Link reads the same file to
# list them, and the README's tool table is made from it.
import os

from addonkit import data

HERE = os.path.dirname(os.path.abspath(__file__))
ACCEPTS = ">=1.0,<2"


def defs():
    return data.load(os.path.join(HERE, "data"), "tools", accepts=ACCEPTS, user=False)["entries"]


def build(group, handlers):
    """Agent Link Tools for one group, in the file's order: every tool of the
    group needs a handler and every handler a tool."""
    from agentlink.protocol import Tool

    mine = {k: v for k, v in defs().items() if v["group"] == group}
    missing, extra = set(mine) - set(handlers), set(handlers) - set(mine)
    if missing or extra:
        raise RuntimeError(f"Make's {group} tools: no handler for {sorted(missing)}, no definition for {sorted(extra)}")
    return [Tool(k, v["description"], v["inputSchema"], handlers[k], changes=v.get("changes", False)) for k, v in mine.items()]
