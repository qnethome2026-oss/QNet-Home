# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""call_emergency - the emergency call, SIMULATED ONLY (DESIGN.md §11, §14).

**Invoked by the engine's ``on_enter``, never by the LLM** - registered
``engine_only=True``. This is the one truly irreversible action in the whole
system, and it is never actually placed: this function builds the exact
payload a real integration would send, writes it to
``data/outbox/emergency_<ts>.json`` with a top-level ``"SIMULATED": true``,
logs the call via ``ctx.log``, and publishes nothing external. The word
SIMULATED appears in both the returned dict and the file - the dashboard's
red "SIMULATED" badge (DESIGN §14) reads directly off this field, and a judge
or bystander must never be able to mistake this for a real call.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from qnet.tools import ToolContext, console_print, register

# Fixed per DESIGN §11 - not configurable. data/ is gitignored; created on demand.
OUTBOX_DIR = Path("data/outbox")


def _resident_name(config: dict) -> str:
    return ((config or {}).get("resident") or {}).get("name") or "the resident"


@register("call_emergency", engine_only=True)
async def call_emergency(ctx: ToolContext) -> dict:
    """Build and file the simulated emergency-call payload. Never raises."""
    ts = time.time()
    payload = {
        "SIMULATED": True,
        "number": (ctx.config or {}).get("emergency_number", "911"),
        "room": ctx.room,
        "resident": _resident_name(ctx.config),
        "session_id": ctx.session_id,
        "ts": round(ts, 1),
        "reason": "no_response_after_escalation",
    }

    try:
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTBOX_DIR / f"emergency_{int(ts * 1000)}.json"
        # utf-8 explicitly, not the platform default.
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        console_print(f"[call_emergency:write-failed] {exc!r}")

    try:
        ctx.log({"event": "tool", "tool": "call_emergency", "result": "SIMULATED"})
    except Exception:
        pass

    return payload
