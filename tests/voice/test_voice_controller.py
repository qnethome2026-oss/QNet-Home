# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Controller behavior on fakes: wake gating (B1), dedupe/backoff (B3).

Rewritten from the extracted branch's suite: the four idle tests that asserted
UNGATED rolling-transcript publishing now assert the opposite - the wake gate
is wired, so background speech never leaves the node (review blocker B1).
"""

from __future__ import annotations

import json
import logging
import threading
import time

from config import VoiceNodeConfig
from message_schema import SayCommand, SessionEvent
from speech_backend import ArduinoSpeechBackend
from voice_controller import (
    ASR_FAILURE_BACKOFF_CAP_SECONDS,
    ASR_FAILURE_BACKOFF_INITIAL_SECONDS,
    VoiceController,
)

from tests.voice.fakes import (
    BlockUntilCancelled,
    FakeASR,
    FakeMQTTTransport,
    FakeTTS,
    PartialTranscript,
)


def config(**overrides) -> VoiceNodeConfig:
    settings = dict(
        device_id="ventuno-living-room",
        room_id="living-room",
        groups=(),
        mqtt_host="iq9",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
        microphone_device="usb:1",
        speaker_device="usb:1",
        language="en",
        idle_listen_timeout_seconds=2,
        session_listen_timeout_seconds=1,
        post_tts_guard_ms=0,
        tts_queue_size=20,
        responder_phrase="I am the first responder",
    )
    settings.update(overrides)
    return VoiceNodeConfig(**settings)


def say(message_id: str, text: str, priority: str = "comfort") -> SayCommand:
    return SayCommand(message_id, time.time(), "living-room", text, priority)


def active_session(state: str = "active") -> SessionEvent:
    return SessionEvent(
        "fall-1", time.time(), "living-room", "fall-response", "safety", "check", state, "phase", {}
    )


def controller(
    *results: str | Exception | BlockUntilCancelled | PartialTranscript,
    cfg: VoiceNodeConfig | None = None,
    sleep_fn=None,
):
    asr = FakeASR(*results)
    tts = FakeTTS()
    transport = FakeMQTTTransport()
    speech = ArduinoSpeechBackend(asr, tts)
    voice = VoiceController(
        speech=speech,
        transport=transport,
        config=cfg or config(),
        sleep_fn=sleep_fn or (lambda _: None),
    )
    return voice, asr, tts, transport


# --- B1: the wake gate decides what leaves the node -----------------------


def test_background_chatter_publishes_nothing() -> None:
    voice, _asr, _tts, transport = controller(
        "the kettle is boiling", "someone is at the door", "lovely weather today"
    )
    voice.run_once()
    assert transport.queries == []
    assert transport.responder_briefs == 0
    assert transport.heard == []


def test_wake_mid_window_publishes_only_the_stripped_command() -> None:
    # The wake phrase arrives mid-window after background speech; the ask must
    # carry the command only - no "News is playing", no "Hey Home".
    voice, _asr, _tts, transport = controller(
        "News is playing.", "Hey Home, where are my glasses?"
    )
    voice.run_once()
    assert transport.queries == ["where are my glasses"]


def test_wake_split_across_vad_finals_is_still_detected() -> None:
    # The rolling window exists because Whisper can cut between the wake
    # phrase and the command; detection runs over the merged text.
    voice, _asr, _tts, transport = controller("Hey Home", "where are my keys")
    voice.run_once()
    assert transport.queries == ["where are my keys"]


def test_bare_wake_without_command_publishes_nothing() -> None:
    voice, _asr, _tts, transport = controller("Hey Home")
    voice.run_once()
    assert transport.queries == []


def test_one_continuous_asr_session_gates_each_final_independently() -> None:
    voice, asr, _tts, transport = controller(
        "the kettle is on", "Hey Home, where are my keys", "more chatter"
    )
    voice.run_once()
    assert asr.continuous_session_count == 1
    assert transport.queries == ["where are my keys"]


def test_partial_wake_phrase_is_preserved_when_whisper_final_drops_it() -> None:
    voice, _asr, _tts, transport = controller(
        PartialTranscript("Hey Home, where are"), "where are my spectacles?"
    )
    voice.run_once()
    assert transport.queries == ["where are my spectacles"]


def test_early_wake_partial_survives_later_command_only_partial() -> None:
    voice, _asr, _tts, transport = controller(
        PartialTranscript("Hey Home, where are"),
        PartialTranscript("Where are my spectacles"),
        "Where are my spectacles?",
    )
    voice.run_once()
    assert transport.queries == ["where are my spectacles"]


def test_wake_phrase_is_configurable_with_asr_tolerance_kept() -> None:
    voice, _asr, _tts, transport = controller(
        "hey home open the door",  # the default phrase no longer matches
        "he house open the door",  # "hey"->"he" tolerance for the new phrase
        cfg=config(wake_phrase="hey house"),
    )
    voice.run_once()
    assert transport.queries == ["open the door"]


def test_idle_responder_phrase_publishes_brief_and_no_query() -> None:
    # The responder phrase needs no wake word: it outranks the gate (contract).
    voice, _asr, _tts, transport = controller(
        "background conversation", "I'm the first responder, brief me"
    )
    voice.run_once()
    assert transport.queries == []
    assert transport.responder_briefs == 1


def test_no_transcript_content_in_info_logs_or_status(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="qnet.ventuno.voice"):
        voice, _asr, _tts, transport = controller(
            "pineapple casserole secret", "Hey Home, locate my dentures"
        )
        voice.run_once()
    assert transport.queries == ["locate my dentures"]
    for word in ("pineapple", "casserole", "secret", "dentures", "locate"):
        assert word not in caplog.text.lower()
    # The WebUI snapshot exposes only post-gate published text - never the
    # rolling window or raw finals (the page is unauthenticated on the LAN).
    snapshot = voice.status_snapshot()
    assert "last_transcript" not in snapshot
    assert "last_partial" not in snapshot
    assert "pineapple" not in json.dumps(snapshot)
    assert snapshot["last_request"] == "locate my dentures"


# --- sessions (unchanged contract behavior) -------------------------------


def test_active_session_publishes_transcript_and_distinguishable_silence() -> None:
    voice, _asr, _tts, transport = controller("I am okay", "")
    voice.on_session_event(active_session())
    voice.run_once()
    voice.run_once()
    assert transport.heard == [
        {"text": "I am okay", "silence": False},
        {"text": "", "silence": True},
    ]


def test_responder_phrase_wins_even_during_active_session() -> None:
    voice, _asr, _tts, transport = controller("I'm the first responder, brief me")
    voice.on_session_event(active_session())
    voice.run_once()
    assert transport.responder_briefs == 1
    assert transport.heard == []


def test_closed_session_returns_to_idle_gated_transcription() -> None:
    voice, _asr, _tts, transport = controller("Hey Home, say something nice")
    voice.on_session_event(active_session())
    voice.on_session_event(active_session("closed"))
    voice.run_once()
    assert transport.heard == []
    assert transport.queries == ["say something nice"]
    assert voice.status_snapshot()["active_session_id"] is None


# --- half-duplex + priorities (unchanged behavior) ------------------------


def test_incoming_say_cancels_asr_and_discards_partial_before_tts() -> None:
    voice, asr, tts, transport = controller(BlockUntilCancelled("Hey Q Home leaked partial"))
    worker = threading.Thread(target=voice.run_once)
    worker.start()
    assert asr.listen_started.wait(timeout=1)
    voice.on_tts_command(say("say-1", "Please stand clear", "safety"))
    worker.join(timeout=2)
    assert not worker.is_alive()
    voice.run_once()
    assert transport.queries == []
    assert tts.spoken == ["Please stand clear"]


def test_asr_is_inactive_for_entire_tts_playback() -> None:
    voice, asr, _tts, _transport = controller(BlockUntilCancelled("speaker leakage"))
    blocking_tts = FakeTTS(block=True)
    voice.speech.tts = blocking_tts
    listener = threading.Thread(target=voice.run_once)
    listener.start()
    assert asr.listen_started.wait(timeout=1)
    voice.on_tts_command(say("say-half-duplex", "This must not be transcribed"))
    listener.join(timeout=2)

    speaker = threading.Thread(target=voice.run_once)
    speaker.start()
    assert blocking_tts.playback_started.wait(timeout=1)
    assert not asr.is_transcribing()
    blocking_tts.release_playback.set()
    speaker.join(timeout=1)
    assert not speaker.is_alive()


def test_safety_speech_precedes_comfort_and_qos_duplicates_are_ignored() -> None:
    voice, _asr, tts, _transport = controller()
    voice.on_tts_command(say("comfort-1", "Dinner is ready", "comfort"))
    voice.on_tts_command(say("safety-1", "Are you okay?", "safety"))
    voice.on_tts_command(say("safety-1", "Are you okay?", "safety"))
    voice.run_once()
    voice.run_once()
    assert tts.spoken == ["Are you okay?", "Dinner is ready"]


# --- B3a: dedupe must not eat the retry of a failed playback --------------


def test_failed_tts_stays_retryable_and_success_finally_dedupes() -> None:
    voice, _asr, _tts, _transport = controller()
    broken = FakeTTS(failure=RuntimeError("speaker unplugged"))
    voice.speech.tts = broken
    voice.on_tts_command(say("safety-9", "Please respond if you can", "safety"))
    voice.run_once()
    assert broken.spoken == ["Please respond if you can"]  # attempted, failed

    # The hub retries the SAME id: it must be accepted and actually spoken.
    working = FakeTTS()
    voice.speech.tts = working
    voice.on_tts_command(say("safety-9", "Please respond if you can", "safety"))
    voice.run_once()
    assert working.spoken == ["Please respond if you can"]

    # Only now is the id consumed: further duplicates are deduped.
    voice.on_tts_command(say("safety-9", "Please respond if you can", "safety"))
    voice.run_once()
    assert working.spoken == ["Please respond if you can"]


# --- B3b: exponential backoff on persistent ASR failure -------------------


def test_persistent_asr_failure_backs_off_exponentially_and_resets() -> None:
    sleeps: list[float] = []
    failures = [RuntimeError(f"runner down {n}") for n in range(7)]
    voice, asr, _tts, transport = controller(*failures, sleep_fn=sleeps.append)
    for _ in failures:
        voice.run_once()
    assert sleeps == [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 10.0]  # doubling, capped
    assert sleeps[0] == ASR_FAILURE_BACKOFF_INITIAL_SECONDS
    assert sleeps[-1] == ASR_FAILURE_BACKOFF_CAP_SECONDS

    # One successful ASR event resets the ladder to the initial delay.
    sleeps.clear()
    asr.queue_result("Hey Home, hello there")
    voice.run_once()  # yields the final (0.1 s clean-restart sleep only)
    assert transport.queries == ["hello there"]
    asr.queue_result(RuntimeError("runner down again"))
    voice.run_once()
    assert sleeps[-1] == ASR_FAILURE_BACKOFF_INITIAL_SECONDS


def test_runner_teardown_race_is_retried_without_error_state() -> None:
    voice, _asr, _tts, transport = controller(
        RuntimeError("A transcription session is already active (session-1). Please close it first")
    )

    voice.run_once()

    assert voice.status_snapshot()["state"] == "IDLE_LISTENING"
    assert voice.status_snapshot()["last_error"] == ""
    assert voice.status_snapshot()["asr_restart_count"] == 1
    assert transport.queries == []


def test_responder_phrases_match_anywhere_and_cover_summary_asks() -> None:
    """User finding (2026-08-06): only "I'm the first responder..." as a strict
    prefix triggered the brief. A responder may lead with the wake phrase or
    just ask for a summary; the person on the floor asking a bare question must
    NOT trigger it."""
    voice, _asr, _tts, _transport = controller("anything")
    match = voice._matches_responder_phrase
    assert match("I'm the first responder")
    assert match("Hey home, I'm the first responder, what happened?")
    assert match("give me a summary of what happened")
    assert match("Tell me what happened")
    assert match("I am a paramedic")
    # The resident's own words stay replies.
    assert not match("what")
    assert not match("I don't know what happened")
    assert not match("my head hurts")
    assert not match("")
