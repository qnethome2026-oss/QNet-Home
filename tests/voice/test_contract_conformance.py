# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""B2: the voice node speaks OUR frozen contract, in both directions.

Inbound: the node's parsers must accept the verbatim frozen fixtures
(`contracts/fixtures/*.json` - the same bytes `dev/inject.py` and
`tests/test_contracts.py` treat as the wire truth) plus the engine's actual
runtime shapes. Outbound: the node's ask/heard builders must produce payloads
satisfying the same field expectations `tests/test_contracts.py` asserts.
The review found the extracted branch rejected everything our engine sends
(strict `id/ts/room`, unknown `prio`, oversize text) - these tests pin the
relaxations so they cannot regress.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from config import VoiceNodeConfig
from message_schema import MAX_SAY_TEXT_CHARS, SayCommand, SessionEvent
from mqtt_transport import MQTTTransport
from voice_controller import LOWEST_PRIORITY, PRIORITY

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / f"{name}.json").read_bytes()


def config(**overrides) -> VoiceNodeConfig:
    settings = dict(
        device_id="kitchen-voice-01",
        room_id="kitchen",
        groups=(),
        mqtt_host="iq9",
        mqtt_port=11883,
        mqtt_username=None,
        mqtt_password=None,
        microphone_device="usb:1",
        speaker_device="usb:1",
        language="en",
        idle_listen_timeout_seconds=30,
        session_listen_timeout_seconds=15,
        post_tts_guard_ms=500,
        tts_queue_size=20,
        responder_phrase="I am the first responder",
    )
    settings.update(overrides)
    return VoiceNodeConfig(**settings)


class RecordingClient:
    def __init__(self):
        self.published: list[tuple[str, dict, int, bool]] = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))
        return SimpleNamespace(rc=0)


def transport() -> tuple[MQTTTransport, RecordingClient]:
    t = MQTTTransport(config())
    client = RecordingClient()
    t.client = client
    return t, client


# --- (a) inbound: the verbatim frozen fixtures ----------------------------


def test_frozen_say_fixture_parses_verbatim() -> None:
    command = SayCommand.from_payload(fixture_bytes("say"))
    assert command.text == "I saw you fall. Are you okay?"
    assert command.priority == "safety"
    # id/ts/room are absent on our wire: a local id is synthesized so the
    # node's dedupe machinery still has something to key on.
    assert command.message_id
    assert command.room is None
    assert isinstance(command.timestamp, float)


def test_frozen_session_fixture_parses_verbatim() -> None:
    event = SessionEvent.from_payload(fixture_bytes("session"))
    assert event.session_id == "01JQ7ZK9NB6WX2TFDA5MEHC38V"
    assert event.room == "kitchen"
    assert event.state == "active"
    assert event.skill == "fall-response"
    assert event.urgency == "safety"
    assert event.phase == "escalate"


# --- (b) inbound: engine-realistic runtime payloads -----------------------


def test_engine_bare_say_shapes_are_accepted() -> None:
    routine = SayCommand.from_payload(json.dumps(
        {"text": "It's a lovely afternoon, Margaret.", "prio": "routine"}
    ))
    assert routine.priority == "routine"
    comfort = SayCommand.from_payload(json.dumps(
        {"text": "Sarah said she is on her way.", "prio": "comfort"}
    ))
    assert comfort.priority == "comfort"
    # Two identical bare says still get distinct local ids: per-message
    # dedupe works without ever deduping distinct engine messages.
    again = SayCommand.from_payload(json.dumps(
        {"text": "It's a lovely afternoon, Margaret.", "prio": "routine"}
    ))
    assert again.message_id != routine.message_id


def test_unknown_priority_is_accepted_and_maps_to_lowest() -> None:
    command = SayCommand.from_payload(json.dumps({"text": "hello", "prio": "urgent-ish"}))
    assert command.priority == "urgent-ish"
    assert PRIORITY.get(command.priority, LOWEST_PRIORITY) == LOWEST_PRIORITY
    assert PRIORITY["routine"] == LOWEST_PRIORITY  # routine is explicitly lowest


