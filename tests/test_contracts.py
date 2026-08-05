# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""T0.1 - the frozen wire contract, one test per fixture (DESIGN.md §4).

Eight fixtures, eight tests. If a payload shape changes, this file and
``contracts/mqtt.md`` change in the same commit, or it didn't happen.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"


def load(name: str) -> dict:
    """Read a fixture. Also asserts it is valid, ASCII-only JSON."""
    raw = Path(FIXTURES / name).read_bytes()
    assert raw.decode("ascii"), f"{name} must be ASCII-only"
    return json.loads(raw)


def test_event_fall() -> None:
    """qnet/<room>/event - a fall the node detected."""
    m = load("event_fall.json")
    assert set(m) == {"id", "ts", "room", "kind", "conf", "meta"}
    assert isinstance(m["id"], str) and m["id"]
    assert isinstance(m["ts"], float)
    assert isinstance(m["room"], str) and m["room"]
    assert m["kind"] == "fall.detected"
    assert isinstance(m["conf"], float) and 0.0 <= m["conf"] <= 1.0
    assert isinstance(m["meta"], dict)
    assert isinstance(m["meta"]["cls"], str) and m["meta"]["cls"]
    assert isinstance(m["meta"]["frames"], str) and "/" in m["meta"]["frames"]


def test_ask_query() -> None:
    """qnet/<room>/ask, kind=query - "hey home, where are my glasses"."""
    m = load("ask_query.json")
    assert set(m) == {"id", "ts", "room", "text", "kind"}
    assert isinstance(m["id"], str) and m["id"]
    assert isinstance(m["ts"], float)
    assert isinstance(m["room"], str) and m["room"]
    assert m["kind"] == "query"
    # A query carries the transcript with the wake phrase stripped.
    assert isinstance(m["text"], str) and m["text"]


def test_ask_responder_brief() -> None:
    """qnet/<room>/ask, kind=responder_brief - text is empty, the room is the request."""
    m = load("ask_responder_brief.json")
    assert set(m) == {"id", "ts", "room", "text", "kind"}
    assert isinstance(m["id"], str) and m["id"]
    assert isinstance(m["ts"], float)
    assert isinstance(m["room"], str) and m["room"]
    assert m["kind"] == "responder_brief"
    assert m["text"] == ""


def test_say() -> None:
    """qnet/<room>/say - speak this."""
    m = load("say.json")
    assert set(m) == {"text", "prio"}
    assert isinstance(m["text"], str) and m["text"]
    assert m["prio"] in {"safety", "comfort"}


def test_heard() -> None:
    """qnet/<room>/heard - what was said."""
    m = load("heard.json")
    assert set(m) == {"text", "silence"}
    assert isinstance(m["text"], str)
    assert isinstance(m["silence"], bool)
    # Silence carries no transcript; a transcript is not silence.
    assert m["silence"] is (m["text"] == "")


def test_look() -> None:
    """qnet/look - broadcast: look for X right now."""
    m = load("look.json")
    assert set(m) == {"qid", "object", "mode", "room"}
    assert isinstance(m["qid"], str) and m["qid"]
    assert isinstance(m["object"], str) and m["object"]
    assert m["mode"] in {"find", "guide"}
    # null broadcasts to every node; guide mode targets one room.
    assert m["room"] is None or isinstance(m["room"], str)


def test_looked() -> None:
    """qnet/<room>/looked - what that node's VLM saw. Text only, never the frame."""
    m = load("looked.json")
    assert set(m) == {"qid", "room", "found", "answer"}
    assert isinstance(m["qid"], str) and m["qid"]
    assert isinstance(m["room"], str) and m["room"]
    assert isinstance(m["found"], bool)
    assert isinstance(m["answer"], str)
    if m["found"]:
        # Found means a usable location phrase, not just a yes.
        assert m["answer"]


def test_session() -> None:
    """qnet/session/<id> - one skill run, trigger to exit, plus its log lines (§6)."""
    m = load("session.json")
    assert set(m) == {"id", "room", "skill", "urgency", "phase", "state", "log"}
    assert isinstance(m["id"], str) and m["id"]
    assert isinstance(m["room"], str) and m["room"]
    assert isinstance(m["skill"], str) and m["skill"]
    assert m["urgency"] in {"safety", "routine"}
    assert isinstance(m["phase"], str) and m["phase"]
    assert m["state"] in {"active", "closed", "cancelled"}
    assert isinstance(m["log"], list) and m["log"]

    required = {
        "detected": {"kind", "conf"},
        "say": {"text"},
        "heard": {"text", "silence"},
        "phase": {"from", "to"},
        "tool": {"tool", "result"},
        "refusal": {"tool", "phase"},
    }
    for line in m["log"]:
        assert isinstance(line["ts"], float)
        assert line["event"] in required, f"unknown log event {line['event']!r}"
        assert required[line["event"]] <= set(line)
    # The log is a timeline: appended as things happen, so it is ordered.
    stamps = [line["ts"] for line in m["log"]]
    assert stamps == sorted(stamps)
    assert {line["event"] for line in m["log"]} == set(required)
