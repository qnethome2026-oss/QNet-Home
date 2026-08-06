from __future__ import annotations

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

import json
import sys
import time
from pathlib import Path

from agent.engine import AgentEngine


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_PYTHON = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python"
sys.path.insert(0, str(NODE_PYTHON))

from config import VoiceNodeConfig  # noqa: E402
from message_schema import SayCommand, SessionEvent  # noqa: E402
from speech_backend import ArduinoSpeechBackend  # noqa: E402
from voice_controller import VoiceController  # noqa: E402

from tests.fakes import FakeASR, FakeMQTTTransport, FakeTTS


def test_fake_fall_to_spoken_check_to_heard_reply(tmp_path) -> None:
    bus: list[tuple[str, dict]] = []

    def publish(topic: str, payload: dict, _qos: int, _retain: bool) -> None:
        bus.append((topic, payload))

    agent = AgentEngine(publish, tmp_path)
    agent.on_message(
        "qnet/living-room/event",
        {
            "id": "fall-fixture",
            "ts": time.time(),
            "room": "living-room",
            "kind": "fall.detected",
            "conf": 0.9,
            "meta": {"frames": "5/8"},
        },
    )

    class LoopbackTransport(FakeMQTTTransport):
        def publish_heard(self, *, text: str, silence: bool) -> str:
            message_id = super().publish_heard(text=text, silence=silence)
            agent.on_message(
                "qnet/living-room/heard",
                {
                    "id": message_id,
                    "ts": time.time(),
                    "room": "living-room",
                    "text": text,
                    "silence": silence,
                },
            )
            return message_id

    transport = LoopbackTransport()
    tts = FakeTTS()
    voice = VoiceController(
        speech=ArduinoSpeechBackend(FakeASR("I'm fine"), tts),
        transport=transport,
        config=VoiceNodeConfig(
            "ventuno-living-room", "living-room", (), "iq9", 1883, None, None, "usb:1", "usb:1", "en", 2, 1, 0, 20,
            "I am the first responder",
        ),
        sleep_fn=lambda _: None,
    )
    session_payload = next(payload for topic, payload in bus if topic.startswith("qnet/session/"))
    say_payload = next(payload for topic, payload in bus if topic == "qnet/living-room/say")
    voice.on_session_event(SessionEvent.from_payload(json.dumps(session_payload)))
    voice.on_tts_command(SayCommand.from_payload(json.dumps(say_payload)))
    voice.run_once()
    voice.run_once()

    assert tts.spoken == ["I saw you fall. Are you okay?"]
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert [record["event"] for record in records] == ["detected", "say", "heard"]
    assert records[-1]["data"]["text"] == "I'm fine"
