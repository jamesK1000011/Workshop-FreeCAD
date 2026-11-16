# SPDX-License-Identifier: LGPL-2.1-or-later
# SafetyNet's own refusal: a code (invalid_input, not_found, invalid_state,
# not_allowed, unavailable, failed) and a message saying what to do instead.
# Agent Link's families turn it into a refusal to the agent; without Agent
# Link it is a plain exception.


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message
