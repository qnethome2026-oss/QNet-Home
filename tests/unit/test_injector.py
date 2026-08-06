from __future__ import annotations

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

import argparse

from dev.inject import build_message


def test_fall_injector_preserves_event_fixture_shape() -> None:
    topic, payload = build_message(argparse.Namespace(command="fall", room="kitchen"))
    assert topic == "qnet/kitchen/event"
    assert set(payload) == {"id", "ts", "room", "kind", "conf", "meta"}
    assert payload["kind"] == "fall.detected"


def test_both_ask_kinds_preserve_fixture_shapes() -> None:
    topic, query = build_message(
        argparse.Namespace(command="query", room="bedroom", text="where are my glasses")
    )
    assert topic == "qnet/bedroom/ask"
    assert query["kind"] == "query"
    assert query["text"] == "where are my glasses"
    _topic, brief = build_message(
        argparse.Namespace(command="responder_brief", room="bedroom", text="")
    )
    assert brief["kind"] == "responder_brief"
    assert brief["text"] == ""
