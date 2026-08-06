"""Ventuno-side validators for the frozen QNet MQTT contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


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


def _timestamp(data: dict[str, Any]) -> float:
    value = data.get("ts")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("ts must be a Unix timestamp number")
    return float(value)


@dataclass(frozen=True)
class SayCommand:
    message_id: str
    timestamp: float
    room: str
    text: str
    priority: str

    @classmethod
    def from_payload(cls, payload: bytes | str) -> "SayCommand":
        data = _decode(payload)
        priority = data.get("prio")
        if priority not in {"safety", "comfort"}:
            raise ValueError("prio must be safety or comfort")
        text = _string(data, "text")
        if len(text) > 1024:
            raise ValueError("text exceeds 1024 characters")
        return cls(
            message_id=_string(data, "id"),
            timestamp=_timestamp(data),
            room=_string(data, "room"),
            text=text,
            priority=priority,
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
        data = body.get("data")
        if not isinstance(data, dict):
            raise ValueError("data must be a JSON object")
        state = _string(body, "state")
        if state not in {"active", "closed", "cancelled"}:
            raise ValueError("state must be active, closed, or cancelled")
        return cls(
            session_id=_string(body, "id"),
            timestamp=_timestamp(body),
            room=_string(body, "room"),
            skill=_string(body, "skill"),
            urgency=_string(body, "urgency"),
            phase=_string(body, "phase"),
            state=state,
            event=_string(body, "event"),
            data=data,
        )


TTSCommand = SayCommand
