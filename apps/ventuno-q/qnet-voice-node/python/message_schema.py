# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Ventuno-side parsers for the frozen QNet MQTT contract.

Accept-liberally by design (B2): the hub's contract is frozen with five
consumers implementing it, so this node adapts to the wire, not the other way
around. A `say` needs only ``{text, prio}`` and a session document needs only
``{id, room, state}`` - everything else is optional telemetry that must never
stop a safety line from being spoken or a fall session from being heard.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

# Longer safety text is spoken truncated, never rejected - a responder brief
# that overruns the limit must still make it to the speaker.
MAX_SAY_TEXT_CHARS = 1024


def _decode(payload: bytes | str) -> dict[str, Any]:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def _string(data: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = data.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{key} must be a {'string' if allow_empty else 'non-empty string'}")
    return value.strip()


def _optional_string(data: dict[str, Any], key: str, default: str = "") -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _optional_timestamp(data: dict[str, Any]) -> float:
    value = data.get("ts")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return time.time()
    return float(value)


@dataclass(frozen=True)
class SayCommand:
    message_id: str
    timestamp: float
    room: str | None
    text: str
    priority: str

    @classmethod
    def from_payload(cls, payload: bytes | str) -> "SayCommand":
        data = _decode(payload)
        # prio is required but ANY value is accepted; the controller maps
        # unknown priorities (including our engine's "routine") to lowest.
        priority = data.get("prio")
        if not isinstance(priority, str) or not priority.strip():
            raise ValueError("prio must be a non-empty string")
        text = _string(data, "text")
        if len(text) > MAX_SAY_TEXT_CHARS:
            text = text[:MAX_SAY_TEXT_CHARS]
        # Our engine sends bare {text, prio}: synthesize a local id so the
        # dedupe/priority machinery keeps working per message received.
        message_id = _optional_string(data, "id") or f"local-{uuid.uuid4()}"
        room = _optional_string(data, "room") or None
        return cls(
            message_id=message_id,
            timestamp=_optional_timestamp(data),
            room=room,
            text=text,
            priority=priority.strip(),
        )


@dataclass(frozen=True)
class SessionEvent:
    session_id: str
    timestamp: float
    room: str
    skill: str
    urgency: str
    phase: str
    state: str
    event: str
    data: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: bytes | str) -> "SessionEvent":
        body = _decode(payload)
        # Our engine publishes session snapshots shaped {id, room, skill,
        # urgency, phase, state, log: [...]}. Only id/room/state drive this
        # node (start or stop the bounded safety listen); the rest is context.
        state = _string(body, "state")
        if state not in {"active", "closed", "cancelled"}:
            raise ValueError("state must be active, closed, or cancelled")
        raw_data = body.get("data")
        return cls(
            session_id=_string(body, "id"),
            timestamp=_optional_timestamp(body),
            room=_string(body, "room"),
            skill=_optional_string(body, "skill"),
            urgency=_optional_string(body, "urgency"),
            phase=_optional_string(body, "phase"),
            state=state,
            event=_optional_string(body, "event"),
            data=raw_data if isinstance(raw_data, dict) else {},
        )


TTSCommand = SayCommand
