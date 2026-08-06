# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_house_template_has_rooms_and_voice_policy() -> None:
    house = (ROOT / "config" / "house.example.yaml").read_text(encoding="utf-8")
    for required in (
        "schema: qnet.house/1.0",
        "rooms:",
        "qos: 1",
        "vad_hangover_ms: 700",
        "post_tts_guard_ms: 500",
    ):
        assert required in house


def test_node_template_has_stable_identity_and_audio_owner_config() -> None:
    node = (ROOT / "config" / "node.example.yaml").read_text(encoding="utf-8")
    for required in (
        "schema: qnet.node/1.0",
        "node_id: ventuno-living-room",
        "room: living-room",
        "port: 1883",
        "asr_mode: sentence",
        "vad_hangover_ms: 700",
    ):
        assert required in node


def test_inventory_and_bedroom_voice_config_are_registered() -> None:
    inventory = (ROOT / "config" / "inventory.example.yaml").read_text(encoding="utf-8")
    bedroom = (
        ROOT / "config" / "voice-nodes" / "ventuno-bedroom.json"
    ).read_text(encoding="utf-8")
    for required in (
        "host: 10.73.51.175",
        "host: 10.73.51.123",
        "host: 10.73.51.178",
        "node_id: ventuno-bedroom",
    ):
        assert required in inventory
    for required in (
        '"device_id": "ventuno-bedroom"',
        '"room_id": "bedroom"',
        '"iq9_host": "10.73.51.175"',
    ):
        assert required in bedroom
