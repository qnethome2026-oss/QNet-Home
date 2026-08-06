# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
REQUIRED = {
    "event.json": {"id", "ts", "room", "kind", "conf", "meta"},
    "ask-query.json": {"id", "ts", "room", "kind", "text"},
    "ask-responder-brief.json": {"id", "ts", "room", "kind", "text"},
    "say.json": {"id", "ts", "room", "text", "prio"},
    "heard.json": {"id", "ts", "room", "text", "silence"},
    "look.json": {"qid", "ts", "object", "mode", "room"},
    "looked.json": {"qid", "ts", "room", "found", "answer"},
    "session.json": {"id", "ts", "room", "skill", "urgency", "phase", "state", "event", "data"},
}


@pytest.mark.parametrize(("name", "required"), REQUIRED.items())
def test_fixture_has_required_fields_and_types(name: str, required: set[str]) -> None:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict) and required <= payload.keys()
    assert isinstance(payload["ts"], (int, float)) and payload["ts"] > 0
    for key in required - {"ts", "conf", "meta", "data", "silence", "found", "room"}:
        assert isinstance(payload[key], str)
    if "room" in required and payload["room"] is not None:
        assert isinstance(payload["room"], str) and payload["room"]


def test_fixture_union_rules() -> None:
    payloads = {name: json.loads((FIXTURES / name).read_text()) for name in REQUIRED}
    assert payloads["event.json"]["kind"] == "fall.detected"
    assert 0 <= payloads["event.json"]["conf"] <= 1
    assert payloads["ask-query.json"]["kind"] == "query" and payloads["ask-query.json"]["text"]
    assert "hey home" in payloads["ask-query.json"]["text"].lower()
    assert payloads["ask-responder-brief.json"]["kind"] == "responder_brief"
    assert payloads["ask-responder-brief.json"]["text"] == ""
    assert payloads["say.json"]["prio"] in {"safety", "comfort"}
    assert payloads["heard.json"]["silence"] is (payloads["heard.json"]["text"] == "")
    assert payloads["look.json"]["mode"] in {"find", "guide"}
    assert isinstance(payloads["looked.json"]["found"], bool)
    assert payloads["session.json"]["urgency"] in {"safety", "routine"}
    assert payloads["session.json"]["state"] in {"active", "closed", "cancelled"}


def test_contract_lists_every_frozen_topic() -> None:
    contract = (ROOT / "contracts" / "mqtt.md").read_text(encoding="utf-8")
    for topic in ("event", "ask", "say", "heard", "looked", "status"):
        assert f"qnet/<room>/{topic}" in contract
    assert "qnet/look" in contract
    assert "qnet/session/<id>" in contract
