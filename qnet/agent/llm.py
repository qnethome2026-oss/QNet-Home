# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""GenieX client - Gemma 4 E2B on the IQ-9075 (DESIGN.md §10).

``geniex serve`` is OpenAI-compatible, so this is the stock ``openai`` client
with a different ``base_url`` (``http://127.0.0.1:18181/v1``). The prompt
template lives here and only here.

Verified on-device constraints (DESIGN.md §10) that this module must honour:

* SDK-native tool-calling does NOT work on GenieX v0.3.18 - v1 is plain prompt
  -> strip after the last ``<channel|>`` marker -> parse JSON -> validate
  against the phase's allowed actions -> one retry -> escalation path.
* Every request carries GenieX's field names, not OpenAI's:
  ``enable_think: false`` and ``max_completion_tokens`` (``think`` and
  ``max_tokens`` are silently ignored), plus ``nctx: 16384``.
* Requests serialize - one model, one queue.

STUB - implemented in T3.3.
"""

from __future__ import annotations

BASE_URL = "http://127.0.0.1:18181/v1"
NCTX = 16384


async def act(phase, session, heard):
    """Ask the model for one action: say | tool | exit. Not implemented (T3.3)."""
    raise NotImplementedError("qnet.agent.llm is a T0.4 stub; built in T3.3")
