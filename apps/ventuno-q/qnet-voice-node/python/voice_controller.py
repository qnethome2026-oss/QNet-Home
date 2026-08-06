# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""VAD-driven, half-duplex voice state machine for one Ventuno Q node."""

from __future__ import annotations

import itertools
import logging
import queue
import re
import threading
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Callable

import wake_gate
from config import VoiceNodeConfig
from message_schema import SayCommand, SessionEvent
from speech_backend import SpeechBackend
from transcript_buffer import RollingTranscriptBuffer

if TYPE_CHECKING:
    from mqtt_transport import MQTTTransport


LOGGER = logging.getLogger("qnet.ventuno.voice")
# B2: our engine's comfort loop sends prio "routine"; any unknown priority is
# accepted and spoken last rather than rejected into silence.
PRIORITY = {"safety": 0, "comfort": 1, "routine": 2}
LOWEST_PRIORITY = max(PRIORITY.values())
ASR_RESTART_BACKOFF_SECONDS = 0.1
ASR_BUSY_BACKOFF_SECONDS = 0.25
# B3b: a persistently failing ASR runner must not be hammered at 4 Hz (nor the
# broker spammed with error statuses at that rate); back off exponentially and
# recover fast once events flow again.
ASR_FAILURE_BACKOFF_INITIAL_SECONDS = 0.25
ASR_FAILURE_BACKOFF_CAP_SECONDS = 10.0


