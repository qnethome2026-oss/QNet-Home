# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""subscribe look -> latest frame -> VLM -> publish looked (DESIGN.md §5, §13).

Answers about its own frame only and never sends the frame: it reads the latest
frame ``vision.py`` left in shared memory, downscales to roughly 640 px, asks
the node-local Qwen3-VL through the ``openai`` client pointed at ``geniex
serve``, and replies with a sentence. Only text crosses the wire.

Subscribes: ``qnet/look`` (broadcast). Publishes: ``qnet/<room>/looked``.

STUB - implemented in T6.3.
"""

from __future__ import annotations


def main() -> int:
    """Entry point for the look service. Not implemented yet (T6.3)."""
    raise NotImplementedError("qnet.node.look is a T0.4 stub; built in T6.3")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
