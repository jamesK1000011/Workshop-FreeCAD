# SPDX-License-Identifier: LGPL-2.1-or-later
# A handler's refusal when no host lends one: the shape of Agent Link's
# ToolError (code, message), so the same raise reads the same either way.


class Refusal(Exception):
    """A request refused, with what to do instead. code: invalid_input,
    not_found, invalid_state, unavailable, failed."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message
