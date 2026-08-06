# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import threading

from tests.fakes import BlockUntilCancelled, FakeASR, FakeMQTTTransport, FakeTTS


def test_fake_asr_models_transcript_silence_and_error() -> None:
    asr = FakeASR("hello", "", RuntimeError("runner unavailable"))
    assert asr.transcribe_sentence(timeout=1) == "hello"
    assert asr.transcribe_sentence(timeout=1) == ""
    try:
        asr.transcribe_sentence(timeout=1)
    except RuntimeError as exc:
        assert str(exc) == "runner unavailable"
    else:
        raise AssertionError("scripted ASR failure was not raised")


def test_fake_asr_cancel_can_return_last_partial() -> None:
    asr = FakeASR(BlockUntilCancelled("hey home partial"))
    result: list[str] = []
    worker = threading.Thread(target=lambda: result.append(asr.transcribe_sentence(timeout=2)))
    worker.start()
    assert asr.listen_started.wait(timeout=1)
    assert asr.is_transcribing()
    asr.cancel()
    worker.join(timeout=1)
    assert result == ["hey home partial"]
    assert not asr.is_transcribing()


def test_fake_tts_blocks_until_released() -> None:
    tts = FakeTTS(block=True)
    worker = threading.Thread(target=lambda: tts.speak("Are you okay?"))
    worker.start()
    assert tts.playback_started.wait(timeout=1)
    assert worker.is_alive()
    tts.release_playback.set()
    worker.join(timeout=1)
    assert tts.playback_finished.is_set()
    assert tts.spoken == ["Are you okay?"]


def test_fake_mqtt_records_voice_outputs() -> None:
    transport = FakeMQTTTransport()
    assert transport.publish_query("where are my glasses") == "fake-query-1"
    assert transport.publish_responder_brief() == "fake-responder-1"
    assert transport.publish_heard(text="", silence=True) == "fake-heard-1"
    assert transport.queries == ["where are my glasses"]
    assert transport.heard == [{"text": "", "silence": True}]
