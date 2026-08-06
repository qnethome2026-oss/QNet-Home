# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Path bootstrap for the voice-node tests.

The voice node is an Arduino App Lab application, not an installed package: on
the device its modules live side by side in ``/app/python`` and import each
other by bare name (``from config import ...``). The tests import them the same
way, so the app package dir goes on ``sys.path`` here — and the repo root too,
so ``tests.voice.fakes`` resolves without touching the root ``tests/conftest.py``
harness.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_PYTHON = REPO_ROOT / "apps" / "ventuno-q" / "qnet-voice-node" / "python"

for entry in (str(REPO_ROOT), str(NODE_PYTHON)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
