from __future__ import annotations

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

import json
import time

from agent.engine import AgentEngine, OPENING


class Publisher:
    def __init__(self):
        self.messages: list[tuple[str, dict, int, bool]] = []

    def __call__(self, topic: str, payload: dict, qos: int, retain: bool) -> None:
        self.messages.append((topic, payload, qos, retain))


def fall(room: str = "living-room") -> dict:
    return {
        "id": "event-1",
        "ts": time.time(),
        "room": room,
        "kind": "fall.detected",
        "conf": 0.91,
        "meta": {"frames": "5/8"},
    }


def test_fall_opens_one_safety_session_speaks_and_logs(tmp_path) -> None:
    publisher = Publisher()
    engine = AgentEngine(publisher, tmp_path)
    session_id = engine.on_message("qnet/living-room/event", fall())
    assert session_id and session_id.startswith("fall-")
    assert [topic for topic, *_ in publisher.messages] == [
        f"qnet/session/{session_id}",
        "qnet/living-room/say",
        f"qnet/session/{session_id}",
    ]
    say = publisher.messages[1][1]
    assert say["text"] == OPENING
    assert say["prio"] == "safety"
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert [record["event"] for record in records] == ["detected", "say"]


def test_duplicate_fall_and_query_are_blocked_but_responder_is_exempt(tmp_path) -> None:
    engine = AgentEngine(Publisher(), tmp_path)
    engine.on_message("qnet/living-room/event", fall())
    assert engine.on_message("qnet/living-room/event", fall()) == "ignored-active-session"
    assert engine.on_message(
        "qnet/living-room/ask",
        {"id": "ask-1", "ts": time.time(), "room": "living-room", "kind": "query", "text": "hello"},
    ) == "ignored-safety-session"
    assert engine.on_message(
        "qnet/living-room/ask",
        {"id": "ask-2", "ts": time.time(), "room": "living-room", "kind": "responder_brief", "text": ""},
    ) == "responder-brief-exempt"


def test_heard_is_written_to_the_live_session_file(tmp_path) -> None:
    engine = AgentEngine(Publisher(), tmp_path)
    session_id = engine.on_message("qnet/living-room/event", fall())
    assert engine.on_message(
        "qnet/living-room/heard",
        {"id": "heard-1", "ts": time.time(), "room": "living-room", "text": "I'm fine", "silence": False},
    ) == session_id
    records = [json.loads(line) for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert records[-1]["event"] == "heard"
    assert records[-1]["data"] == {"text": "I'm fine", "silence": False}