class VoiceController:
    """The only code allowed to start ASR or TTS on the node."""

    def __init__(
        self,
        *,
        speech: SpeechBackend,
        transport: MQTTTransport,
        config: VoiceNodeConfig,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self.speech = speech
        self.transport = transport
        self.config = config
        self.sleep_fn = sleep_fn
        self.tts_queue: queue.PriorityQueue[tuple[int, int, SayCommand]] = queue.PriorityQueue(
            maxsize=config.tts_queue_size
        )
        self._sequence = itertools.count()
        self.recent_ids: deque[str] = deque(maxlen=100)
        self.recent_id_set: set[str] = set()
        self.queued_ids: set[str] = set()
        # Ids being spoken right now: dedupes QoS-1 redelivery during playback
        # without permanently consuming an id whose playback then fails (B3a).
        self._inflight_ids: set[str] = set()
        self._lock = threading.RLock()
        self._state = "STARTING"
        self._last_request = ""
        self._last_tts = ""
        self._last_error = ""
        self._last_asr_event_at: float | None = None
        self._asr_stream_started_at: float | None = None
        self._asr_restart_count = 0
        self._asr_failure_backoff = ASR_FAILURE_BACKOFF_INITIAL_SECONDS
        self._active_session_id: str | None = None
        self._listen_generation = 0
        self._current_listen_generation: int | None = None
        self._cancelled_generations: set[int] = set()
        self._transcripts = RollingTranscriptBuffer(config.transcript_window_seconds)
        # B1: the wake gate is the node-side activation decision. Compiled once
        # from config so "hey home" can become any phrase while keeping the
        # ASR tolerances ("he home", "hey q home").
        self._wake_pattern = wake_gate.compile_wake_pattern(config.wake_phrase)

    def on_tts_command(self, command: SayCommand) -> None:
        cancel_listen = False
        with self._lock:
            if (
                command.message_id in self.recent_id_set
                or command.message_id in self.queued_ids
                or command.message_id in self._inflight_ids
            ):
                return
            try:
                self.tts_queue.put_nowait(
                    (PRIORITY.get(command.priority, LOWEST_PRIORITY), next(self._sequence), command)
                )
                self.queued_ids.add(command.message_id)
            except queue.Full:
                self._set_status(state="ERROR", error="TTS queue is full")
                self._publish_status("error", error="TTS queue is full", say_id=command.message_id)
                return
            if self._current_listen_generation is not None:
                self._cancelled_generations.add(self._current_listen_generation)
                self._state = "CANCELLING_LISTEN"
                cancel_listen = True
        if cancel_listen:
            self.speech.cancel_listen()

    def on_session_event(self, event: SessionEvent) -> None:
        cancel_listen = False
        with self._lock:
            if event.state == "active":
                self._active_session_id = event.session_id
            elif self._active_session_id == event.session_id:
                self._active_session_id = None
            if self._current_listen_generation is not None:
                self._cancelled_generations.add(self._current_listen_generation)
                cancel_listen = True
        # Wake the controller immediately so it switches between the long-lived
        # idle stream and bounded safety-session listens.
        if cancel_listen:
            self.speech.cancel_listen()

    def run_once(self) -> None:
        command = self._take_next_command()
        if command is not None:
            self._speak(command)
            return
        self._listen_once()

    def voice_state(self) -> str:
        """The four-state wire view, for the transport's heartbeat (B3c)."""
        with self._lock:
            return self._wire_voice_state()

    def status_snapshot(self) -> dict[str, Any]:
        # B1/R5: no raw transcript here - this feeds an unauthenticated LAN
        # page. Only text that already left the node (post-gate publishes,
        # spoken says) is exposed.
        with self._lock:
            return {
                "device_id": self.config.device_id,
                "room_id": self.config.room_id,
                "state": self._state,
                "voice_state": self._wire_voice_state(),
                "mqtt_connected": self.transport.connected,
                "active_session_id": self._active_session_id,
                "last_request": self._last_request,
                "last_tts": self._last_tts,
                "last_error": self._last_error,
                "last_asr_event_at": self._last_asr_event_at,
                "asr_stream_started_at": self._asr_stream_started_at,
                "asr_restart_count": self._asr_restart_count,
                "queued_tts": self.tts_queue.qsize(),
            }

    def _take_next_command(self) -> SayCommand | None:
        with self._lock:
            try:
                _priority, _sequence, command = self.tts_queue.get_nowait()
            except queue.Empty:
                return None
            self.queued_ids.discard(command.message_id)
            return command

    def _listen_once(self) -> None:
        # Queue inspection and ASR ownership are one atomic transition. An MQTT
        # callback arriving afterward sees this generation and cancels it.
        with self._lock:
            command = self._take_next_command()
            if command is not None:
                pass
            else:
                self._listen_generation += 1
                generation = self._listen_generation
                self._current_listen_generation = generation
                active_session = self._active_session_id is not None
                self._state = "SESSION_LISTENING" if active_session else "IDLE_LISTENING"
                self._last_error = ""
        if command is not None:
            self._speak(command)
            return

        self._publish_status("listening")
        if active_session:
            self._listen_for_session(generation)
        else:
            self._listen_continuously(generation)

    def _listen_continuously(self, generation: int) -> None:
        """Keep one Arduino ASR session open; the wake gate decides what leaves."""
        failure: Exception | None = None
        with self._lock:
            self._asr_stream_started_at = time.time()
        try:
            for event in self.speech.listen_continuously():
                with self._lock:
                    cancelled = generation in self._cancelled_generations
                if cancelled:
                    break
                text = (event.text or "").strip()
                if event.kind == "partial":
                    self._transcripts.add_partial(text)
                    with self._lock:
                        self._last_asr_event_at = time.time()
                    continue
                if not text:
                    continue
                rolling = self._transcripts.add_final(text)
                with self._lock:
                    self._last_asr_event_at = time.time()
                self._reset_asr_backoff()
                # Responder phrase outranks the wake gate: a first responder
                # announcing themselves must get the brief in any state.
                if self._matches_responder_phrase(text):
                    self._publish_responder_brief()
                    continue
                # B1: detect over the ROLLING window (Whisper can split the
                # wake phrase across finals) but publish only the remainder
                # after the phrase - background speech never rides along.
                request = wake_gate.extract_wake_request(rolling, self._wake_pattern)
                if request is None:
                    continue  # not addressed to us: nothing leaves the node
                # The wake+command is consumed; drop the window so later
                # background finals cannot re-trigger on the same match.
                self._transcripts.clear()
                self._publish_wake_request(request)
        except Exception as exc:
            failure = exc

        cancelled = self._finish_generation(generation)
        if cancelled:
            return
        with self._lock:
            self._asr_restart_count += 1
        self._handle_asr_failure(failure)

    def _listen_for_session(self, generation: int) -> None:
        """A fall session needs a bounded result, including explicit silence."""
        failure: Exception | None = None
        transcript = ""
        try:
            transcript = (
                self.speech.listen_sentence(timeout=self.config.session_listen_timeout_seconds)
                or ""
            ).strip()
        except Exception as exc:
            failure = exc

        cancelled = self._finish_generation(generation)
        if cancelled:
            return
        if failure is not None:
            self._handle_asr_failure(failure)
            return

        self._reset_asr_backoff()
        if self._matches_responder_phrase(transcript):
            self._publish_responder_brief()
            return
        try:
            silence = not bool(transcript)
            message_id = self.transport.publish_heard(text=transcript, silence=silence)
            self._set_status(state="SESSION_LISTENING", request=transcript)
            # Length/boolean only - session transcripts stay out of the logs.
            LOGGER.info(
                "Published session heard result %s (silence=%s, %d chars)",
                message_id,
                silence,
                len(transcript),
            )
        except Exception as exc:
            LOGGER.exception("Failed to publish heard result")
            self._set_status(state="ERROR", error=f"MQTT: {exc}")
            self._publish_status("error", error=f"MQTT: {exc}")

    def _finish_generation(self, generation: int) -> bool:
        with self._lock:
            cancelled = generation in self._cancelled_generations
            self._cancelled_generations.discard(generation)
            if self._current_listen_generation == generation:
                self._current_listen_generation = None
            return cancelled

    def _reset_asr_backoff(self) -> None:
        with self._lock:
            self._asr_failure_backoff = ASR_FAILURE_BACKOFF_INITIAL_SECONDS

    def _handle_asr_failure(self, failure: Exception | None) -> None:
        # A cleanly-ended continuous stream is unexpected but recoverable.
        if failure is None:
            self._reset_asr_backoff()
            self._set_status(state="IDLE_LISTENING", error="")
            self.sleep_fn(ASR_RESTART_BACKOFF_SECONDS)
            return
        if "transcription session is already active" in str(failure).lower():
            LOGGER.warning("ASR runner is closing the previous session; retrying shortly")
            self._set_status(state="IDLE_LISTENING", error="")
            self.sleep_fn(ASR_BUSY_BACKOFF_SECONDS)
            return
        LOGGER.exception("ASR failed", exc_info=failure)
        self._set_status(state="ERROR", error=f"ASR: {failure}")
        self._publish_status("error", error=f"ASR: {failure}")
        # B3b: double the wait on every consecutive failure (0.25 s -> 10 s
        # cap); any successful ASR event resets it via _reset_asr_backoff.
        with self._lock:
            delay = self._asr_failure_backoff
            self._asr_failure_backoff = min(delay * 2, ASR_FAILURE_BACKOFF_CAP_SECONDS)
        self.sleep_fn(delay)

    def _publish_wake_request(self, request: str) -> None:
        try:
            message_id = self.transport.publish_query(request)
            self._set_status(state="IDLE_LISTENING", request=request)
            # The request already left the node; log its size, not its words.
            LOGGER.info("Published wake request %s (%d chars)", message_id, len(request))
        except Exception as exc:
            LOGGER.exception("Failed to publish voice query")
            self._set_status(state="ERROR", error=f"MQTT: {exc}")
            self._publish_status("error", error=f"MQTT: {exc}")

    def _publish_responder_brief(self) -> None:
        try:
            message_id = self.transport.publish_responder_brief()
            self._set_status(state="IDLE_LISTENING", request="responder_brief")
            LOGGER.info("Published responder brief request %s", message_id)
        except Exception as exc:
            LOGGER.exception("Failed to publish responder brief")
            self._set_status(state="ERROR", error=f"MQTT: {exc}")
            self._publish_status("error", error=f"MQTT: {exc}")

    def _speak(self, command: SayCommand) -> None:
        with self._lock:
            if command.message_id in self.recent_id_set:
                return
            self._inflight_ids.add(command.message_id)
            # Never combine pre-playback speech or the speaker's output with a
            # later user query when ASR resumes.
            self._transcripts.clear()
        self._set_status(state="SPEAKING", tts=command.text, error="")
        self._publish_status("speaking", say_id=command.message_id)
        try:
            self.speech.speak(command.text)
        except Exception as exc:
            LOGGER.exception("TTS failed")
            self._set_status(state="ERROR", error=f"TTS: {exc}")
            self._publish_status("error", error=f"TTS: {exc}", say_id=command.message_id)
            return
        finally:
            with self._lock:
                self._inflight_ids.discard(command.message_id)
        # B3a: remember only AFTER a successful playback. A say whose playback
        # failed was never heard in the room - the hub's retry must not be
        # deduped into silence. The in-flight set above still absorbs QoS-1
        # redelivery while the speaker is busy.
        with self._lock:
            self._remember(command.message_id)
        self._set_status(state="POST_TTS_GUARD")
        self.sleep_fn(self.config.post_tts_guard_ms / 1000)
        self._set_status(state="IDLE_LISTENING")
        self._publish_status("idle", say_id=command.message_id)

    def _matches_responder_phrase(self, transcript: str) -> bool:
        def normalize(value: str) -> str:
            value = re.sub(r"\bi['’]m\b", "i am", value.lower())
            return re.sub(r"[^a-z0-9]+", " ", value).strip()

        normalized = normalize(transcript)
        expected = normalize(self.config.responder_phrase)
        return bool(normalized and expected and normalized.startswith(expected))

    def _remember(self, message_id: str) -> None:
        if len(self.recent_ids) == self.recent_ids.maxlen:
            removed = self.recent_ids.popleft()
            self.recent_id_set.discard(removed)
        self.recent_ids.append(message_id)
        self.recent_id_set.add(message_id)

    def _wire_voice_state(self) -> str:
        if self._state == "STARTING":
            return "starting"
        if self._state in {"IDLE_LISTENING", "SESSION_LISTENING", "CANCELLING_LISTEN"}:
            return "listening"
        if self._state == "SPEAKING":
            return "speaking"
        if self._state == "ERROR":
            return "error"
        return "idle"

    def _publish_status(self, state: str, **kwargs) -> None:
        try:
            self.transport.publish_voice_status(state, **kwargs)
        except Exception:
            LOGGER.exception("Failed to publish node status")

    def _set_status(
        self,
        *,
        state: str | None = None,
        request: str | None = None,
        tts: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if state is not None:
                self._state = state
            if request is not None:
                self._last_request = request
            if tts is not None:
                self._last_tts = tts
            if error is not None:
                self._last_error = error
