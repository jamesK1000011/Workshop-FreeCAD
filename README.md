<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Workshop for FreeCAD

> Not affiliated with or endorsed by the FreeCAD project or the FreeCAD project association (FPA); FreeCAD is the FPA's trademark. Get FreeCAD itself from [freecad.org](https://freecad.org).

FreeCAD add-ons for making things. Each folder is an add-on of its own, with
its own workbench, task panels and Python API, and works with no other
add-on installed. When
[Agent Link for FreeCAD](https://github.com/jamesK1000011/AgentLink-FreeCAD) is
installed, the same functions are also tools an AI agent can call.

| Add-on | What it does |
|---|---|
| [Workshop Parts](Parts/README.md) | Standard parts made to size: Gridfinity bins and baseplates, project boxes with lids, enclosures round a circuit board. |
| [Workshop Make](Make/README.md) | Getting a part made: setups, a printability check and one verdict, fits and hardware holes for your printer, threads, parts encased mid-print, mass, slicing, printers on the network, and output for laser, waterjet and mill. |
| [Workshop Electronics](Electronics/README.md) | KiCad boards read without KiCad, enclosures round them, PCB order packages, channels for wire inside printed parts. |
| [Workshop Documents](Documents/README.md) | Drawing sheets, assembly manuals, patent figures and a draft, and library packs to share. |

## Install

You need FreeCAD 1.0 or newer.

- **Addon Manager:** add `https://github.com/jamesK1000011/Workshop-FreeCAD`
  (branch `main`) under **Edit ▸ Preferences ▸ Addon Manager ▸ Custom
  repositories**, then install **Workshop for FreeCAD**. You get Parts, Make,
  Electronics and Documents together.
- **Agent Link:** the Agent Link extension for Claude Desktop installs each
  add-on on its own (`Mod/WorkshopParts`, `Mod/WorkshopMake`,
  `Mod/WorkshopElectronics`, `Mod/WorkshopDocuments`).
- **By hand:** copy the folders you want into FreeCAD's `Mod` folder under
  those names.

Use one way, not two. Each add-on's README says what you see in FreeCAD and
what an agent can do with it.

## Uninstall

- **Addon Manager**: Tools ▸ Addon manager ▸ Workshop for FreeCAD ▸
  Uninstall, then restart FreeCAD. This removes all four.
- **Installed by Agent Link or by hand**: delete the add-on folders from
  FreeCAD's `Mod` folder (`WorkshopParts`, `WorkshopMake`,
  `WorkshopElectronics`, `WorkshopDocuments`) and restart FreeCAD.
- **Your files** are yours to keep or delete: what the add-ons write goes
  beside the open document, or to `~/Workshop` when it has not been saved.

## Privacy

No add-on here has telemetry, and none sends anything anywhere on its own.
The one network use is Workshop Make's printer connection: when you ask it
to, it talks to printers on your own network (OctoPrint, Moonraker,
PrusaLink) at the addresses you give it. Their keys and passwords are kept
in a file only your user can read, and are never shown back. Library packs
from Workshop Documents are scrubbed of personal details before they are
written. With Agent Link, what the agent reads goes to the AI provider your
MCP client uses, under that provider's terms.

## Tests

CI runs each add-on alone, then with Agent Link beside it:

```
AGENTLINK_HOME=$(mktemp -d) python3 -m unittest discover -s tests
cd Parts && AGENTLINK_HOME=$(mktemp -d) PYTHONPATH=. python3 -m unittest discover -s tests
```

## Licence and history

LGPL-2.1-or-later (`LICENSE`); the data files are CC BY 4.0 (`LICENSE-DATA`).
Each add-on carries its own `LICENSE`, `LICENSES/`, `REUSE.toml` and
`CHANGELOG.md`; `CHANGELOG.md` here covers the suite as the Addon Manager
installs it. Parts moved here from Agent Link for FreeCAD on 14 Nov 2026;
its history before that is in that repository (`agentlink/gridfinity.py`,
`agentlink/boxes.py` and `agentlink/families/parts.py` up to commit c954763).
