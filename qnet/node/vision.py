# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""camera -> fall model -> temporal check -> publish (DESIGN.md §5, §8).

Owns the camera. GStreamer source from config (v4l2 and filesrc), ONNX Runtime
+ QNN for the YOLOv11 fall fine-tune, an N-of-M temporal check, fire-once with
a re-arm window, and a heartbeat on ``qnet/<room>/status``. It also exposes the
latest frame in shared memory so ``look.py`` never opens a second capture.

Publishes: ``qnet/<room>/event`` (kind ``fall.detected``), ``qnet/<room>/status``.

STUB - implemented in T4.2.
"""

from __future__ import annotations


def main() -> int:
    """Entry point for the vision service. Not implemented yet (T4.2)."""
    raise NotImplementedError("qnet.node.vision is a T0.4 stub; built in T4.2")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
