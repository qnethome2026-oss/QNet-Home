# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The loop and the rails (DESIGN.md §6).

The agent decides what to say, which allowed tool to call, and whether a phase
goal is met. The engine guarantees everything consequential regardless of the
model:

* timers fire on schedule; a missing ``timer`` simply means no timer
* ``on_enter`` actions run before the agent's first turn, once per SESSION
* tools outside the current phase are refused and logged
* cancel is an engine-level interrupt matched before the agent sees a transcript
* the responder brief is an interrupt, not a session (§12)
* every session writes ``data/sessions/<room>__<skill>__<started_at>.jsonl``
  and publishes the identical stream to ``qnet/session/<id>``

Exit resolution, one rule: an exit whose name matches a phase id jumps to that
phase; any other name ends the session with that label as its final state.

STUB - implemented in T1.3 (skeleton) and T2.2 (phases, timers, cancel, logging).
"""

from __future__ import annotations


async def run_phase(phase, session):
    """Run one phase to its exit. Not implemented yet (T2.2)."""
    raise NotImplementedError("qnet.agent.engine is a T0.4 stub; built in T1.3/T2.2")


async def run(config: dict, use_llm: bool = True) -> int:
    """Connect to the broker and serve sessions. Not implemented yet (T1.3)."""
    raise NotImplementedError("qnet.agent.engine is a T0.4 stub; built in T1.3/T2.2")
