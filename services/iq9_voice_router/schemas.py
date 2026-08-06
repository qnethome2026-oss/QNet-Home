"""Frozen Phase-0 MQTT message contracts used by the IQ9 voice router."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal


MAX_TEXT_LENGTH = 1024
AskKind = Literal["query", "responder_brief"]
Priority = Literal["safety", "comfort"]


class MessageValidationError(ValueError):
    """Raised when an MQTT payload does not satisfy contracts/mqtt.md."""


def _decode_payload(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    try:
        decoded = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MessageValidationError("payload must be valid JSON") from exc
    if not isinstance(decoded, dict):
        raise MessageValidationError("payload must be a JSON object")
    return decoded


def _required_string(
    data: dict[str, Any], key: str, *, allow_empty: bool = False, max_length: int = 256
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        suffix = "a string" if allow_empty else "a non-empty string"
        raise MessageValidationError(f"{key} must be {suffix}")
    value = value.strip()
    if len(value) > max_length:
        raise MessageValidationError(f"{key} exceeds {max_length} characters")
    return value


def _timestamp(data: dict[str, Any]) -> float:
    value = data.get("ts")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MessageValidationError("ts must be a Unix timestamp number")
    return float(value)


@dataclass(frozen=True)
class VoiceRequest:
    message_id: str
    timestamp: float
    room: str
    kind: AskKind
    text: str

    @classmethod
    def from_payload(cls, payload: bytes | str | dict[str, Any]) -> "VoiceRequest":
        data = _decode_payload(payload)
        kind = data.get("kind")
        if kind not in {"query", "responder_brief"}:
            raise MessageValidationError("kind must be query or responder_brief")
        text = _required_string(
            data, "text", allow_empty=kind == "responder_brief", max_length=MAX_TEXT_LENGTH
        )
        if kind == "responder_brief" and text != "":
            raise MessageValidationError("responder_brief text must be empty")
        return cls(
            message_id=_required_string(data, "id"),
            timestamp=_timestamp(data),
            room=_required_string(data, "room"),
            kind=kind,
            text=text,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.message_id,
            "ts": self.timestamp,
            "room": self.room,
            "kind": self.kind,
            "text": self.text,
        }


@dataclass(frozen=True)
class SayCommand:
    message_id: str
    timestamp: float
    room: str
    text: str
    priority: Priority = "comfort"

    @classmethod
    def create(
        cls,
        *,
        request: VoiceRequest,
        room: str,
        text: str,
        priority: Priority = "comfort",
    ) -> "SayCommand":
        text = text.strip()
        if not text:
            raise MessageValidationError("text must be a non-empty string")
        if priority not in {"safety", "comfort"}:
            raise MessageValidationError("prio must be safety or comfort")
        room = room.strip()
        if not room:
            raise MessageValidationError("room must be a non-empty string")
        return cls(request.message_id, time.time(), room, text, priority)

    @classmethod
    def from_payload(cls, payload: bytes | str | dict[str, Any]) -> "SayCommand":
        data = _decode_payload(payload)
        priority = data.get("prio")
        if priority not in {"safety", "comfort"}:
            raise MessageValidationError("prio must be safety or comfort")
        return cls(
            message_id=_required_string(data, "id"),
            timestamp=_timestamp(data),
            room=_required_string(data, "room"),
            text=_required_string(data, "text", max_length=MAX_TEXT_LENGTH),
            priority=priority,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.message_id,
            "ts": self.timestamp,
            "room": self.room,
            "text": self.text,
            "prio": self.priority,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


# Compatibility name for old internal imports. The wire format is the frozen Say payload.
TTSCommand = SayCommand
