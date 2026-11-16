# SPDX-License-Identifier: LGPL-2.1-or-later
# The add-on's one copy of tooldata.py is workshop/tooldata.py; this name
# keeps the old imports working and is the same module object.
import sys

from workshop import tooldata as _one

sys.modules[__name__] = _one
