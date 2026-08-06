from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_PYTHON = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python"
sys.path.insert(0, str(NODE_PYTHON))

from config import VoiceNodeConfig  # noqa: E402


def test_asr_model_can_be_selected_from_node_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qhome-config.json"
    config_path.write_text(json.dumps({"asr_model": "whisper-small"}), encoding="utf-8")
    monkeypatch.setenv("QHOME_CONFIG_PATH", str(config_path))

    assert VoiceNodeConfig.from_env().asr_model == "whisper-small"


def test_asr_model_defaults_to_unquantized_small(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qhome-config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("QHOME_CONFIG_PATH", str(config_path))

    assert VoiceNodeConfig.from_env().asr_model == "whisper-small"


def test_asr_model_environment_override_wins(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "qhome-config.json"
    config_path.write_text(json.dumps({"asr_model": "whisper-small"}), encoding="utf-8")
    monkeypatch.setenv("QHOME_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("QHOME_ASR_MODEL", "whisper-medium")

    assert VoiceNodeConfig.from_env().asr_model == "whisper-medium"
