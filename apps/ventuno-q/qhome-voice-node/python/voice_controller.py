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

from config import VoiceNodeConfig
from message_schema import SayCommand, SessionEvent
from speech_backend import SpeechBackend
from transcript_buffer import RollingTranscriptBuffer

if TYPE_CHECKING:
    from mqtt_transport import MQTTTransport


LOGGER = logging.getLogger("qnet.ventuno.voice")
PRIORITY = {"safety": 0, "comfort": 1}
ASR_RESTART_BACKOFF_SECONDS = 0.1
ASR_BUSY_BACKOFF_SECONDS = 0.25


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
        self._lock = threading.RLock()
        self._state = "STARTING"
        self._last_transcript = ""
        self._last_request = ""
        self._last_tts = ""
        self._last_error = ""
        self._last_partial = ""
        self._last_asr_event_at: float | None = None
        self._asr_stream_started_at: float | None = None
        self._asr_restart_count = 0
        self._active_session_id: str | None = None
        self._listen_generation = 0
        self._current_listen_generation: int | None = None
        self._cancelled_generations: set[int] = set()
        self._transcripts = RollingTranscriptBuffer(config.transcript_window_seconds)

    def on_tts_command(self, command: SayCommand) -> None:
        cancel_listen = False
        with self._lock:
            if command.message_id in self.recent_id_set or command.message_id in self.queued_ids:
                return
            try:
                self.tts_queue.put_nowait(
                    (PRIORITY[command.priority], next(self._sequence), command)
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

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "device_id": self.config.device_id,
                "room_id": self.config.room_id,
                "state": self._state,
                "voice_state": self._wire_voice_state(),
                "mqtt_connected": self.transport.connected,
                "active_session_id": self._active_session_id,
                "last_transcript": self._last_transcript,
                "last_request": self._last_request,
                "last_tts": self._last_tts,
                "last_error": self._last_error,
                "last_partial": self._last_partial,
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
        """Keep one Arduino ASR session open and forward every VAD final."""
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
                        self._last_partial = text
                        self._last_asr_event_at = time.time()
                    continue
                if not text:
                    continue
                rolling = self._transcripts.add_final(text)
                with self._lock:
                    self._last_partial = ""
                    self._last_asr_event_at = time.time()
                self._set_status(transcript=text)
                if self._matches_responder_phrase(text):
                    self._publish_responder_brief()
                else:
                    self._publish_idle_transcript(rolling)
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

        self._set_status(transcript=transcript)
        if self._matches_responder_phrase(transcript):
            self._publish_responder_brief()
            return
        try:
            message_id = self.transport.publish_heard(text=transcript, silence=not bool(transcript))
            self._set_status(state="SESSION_LISTENING")
            LOGGER.info("Published session heard result %s", message_id)
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

    def _handle_asr_failure(self, failure: Exception | None) -> None:
        # A cleanly-ended continuous stream is unexpected but recoverable.
        if failure is None:
            self._set_status(state="IDLE_LISTENING", error="")
            self.sleep_fn(ASR_RESTART_BACKOFF_SECONDS)
            return
        if failure is not None:
            if "transcription session is already active" in str(failure).lower():
                LOGGER.warning("ASR runner is closing the previous session; retrying shortly")
                self._set_status(state="IDLE_LISTENING", error="")
                self.sleep_fn(ASR_BUSY_BACKOFF_SECONDS)
                return
            LOGGER.exception("ASR failed", exc_info=failure)
            self._set_status(state="ERROR", error=f"ASR: {failure}")
            self._publish_status("error", error=f"ASR: {failure}")
            self.sleep_fn(0.25)

    def _publish_idle_transcript(self, transcript: str) -> None:
        try:
            message_id = self.transport.publish_query(transcript)
            self._set_status(state="IDLE_LISTENING", request=transcript)
            LOGGER.info("Published rolling transcript %s: %s", message_id, transcript)
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
            self._remember(command.message_id)
            # Never combine pre-playback speech or the speaker's output with a
            # later user query when ASR resumes.
            self._transcripts.clear()
            self._last_partial = ""
        self._set_status(state="SPEAKING", tts=command.text, error="")
        self._publish_status("speaking", say_id=command.message_id)
        try:
            self.speech.speak(command.text)
        except Exception as exc:
            LOGGER.exception("TTS failed")
            self._set_status(state="ERROR", error=f"TTS: {exc}")
            self._publish_status("error", error=f"TTS: {exc}", say_id=command.message_id)
            return
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
        transcript: str | None = None,
        request: str | None = None,
        tts: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if state is not None:
                self._state = state
            if transcript is not None:
                self._last_transcript = transcript
            if request is not None:
                self._last_request = request
            if tts is not None:
                self._last_tts = tts
            if error is not None:
                self._last_error = error
