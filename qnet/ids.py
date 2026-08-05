# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""ULIDs - the ids on ``event``, ``ask`` and ``session`` (contracts/mqtt.md).

The contract says "ULID" and the fixtures carry real ones, so ids are generated
rather than faked: 48-bit millisecond timestamp + 80 random bits, Crockford
base32, 26 characters. Lexicographic order is time order, which is the only
property anything in QNet actually leans on.

Twelve lines beats a dependency, and both the engine and ``dev/inject.py`` need
it - one implementation, so an id minted by the injector is indistinguishable
from one minted by the agent.
"""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid(ts: float | None = None) -> str:
    """A fresh ULID; ``ts`` (unix seconds) defaults to now."""
    ms = int((time.time() if ts is None else ts) * 1000)
    value = (ms << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_CROCKFORD[(value >> shift) & 0x1F] for shift in range(125, -1, -5))
