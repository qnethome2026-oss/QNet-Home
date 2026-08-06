# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.

from __future__ import annotations

import wake_gate


def test_extracts_supported_wake_phrases() -> None:
    assert wake_gate.extract_wake_request("Hey Q Home, broadcast that dinner is ready") == "broadcast that dinner is ready"
    assert wake_gate.extract_wake_request("hey q home announce in the bedroom that hello") == "announce in the bedroom that hello"
    assert wake_gate.extract_wake_request("Hey Home: how are you?") == "how are you"
    assert wake_gate.extract_wake_request("He home. Broadcast the TOWER YOU") == "Broadcast the TOWER YOU"


def test_wake_phrase_mid_window_returns_only_the_remainder() -> None:
    # B1: detection runs over the rolling window, so background speech may
    # precede the phrase - and must never ride along into the request.
    assert wake_gate.extract_wake_request(
        "News is playing. Hey Home, where are my glasses?"
    ) == "where are my glasses"


def test_rejects_non_wake_speech_and_empty_commands() -> None:
    assert wake_gate.extract_wake_request("broadcast that dinner is ready") is None
    assert wake_gate.extract_wake_request("The television said hey q home") is None
    assert wake_gate.extract_wake_request("Hey Q Home") is None


def test_custom_phrase_keeps_the_asr_tolerances() -> None:
    pattern = wake_gate.compile_wake_pattern("hey house")
    assert wake_gate.extract_wake_request("hey house open the door", pattern) == "open the door"
    # Whisper's "Hey"->"He" rendering and the optional "q" both survive.
    assert wake_gate.extract_wake_request("he house open the door", pattern) == "open the door"
    assert wake_gate.extract_wake_request("hey q house open the door", pattern) == "open the door"
    # The default phrase no longer matches under a custom pattern.
    assert wake_gate.extract_wake_request("hey home open the door", pattern) is None
