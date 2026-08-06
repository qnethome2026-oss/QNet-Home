# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""B3c: status is our heartbeat pattern, not a retained LWT.

`qnet/<room>/status` follows what `qnet/node/vision.py` settled in T4.2:
periodic, non-retained, QoS 0, `{node, room, ts, state}`. A dead node stops
beating; the dashboard's 15 s staleness rule does the rest. No retained
payloads means no "Camera online" corpse after the node is gone.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

from config import VoiceNodeConfig
from mqtt_transport import MQTTTransport


class RecordingClient:
    """Captures paho publish calls; network never opens in these tests."""

    def __init__(self):
        self.published: list[tuple[str, dict, int, bool]] = []

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))
        return SimpleNamespace(rc=0)  # mqtt.MQTT_ERR_SUCCESS


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


def transport(**overrides) -> tuple[MQTTTransport, RecordingClient]:
    t = MQTTTransport(config(**overrides))
    client = RecordingClient()
    t.client = client
    return t, client


def test_status_is_heartbeat_shaped_qos0_and_never_retained() -> None:
    t, client = transport()
    t.publish_voice_status("listening")
    [(topic, payload, qos, retain)] = client.published
    assert topic == "qnet/kitchen/status"
    assert qos == 0
    assert retain is False
    assert payload["node"] == "kitchen-voice-01"  # `node`, not her `node_id`
    assert "node_id" not in payload
    assert payload["room"] == "kitchen"
    assert isinstance(payload["ts"], float)
    assert payload["state"] == "listening"


def test_non_wire_states_normalize_to_idle() -> None:
    t, client = transport()
    t.publish_voice_status("starting")
    assert client.published[-1][1]["state"] == "idle"


def test_no_last_will_is_registered() -> None:
    # The LWT + retained offline pattern is gone: liveness is proven by
    # heartbeat arrival, offline by 15 s of silence.
    t = MQTTTransport(config())
    assert t.client._will is False


def test_error_and_say_id_extras_survive() -> None:
    t, client = transport()
    t.publish_voice_status("error", error="ASR: runner down", say_id="say-1")
    payload = client.published[-1][1]
    assert payload["state"] == "error"
    assert payload["error"] == "ASR: runner down"
    assert payload["say_id"] == "say-1"


def test_heartbeat_thread_beats_periodically_with_provider_state() -> None:
    t, client = transport(heartbeat_interval_seconds=0.02)
    t.set_state_provider(lambda: "listening")
    t.start_heartbeat()
    try:
        deadline = time.monotonic() + 2.0
        while len(client.published) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        t.stop_heartbeat()
    assert len(client.published) >= 3
    for _topic, payload, qos, retain in client.published:
        assert payload["state"] == "listening"
        assert qos == 0
        assert retain is False


def test_heartbeat_defaults_to_idle_and_survives_provider_failure() -> None:
    t, client = transport()
    t.publish_heartbeat()  # no provider wired yet
    assert client.published[-1][1]["state"] == "idle"

    def broken() -> str:
        raise RuntimeError("controller lock poisoned")

    t.set_state_provider(broken)
    t.publish_heartbeat()
    assert client.published[-1][1]["state"] == "error"