def test_oversize_say_text_is_truncated_never_rejected() -> None:
    long_text = "all work and no play " * 100  # > 1024 chars
    command = SayCommand.from_payload(json.dumps({"text": long_text, "prio": "safety"}))
    assert len(command.text) == MAX_SAY_TEXT_CHARS
    assert command.text == long_text.strip()[:MAX_SAY_TEXT_CHARS]


def test_say_still_requires_text_and_prio() -> None:
    with pytest.raises(ValueError):
        SayCommand.from_payload(json.dumps({"prio": "safety"}))
    with pytest.raises(ValueError):
        SayCommand.from_payload(json.dumps({"text": "hello"}))


def test_minimal_and_closed_session_snapshots_are_accepted() -> None:
    minimal = SessionEvent.from_payload(json.dumps(
        {"id": "01SESSION", "room": "kitchen", "state": "active"}
    ))
    assert (minimal.session_id, minimal.room, minimal.state) == ("01SESSION", "kitchen", "active")

    closed = json.loads(fixture_bytes("session"))
    closed["state"] = "closed"
    closed["log"].append({"ts": closed["log"][-1]["ts"] + 1, "event": "phase",
                          "from": "escalate", "to": "resolved"})
    event = SessionEvent.from_payload(json.dumps(closed))
    assert event.state == "closed"


def test_say_room_crosscheck_only_when_room_present() -> None:
    t, _client = transport()
    received: list[SayCommand] = []
    t.set_say_handler(received.append)

    def deliver(payload: dict) -> None:
        t._on_message(None, None, SimpleNamespace(
            topic="qnet/kitchen/say", payload=json.dumps(payload).encode()
        ))

    deliver({"text": "no room field", "prio": "safety"})
    assert len(received) == 1  # roomless say accepted (our engine's shape)
    deliver({"text": "wrong room", "prio": "safety", "room": "bedroom"})
    assert len(received) == 1  # mismatched room still rejected
    deliver({"text": "right room", "prio": "safety", "room": "kitchen"})
    assert len(received) == 2


# --- (c) outbound: the node's publishes vs test_contracts expectations ----


def test_published_ask_query_satisfies_frozen_contract() -> None:
    t, client = transport()
    message_id = t.publish_query("where are my glasses")
    [(topic, m, qos, retain)] = client.published
    assert topic == "qnet/kitchen/ask"
    assert qos == 1 and retain is False
    # The exact assertions test_contracts.test_ask_query makes of the fixture:
    assert set(m) == {"id", "ts", "room", "text", "kind"}
    assert isinstance(m["id"], str) and m["id"] and m["id"] == message_id
    assert isinstance(m["ts"], float)
    assert isinstance(m["room"], str) and m["room"]
    assert m["kind"] == "query"
    assert isinstance(m["text"], str) and m["text"]


def test_published_responder_brief_satisfies_frozen_contract() -> None:
    t, client = transport()
    t.publish_responder_brief()
    [(_topic, m, _qos, _retain)] = client.published
    # The exact assertions test_contracts.test_ask_responder_brief makes:
    assert set(m) == {"id", "ts", "room", "text", "kind"}
    assert isinstance(m["id"], str) and m["id"]
    assert isinstance(m["ts"], float)
    assert isinstance(m["room"], str) and m["room"]
    assert m["kind"] == "responder_brief"
    assert m["text"] == ""


@pytest.mark.parametrize("text,silence", [("i'm fine", False), ("", True)])
def test_published_heard_satisfies_frozen_contract(text: str, silence: bool) -> None:
    t, client = transport()
    t.publish_heard(text=text, silence=silence)
    [(topic, m, qos, _retain)] = client.published
    assert topic == "qnet/kitchen/heard"
    assert qos == 1
    # The exact assertions test_contracts.test_heard makes of the fixture:
    assert set(m) == {"text", "silence"}
    assert isinstance(m["text"], str)
    assert isinstance(m["silence"], bool)
    assert m["silence"] is (m["text"] == "")


def test_heard_text_and_silence_must_agree() -> None:
    t, _client = transport()
    with pytest.raises(ValueError):
        t.publish_heard(text="i'm fine", silence=True)
    with pytest.raises(ValueError):
        t.publish_heard(text="", silence=False)
