# SPDX-License-Identifier: LGPL-2.1-or-later
"""Workshop for FreeCAD's shared pieces: the records kept in a document (setups,
specs, materials, the printer's fit calibration — the same format Agent Link
keeps, so either reads what the other wrote), shape helpers, fits, the
refusal every add-on raises, and a parameter form for the commands."""

VERSION = "0.1.0"


class Refused(ValueError):
    """A request an add-on will not carry out, with what to do instead.
    code: invalid_input, not_found, invalid_state, unavailable."""

    def __init__(self, message, code="invalid_input"):
        super().__init__(message)
        self.code = code
        self.message = message
