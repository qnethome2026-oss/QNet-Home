# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""MQTT <-> HTTP adapter onto the speech service (DESIGN.md §5, §9).

A translator, not a brain: it decides nothing. It subscribes to
``qnet/<room>/say`` and hands the text to the speech service, and it routes
every transcript three ways, in this order:

    1. responder phrase  -> ``qnet/<room>/ask``   kind ``responder_brief``
    2. session active    -> ``qnet/<room>/heard``
    3. wake phrase       -> ``qnet/<room>/ask``   kind ``query`` (phrase stripped)
    4. anything else     -> discarded

NOTE: routing duplicated in dev/sim.html / qnet/node/voice.py - change both.

STUB - implemented in T1.4.
"""

from __future__ import annotations


def main() -> int:
    """Entry point for the voice adapter. Not implemented yet (T1.4)."""
    raise NotImplementedError("qnet.node.voice is a T0.4 stub; built in T1.4")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
