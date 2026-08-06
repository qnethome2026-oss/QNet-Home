from __future__ import annotations

import time

import pytest

from services.iq9_voice_router.device_registry import DeviceRegistry
from services.iq9_voice_router.message_store import MessageStore
from services.iq9_voice_router.router import RouteError, VoiceRouter
from services.iq9_voice_router.schemas import VoiceRequest


def request(text: str, message_id: str = "req-1", kind: str = "query") -> VoiceRequest:
    return VoiceRequest(message_id, time.time(), "living-room", kind, text)


@pytest.fixture
def router() -> VoiceRouter:
    registry = DeviceRegistry(
        devices={
            "ventuno-living-room": {
                "room": "living-room",
                "aliases": ["living room"],
                "groups": ["downstairs"],
            },
            "ventuno-bedroom": {
                "room": "bedroom",
                "aliases": ["bedroom"],
                "groups": ["upstairs"],
            },
            "ventuno-kitchen": {
                "room": "kitchen",
                "aliases": ["kitchen"],
                "groups": ["downstairs"],
            },
        }
    )
    return VoiceRouter(registry, MessageStore())


def test_routes_broadcast_as_one_room_correct_payload_per_topic(router: VoiceRouter) -> None:
    result = router.route(request("broadcast that dinner is ready"))
    assert result.topics == (
        "qnet/bedroom/say",
        "qnet/kitchen/say",
        "qnet/living-room/say",
    )
    for publication in result.publications:
        assert publication.command.room == publication.topic.split("/")[1]
        assert publication.command.text == "dinner is ready"
        assert publication.command.priority == "comfort"


def test_routes_to_named_device(router: VoiceRouter) -> None:
    result = router.route(request("announce on the bedroom device that dinner is ready"))
    assert result.topics == ("qnet/bedroom/say",)
    assert result.publications[0].command.room == "bedroom"


def test_routes_to_group(router: VoiceRouter) -> None:
    result = router.route(request("broadcast to upstairs that lights are off"))
    assert result.topics == ("qnet/bedroom/say",)


def test_replays_last_announcement_on_selected_device(router: VoiceRouter) -> None:
    router.route(request("broadcast that dinner is ready", "req-original"))
    replay = router.route(request("play the last broadcast on the kitchen device", "req-replay"))
    assert replay.replay is True
    assert replay.topics == ("qnet/kitchen/say",)
    assert replay.publications[0].command.text == "dinner is ready"
    assert replay.publications[0].command.message_id == "req-replay"


def test_rejects_unknown_target_non_announcement_and_responder(router: VoiceRouter) -> None:
    with pytest.raises(RouteError, match="unknown target"):
        router.route(request("announce in the garage that hello"))
    with pytest.raises(RouteError, match="not a broadcast"):
        router.route(request("how are you"))
    with pytest.raises(RouteError, match="Phase-2"):
        router.route(request("", kind="responder_brief"))
