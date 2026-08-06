from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

from services.iq9_voice_router.device_registry import DeviceRegistry
from services.iq9_voice_router.router import VoiceRouter
from services.iq9_voice_router.schemas import VoiceRequest


REPO_ROOT = Path(__file__).resolve().parents[2]
VENTUNO_SCHEMA_PATH = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python/message_schema.py"
SPEC = importlib.util.spec_from_file_location("ventuno_message_schema", VENTUNO_SCHEMA_PATH)
assert SPEC and SPEC.loader
VENTUNO_SCHEMA = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VENTUNO_SCHEMA
SPEC.loader.exec_module(VENTUNO_SCHEMA)


def test_iq9_say_is_accepted_by_ventuno_contract() -> None:
    registry = DeviceRegistry(
        devices={"ventuno-bedroom": {"room": "bedroom", "aliases": ["bedroom"], "groups": []}}
    )
    result = VoiceRouter(registry).route(
        VoiceRequest(
            "contract-1",
            time.time(),
            "bedroom",
            "query",
            "announce in the bedroom that QHome is connected",
        )
    )
    publication = result.publications[0]
    command = VENTUNO_SCHEMA.SayCommand.from_payload(publication.command.to_json())
    assert publication.topic == "qnet/bedroom/say"
    assert command.message_id == "contract-1"
    assert command.room == "bedroom"
    assert command.text == "QHome is connected"
    assert command.priority == "comfort"
