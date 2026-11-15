# SPDX-License-Identifier: LGPL-2.1-or-later
# Workshop Make's own copy of Agent Link for FreeCAD's refusal.py, trimmed to what Make uses; 14 Nov 2026.
# A refusal that says what to do instead, and version ranges (">=1.0,<2").


class Refused(ValueError):
    """A request this add-on will not carry out, with what to do instead.
    code: invalid_input, not_found, invalid_state, unavailable. Agent Link
    turns it into a refusal (any exception with code and message)."""

    def __init__(self, message, code="invalid_input"):
        super().__init__(message)
        self.code = code
        self.message = message


def _parse(v):
    return tuple(int(x) for x in v.split("."))


def satisfies(spec, version):
    """True when version meets every clause of spec (">=1.0,<2")."""
    have = _parse(version)
    for clause in (c.strip() for c in spec.split(",") if c.strip()):
        for op in (">=", "<=", "==", ">", "<"):
            if clause.startswith(op):
                want = _parse(clause[len(op):].strip())
                n = max(len(have), len(want))
                a, b = have + (0,) * (n - len(have)), want + (0,) * (n - len(want))
                if not {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]:
                    return False
                break
        else:
            raise ValueError(f"version clause {clause!r}: use >=, <=, ==, > or <")
    return True
