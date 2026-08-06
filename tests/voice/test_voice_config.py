# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.

from __future__ import annotations

import json

from config import VoiceNodeConfig


def test_asr_model_can_be_selected_from_node_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qnet-config.json"
    config_path.write_text(json.dumps({"asr_model": "whisper-small"}), encoding="utf-8")
    monkeypatch.setenv("QNET_CONFIG_PATH", str(config_path))

    assert VoiceNodeConfig.from_env().asr_model == "whisper-small"


def test_asr_model_defaults_to_unquantized_small(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qnet-config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("QNET_CONFIG_PATH", str(config_path))

    assert VoiceNodeConfig.from_env().asr_model == "whisper-small"


def test_asr_model_environment_override_wins(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qnet-config.json"
    config_path.write_text(json.dumps({"asr_model": "whisper-small"}), encoding="utf-8")
    monkeypatch.setenv("QNET_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("QNET_ASR_MODEL", "whisper-medium")

    assert VoiceNodeConfig.from_env().asr_model == "whisper-medium"
