from __future__ import annotations

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

import sys
import threading
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_PYTHON = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python"
sys.path.insert(0, str(NODE_PYTHON))

from config import VoiceNodeConfig  # noqa: E402
from message_schema import SayCommand, SessionEvent  # noqa: E402
from speech_backend import ArduinoSpeechBackend  # noqa: E402
from voice_controller import VoiceController  # noqa: E402

from tests.fakes import (
    BlockUntilCancelled,
    FakeASR,
    FakeMQTTTransport,
    FakeTTS,
    PartialTranscript,
)


def config() -> VoiceNodeConfig:
    return VoiceNodeConfig(
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


def say(message_id: str, text: str, priority: str = "comfort") -> SayCommand:
    return SayCommand(message_id, time.time(), "living-room", text, priority)


def active_session(state: str = "active") -> SessionEvent:
    return SessionEvent(
        "fall-1", time.time(), "living-room", "fall-response", "safety", "check", state, "phase", {}
    )


def controller(*results: str | Exception | BlockUntilCancelled | PartialTranscript):
    asr = FakeASR(*results)
    tts = FakeTTS()
    transport = FakeMQTTTransport()
    speech = ArduinoSpeechBackend(asr, tts)
    voice = VoiceController(speech=speech, transport=transport, config=config(), sleep_fn=lambda _: None)
    return voice, asr, tts, transport


def test_idle_continuous_stream_publishes_rolling_transcripts_for_iq9_gate() -> None:
    voice, _asr, _tts, transport = controller("background conversation", "Hey QHome, where are my glasses?")
    voice.run_once()
    assert transport.queries == [
        "background conversation",
        "background conversation Hey QHome, where are my glasses?",
    ]
    assert voice.status_snapshot()["last_transcript"] == "Hey QHome, where are my glasses?"


def test_one_continuous_asr_session_handles_multiple_vad_finals() -> None:
    voice, asr, _tts, transport = controller("first", "second", "third")
    voice.run_once()
    assert asr.continuous_session_count == 1
    assert len(transport.queries) == 3


def test_partial_wake_phrase_is_preserved_when_whisper_final_drops_it() -> None:
    voice, _asr, _tts, transport = controller(
        PartialTranscript("Hey Home, where are"), "where are my spectacles?"
    )
    voice.run_once()
    assert transport.queries == ["Hey Home, where are my spectacles?"]


def test_early_wake_partial_survives_later_command_only_partial() -> None:
    voice, _asr, _tts, transport = controller(
        PartialTranscript("Hey Home, where are"),
        PartialTranscript("Where are my spectacles"),
        "Where are my spectacles?",
    )
    voice.run_once()
    assert transport.queries == ["Hey Home, where are my spectacles?"]


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


def test_idle_responder_phrase_is_not_hidden_by_rolling_background_text() -> None:
    voice, _asr, _tts, transport = controller(
        "background conversation", "I'm the first responder, brief me"
    )
    voice.run_once()
    assert transport.queries == ["background conversation"]
    assert transport.responder_briefs == 1


def test_incoming_say_cancels_asr_and_discards_partial_before_tts() -> None:
    voice, asr, tts, transport = controller(BlockUntilCancelled("Hey QHome leaked partial"))
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


def test_closed_session_returns_to_idle_continuous_transcription() -> None:
    voice, _asr, _tts, transport = controller("ordinary speech")
    voice.on_session_event(active_session())
    voice.on_session_event(active_session("closed"))
    voice.run_once()
    assert transport.heard == []
    assert transport.queries == ["ordinary speech"]
    assert voice.status_snapshot()["active_session_id"] is None


def test_runner_teardown_race_is_retried_without_error_state() -> None:
    voice, _asr, _tts, transport = controller(
        RuntimeError("A transcription session is already active (session-1). Please close it first")
    )

    voice.run_once()

    assert voice.status_snapshot()["state"] == "IDLE_LISTENING"
    assert voice.status_snapshot()["last_error"] == ""
    assert voice.status_snapshot()["asr_restart_count"] == 1
    assert transport.queries == []
