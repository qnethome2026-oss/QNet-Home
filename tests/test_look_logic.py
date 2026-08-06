# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The look node's pure logic - prompt, parse, trim, routing - off-device (T6.3).

No camera, no VLM, no broker: what is asserted here is the exact prompt the
board sends, the exact parser its replies go through (including the garbage
cases the contract says must degrade to found=false, never crash), the qid
echo discipline, and the shm-vs-camera frame decision. The raw VLM strings are
real shapes observed from qwen3_vl_4b_instruct on the Ventuno Q container.
"""

from __future__ import annotations

import json
from pathlib import Path

from qnet.node.look import (
    FRESH_S,
    answer_look,
    build_looked,
    build_prompt,
    choose_frame,
    one_sentence,
    parse_reply,
    should_answer,
)

FIXTURES = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"


# --- prompt build -----------------------------------------------------------


def test_prompt_find_names_object_and_demands_json():
    p = build_prompt("glasses", "find")
    assert "glasses" in p
    assert "JSON only" in p
    assert '"found"' in p and '"answer"' in p
    # find asks for a location phrase relative to a nearby anchor, not guidance
    assert "relative to something obvious nearby" in p


def test_prompt_guide_asks_for_positional_guidance():
    p = build_prompt("glasses", "guide")
    assert "glasses" in p and "JSON only" in p
    assert "guiding them" in p and "landmarks" in p
    assert p != build_prompt("glasses", "find")


def test_prompt_unknown_mode_falls_back_to_find():
    # The contract only knows find|guide; anything else must still produce a
    # valid find prompt rather than a crash on a malformed broadcast.
    assert build_prompt("keys", "banana") == build_prompt("keys", "find")


# --- reply parsing - the exact strings a small VLM actually emits -----------


def test_parse_clean_json():
    assert parse_reply('{"found": true, "answer": "on the counter next to the kettle"}') == (
        True,
        "on the counter next to the kettle",
    )


def test_parse_fenced_json_with_prose():
    raw = 'Sure! Here is the JSON:\n```json\n{"found": false, "answer": ""}\n```'
    assert parse_reply(raw) == (False, "")


def test_parse_string_booleans():
    # Observed small-model behaviour: "true" as a string, not a bool.
    assert parse_reply('{"found": "true", "answer": "by the sink"}') == (True, "by the sink")
    assert parse_reply('{"found": "false", "answer": ""}') == (False, "")


def test_parse_garbage_returns_none():
    for raw in (None, "", "I see a kitchen with a kettle.", "{broken json", '["found"]',
                '{"found": "maybe", "answer": "?"}', '{"answer": "no verdict field"}'):
        assert parse_reply(raw) is None, raw


def test_parse_non_string_answer_coerced_empty():
    assert parse_reply('{"found": true, "answer": null}') == (True, "")
    assert parse_reply('{"found": true, "answer": 42}') == (True, "")


def test_parse_not_found_forces_empty_answer():
    # A location for something not seen is confabulated - observed live: the
    # model parroting a prompt example into a found=false reply.
    assert parse_reply('{"found": false, "answer": "on the desk, left of the monitor"}') == (False, "")


# --- one-sentence trim ------------------------------------------------------


def test_trim_cuts_after_first_sentence():
    assert (
        one_sentence("On the desk, left of the monitor. There is also a mug nearby. And a lamp.")
        == "On the desk, left of the monitor."
    )


def test_trim_survives_decimals_and_collapses_whitespace():
    # "2.5" must not be read as a sentence boundary; newlines collapse.
    assert one_sentence("next to the 2.5 kg\n  weight") == "next to the 2.5 kg weight"


def test_trim_hard_caps_a_rambler():
    rambling = "it is " + "very " * 100 + "far away"
    trimmed = one_sentence(rambling)
    assert len(trimmed) <= 163 and trimmed.endswith("...")


# --- qid echo + the frozen looked shape -------------------------------------


def test_looked_echoes_qid_exactly_and_matches_fixture_shape():
    fixture = json.loads((FIXTURES / "looked.json").read_text(encoding="ascii"))
    reply = build_looked("q7", "kitchen", True, "on the counter next to the kettle")
    assert reply == fixture  # byte-for-byte the frozen contract sample
    weird = "01JR-look-é"
    assert build_looked(weird, "kitchen", False, "")["qid"] == weird


def test_looked_second_question_gets_second_qid():
    # Stale-qid discipline is the agent's filter; our half is echoing exactly
    # what was asked, per question, never a remembered one.
    first = build_looked("q1", "kitchen", False, "")
    second = build_looked("q2", "kitchen", False, "")
    assert (first["qid"], second["qid"]) == ("q1", "q2")


# --- the full answer path, VLM faked ----------------------------------------


class _FakeVlm:
    """Duck-typed VlmClient: scripted replies, records how often it was asked."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def ask(self, prompt, jpeg, max_tokens=96):
        self.calls += 1
        return self.replies.pop(0)


def test_answer_look_room_is_ours_not_the_broadcasts():
    # Regression: a broadcast carries room=null (the TARGET filter); the reply's
    # room must be the answering node's. Caught live on the wire in T6.3.
    look = {"qid": "q9", "object": "glasses", "mode": "find", "room": None}
    reply = answer_look(_FakeVlm(['{"found": true, "answer": "by the kettle"}']), look, b"jpg", "kitchen")
    assert reply == {"qid": "q9", "room": "kitchen", "found": True, "answer": "by the kettle"}


def test_answer_look_retries_garbage_then_degrades_to_not_found():
    vlm = _FakeVlm(["", "still not json"])  # empty first call is the documented container quirk
    look = {"qid": "q10", "object": "keys", "mode": "find", "room": None}
    assert answer_look(vlm, look, b"jpg", "kitchen") == {"qid": "q10", "room": "kitchen", "found": False, "answer": ""}
    assert vlm.calls == 2  # exactly one retry, then honesty


# --- routing: which broadcasts we answer ------------------------------------


def test_broadcast_room_null_is_for_everyone():
    assert should_answer({"qid": "q1", "object": "glasses", "mode": "find", "room": None}, "kitchen")


def test_targeted_room_only_answers_there():
    guide = {"qid": "q2", "object": "glasses", "mode": "guide", "room": "bedroom"}
    assert should_answer(guide, "bedroom")
    assert not should_answer(guide, "kitchen")


def test_malformed_look_is_ignored():
    for payload in (None, "look!", {}, {"qid": "", "object": "x"}, {"qid": "q1", "object": "  "},
                    {"qid": "q1"}, {"object": "glasses"}, {"qid": 7, "object": "glasses"}):
        assert not should_answer(payload, "kitchen"), payload


# --- stale-frame decision ---------------------------------------------------


def test_fresh_export_uses_shm():
    assert choose_frame(0.4) == "shm"
    assert choose_frame(FRESH_S) == "shm"  # boundary counts as fresh


def test_stale_or_missing_export_goes_to_camera():
    assert choose_frame(FRESH_S + 0.1) == "camera"
    assert choose_frame(3600.0) == "camera"
    assert choose_frame(None) == "camera"  # vision.py never ran
