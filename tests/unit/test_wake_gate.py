from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WAKE_GATE_PATH = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python/wake_gate.py"
SPEC = importlib.util.spec_from_file_location("qhome_wake_gate", WAKE_GATE_PATH)
assert SPEC and SPEC.loader
WAKE_GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WAKE_GATE)


def test_extracts_supported_wake_phrases() -> None:
    assert WAKE_GATE.extract_wake_request("Hey QHome, broadcast that dinner is ready") == "broadcast that dinner is ready"
    assert WAKE_GATE.extract_wake_request("hey q home announce in the bedroom that hello") == "announce in the bedroom that hello"
    assert WAKE_GATE.extract_wake_request("Hey Home: how are you?") == "how are you?"
    assert WAKE_GATE.extract_wake_request("He home. Broadcast the TOWER YOU") == "Broadcast the TOWER YOU"


def test_rejects_non_wake_speech_and_empty_commands() -> None:
    assert WAKE_GATE.extract_wake_request("broadcast that dinner is ready") is None
    assert WAKE_GATE.extract_wake_request("The television said hey QHome") is None
    assert WAKE_GATE.extract_wake_request("Hey QHome") is None
