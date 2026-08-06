"""Small adapter around Arduino's local ASR and TTS bricks."""

# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Iterator, Literal, Protocol


@dataclass(frozen=True)
class TranscriptEvent:
    kind: Literal["partial", "final"]
    text: str


class SpeechBackend(Protocol):
    def listen_sentence(self, timeout: int) -> str: ...

    def listen_continuously(self) -> Iterator[TranscriptEvent]: ...

    def cancel_listen(self) -> None: ...

    def is_listening(self) -> bool: ...

    def speak(self, text: str) -> None: ...


class ArduinoSpeechBackend:
    """Uses one long-lived idle ASR stream plus bounded safety-session listens."""

    def __init__(self, asr, tts):
        self.asr = asr
        self.tts = tts
        self._cancel_requested = threading.Event()

    def listen_sentence(self, timeout: int) -> str:
        if self._cancel_requested.is_set():
            self._cancel_requested.clear()
        try:
            return self.asr.transcribe_sentence(timeout=timeout)
        finally:
            self._cancel_requested.clear()

    def listen_continuously(self) -> Iterator[TranscriptEvent]:
        """Yield every Arduino partial/final event without reopening ASR sessions."""
        if self._cancel_requested.is_set():
            self._cancel_requested.clear()
            return
        try:
            with self.asr.transcribe_until_cancelled() as stream:
                for event in stream:
                    kind = "partial" if event.type == "partial_text" else "final"
                    yield TranscriptEvent(kind, event.data)
        finally:
            self._cancel_requested.clear()

    def cancel_listen(self) -> None:
        self._cancel_requested.set()
        self.asr.cancel()

        # Close the tiny race where MQTT queues speech just before Arduino has
        # marked the ASR session active. Never block the MQTT network callback.
        def cancel_when_started() -> None:
            for _ in range(50):
                if not self._cancel_requested.is_set():
                    return
                if self.asr.is_transcribing():
                    self.asr.cancel()
                    return
                time.sleep(0.01)

        threading.Thread(target=cancel_when_started, daemon=True).start()

    def is_listening(self) -> bool:
        return self.asr.is_transcribing()

    def speak(self, text: str) -> None:
        # TextToSpeech.speak is synchronous in the current Arduino runtime.
        self.tts.speak(text)
