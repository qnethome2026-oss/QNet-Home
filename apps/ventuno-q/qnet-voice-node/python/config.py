# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Environment configuration for one Ventuno Q voice node."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceNodeConfig:
    device_id: str
    room_id: str
    groups: tuple[str, ...]
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    microphone_device: str
    speaker_device: str
    language: str
    idle_listen_timeout_seconds: int
    session_listen_timeout_seconds: int
    post_tts_guard_ms: int
    tts_queue_size: int
    responder_phrase: str
    asr_model: str = "whisper-small"
    transcript_window_seconds: int = 10
    # B1: the node-side activation gate. The matcher tolerates ASR variants
    # ("he home", "hey q home") for whatever phrase is configured here.
    wake_phrase: str = "hey home"
    # B3c: our heartbeat cadence (contracts/mqtt.md status section) - periodic,
    # non-retained, QoS 0; the dashboard's 15 s staleness rule detects offline.
    heartbeat_interval_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "VoiceNodeConfig":
        config_path = Path(os.getenv("QNET_CONFIG_PATH", "/app/qnet-config.json"))
        file_config = {}
        if config_path.exists():
            file_config = json.loads(config_path.read_text(encoding="utf-8"))

        def setting(env_name: str, file_name: str, default):
            return os.getenv(env_name, file_config.get(file_name, default))

        device_id = str(setting("QNET_DEVICE_ID", "device_id", "ventuno-01")).strip()
        room_id = str(setting("QNET_ROOM_ID", "room_id", "unassigned")).strip()
        raw_groups = setting("QNET_GROUPS", "groups", [])
        if isinstance(raw_groups, str):
            raw_groups = raw_groups.split(",")
        groups = tuple(
            group.strip()
            for group in raw_groups
            if group.strip()
        )
        if not device_id:
            raise ValueError("QNET_DEVICE_ID cannot be empty")
        if not room_id:
            raise ValueError("QNET_ROOM_ID cannot be empty")
        result = cls(
            device_id=device_id,
            room_id=room_id,
            groups=groups,
            mqtt_host=str(setting("QNET_IQ9_HOST", "iq9_host", "127.0.0.1")),
            mqtt_port=int(setting("QNET_MQTT_PORT", "mqtt_port", 1883)),
            mqtt_username=setting("QNET_MQTT_USERNAME", "mqtt_username", None) or None,
            mqtt_password=setting("QNET_MQTT_PASSWORD", "mqtt_password", None) or None,
            microphone_device=str(
                setting("QNET_MICROPHONE_DEVICE", "microphone_device", "usb:1")
            ),
            speaker_device=str(setting("QNET_SPEAKER_DEVICE", "speaker_device", "usb:1")),
            language=str(setting("QNET_LANGUAGE", "language", "en")),
            idle_listen_timeout_seconds=int(
                setting("QNET_IDLE_LISTEN_TIMEOUT", "idle_listen_timeout_seconds", 30)
            ),
            session_listen_timeout_seconds=int(
                setting("QNET_SESSION_LISTEN_TIMEOUT", "session_listen_timeout_seconds", 15)
            ),
            post_tts_guard_ms=int(setting("QNET_POST_TTS_GUARD_MS", "post_tts_guard_ms", 500)),
            tts_queue_size=int(setting("QNET_TTS_QUEUE_SIZE", "tts_queue_size", 20)),
            responder_phrase=str(
                setting("QNET_RESPONDER_PHRASE", "responder_phrase", "I am the first responder")
            ).strip(),
            asr_model=str(
                setting("QNET_ASR_MODEL", "asr_model", "whisper-small")
            ).strip(),
            transcript_window_seconds=int(
                setting("QNET_TRANSCRIPT_WINDOW_SECONDS", "transcript_window_seconds", 10)
            ),
            wake_phrase=str(
                setting("QNET_WAKE_PHRASE", "wake_phrase", "hey home")
            ).strip(),
            heartbeat_interval_seconds=float(
                setting("QNET_HEARTBEAT_INTERVAL", "heartbeat_interval_seconds", 5.0)
            ),
        )
        if result.idle_listen_timeout_seconds <= 0 or result.session_listen_timeout_seconds <= 0:
            raise ValueError("listen timeouts must be positive")
        if result.post_tts_guard_ms < 0:
            raise ValueError("post_tts_guard_ms cannot be negative")
        if result.tts_queue_size <= 0:
            raise ValueError("tts_queue_size must be positive")
        if not result.responder_phrase:
            raise ValueError("responder_phrase cannot be empty")
        if not result.asr_model:
            raise ValueError("asr_model cannot be empty")
        if result.transcript_window_seconds <= 0:
            raise ValueError("transcript_window_seconds must be positive")
        if not result.wake_phrase:
            raise ValueError("wake_phrase cannot be empty")
        if result.heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        return result
