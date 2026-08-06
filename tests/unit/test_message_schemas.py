from __future__ import annotations

import time

import pytest

from services.iq9_voice_router.schemas import MessageValidationError, SayCommand, VoiceRequest


def test_voice_request_round_trip() -> None:
    original = VoiceRequest("req-10", time.time(), "bedroom", "query", "broadcast that hello")
    decoded = VoiceRequest.from_payload(original.to_dict())
    assert decoded == original
    assert set(original.to_dict()) == {"id", "ts", "room", "kind", "text"}


def test_say_command_round_trip() -> None:
    request = VoiceRequest("req-11", time.time(), "bedroom", "query", "broadcast that hello")
    command = SayCommand.create(request=request, room="kitchen", text="hello", priority="comfort")
    decoded = SayCommand.from_payload(command.to_json())
    assert decoded == command
    assert set(command.to_dict()) == {"id", "ts", "room", "text", "prio"}


def test_responder_brief_allows_empty_text() -> None:
    decoded = VoiceRequest.from_payload(
        {"id": "brief-1", "ts": time.time(), "room": "hall", "kind": "responder_brief", "text": ""}
    )
    assert decoded.text == ""
    with pytest.raises(MessageValidationError, match="must be empty"):
        VoiceRequest.from_payload(
            {"id": "brief-2", "ts": time.time(), "room": "hall", "kind": "responder_brief", "text": "brief me"}
        )


def test_rejects_old_schema_and_bad_priority() -> None:
    with pytest.raises(MessageValidationError):
        VoiceRequest.from_payload({"schema_version": 1})
    with pytest.raises(MessageValidationError, match="prio"):
        SayCommand.from_payload(
            {"id": "say-1", "ts": time.time(), "room": "hall", "text": "hello", "prio": "normal"}
        )
