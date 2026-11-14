# SPDX-License-Identifier: LGPL-2.1-or-later
# AddonKit's addonkit.records: the shared library every add-on uses (this module
# is that one). Kept so add-ons written for workshop_common still work.
import sys

from addonkit import records  # noqa: F401
from addonkit import records as _impl  # noqa: E402

sys.modules[__name__] = _impl
