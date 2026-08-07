# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

@dataclass(frozen=True)
class BlockUntilCancelled:
    """A scripted listen that returns a last partial after cancellation."""

    partial: str = ""


@dataclass(frozen=True)
class PartialTranscript:
    text: str


@dataclass(frozen=True)
class FakeASREvent:
    type: str
    data: str


class _FakeTranscriptionStream:
    def __init__(self, asr: "FakeASR"):
        self.asr = asr

    def __enter__(self):
        if not self.asr._active_lock.acquire(blocking=False):
            raise RuntimeError("ASR session is already active")
        self.asr._active = True
        self.asr.continuous_session_count += 1
        self.asr.listen_started.set()
        self.asr.cancel_requested.clear()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.asr._active = False
        self.asr.listen_started.clear()
        self.asr._active_lock.release()

    def __iter__(self):
        while not self.asr.cancel_requested.is_set():
            try:
                result = self.asr.results.get_nowait()
            except queue.Empty:
                return
            if isinstance(result, Exception):
                raise result
            if isinstance(result, BlockUntilCancelled):
                self.asr.cancel_requested.wait()
                if result.partial:
                    yield FakeASREvent("partial_text", result.partial)
                return
            if isinstance(result, PartialTranscript):
                yield FakeASREvent("partial_text", result.text)
            else:
                yield FakeASREvent("full_text", result)


class FakeASR:
    """Host-side stand-in for Arduino AutomaticSpeechRecognition."""

    def __init__(self, *results: str | Exception | BlockUntilCancelled | PartialTranscript):
        self.results: queue.Queue[
            str | Exception | BlockUntilCancelled | PartialTranscript
        ] = queue.Queue()
        for result in results:
            self.results.put(result)
        self.listen_started = threading.Event()
        self.cancel_requested = threading.Event()
        self._active_lock = threading.Lock()
        self._active = False
        self.continuous_session_count = 0

    def queue_result(
        self, result: str | Exception | BlockUntilCancelled | PartialTranscript
    ) -> None:
        self.results.put(result)

    def transcribe_until_cancelled(self) -> _FakeTranscriptionStream:
        return _FakeTranscriptionStream(self)

    def transcribe_sentence(self, timeout: int = 0) -> str:
        if not self._active_lock.acquire(blocking=False):
            raise RuntimeError("ASR session is already active")
        self._active = True
        self.listen_started.set()
        self.cancel_requested.clear()
        try:
            wait = None if timeout == 0 else timeout
            try:
                result = self.results.get(timeout=wait)
            except queue.Empty:
                return ""
            if isinstance(result, Exception):
                raise result
            if isinstance(result, BlockUntilCancelled):
                self.cancel_requested.wait(timeout=wait)
                return result.partial if self.cancel_requested.is_set() else ""
            if isinstance(result, PartialTranscript):
                return result.text
            return result
        finally:
            self._active = False
            self.listen_started.clear()
            self._active_lock.release()

    def cancel(self) -> None:
        if self._active:
            self.cancel_requested.set()

    def is_transcribing(self) -> bool:
        return self._active


class FakeTTS:
    """Host-side stand-in for blocking Arduino TextToSpeech.speak."""

    def __init__(self, *, block: bool = False, failure: Exception | None = None):
        self.block = block
        self.failure = failure
        self.spoken: list[str] = []
        self.playback_started = threading.Event()
        self.playback_finished = threading.Event()
        self.release_playback = threading.Event()
        self._active_lock = threading.Lock()

    def speak(self, text: str) -> None:
        if not self._active_lock.acquire(blocking=False):
            raise RuntimeError("TTS session is already active")
        self.playback_finished.clear()
        self.playback_started.set()
        self.spoken.append(text)
        try:
            if self.failure:
                raise self.failure
            if self.block:
                self.release_playback.wait()
        finally:
            self.playback_started.clear()
            self.playback_finished.set()
            self._active_lock.release()
