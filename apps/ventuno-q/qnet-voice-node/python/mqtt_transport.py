# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""MQTT transport between one Ventuno voice node and the IQ9 hub."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Callable

import paho.mqtt.client as mqtt

from config import VoiceNodeConfig
from message_schema import SayCommand, SessionEvent


LOGGER = logging.getLogger("qnet.ventuno.mqtt")
SayHandler = Callable[[SayCommand], None]
SessionHandler = Callable[[SessionEvent], None]
StateProvider = Callable[[], str]

# The wire vocabulary for qnet/<room>/status (contracts/mqtt.md). Anything
# else (e.g. the controller's pre-first-listen "starting") reads as idle.
HEARTBEAT_STATES = ("idle", "listening", "speaking", "error")


class MQTTTransport:
    """Publishes the node's asks/heards and our 5 s status heartbeat.

    B3c: status follows the production heartbeat pattern - periodic,
    non-retained, QoS 0 to ``qnet/<room>/status``. No LWT and no retained
    payloads: a vanished node simply stops beating, and the dashboard's 15 s
    staleness rule marks it offline without a retained corpse claiming the
    node is alive (or dead) forever.
    """

    def __init__(self, config: VoiceNodeConfig):
        self.config = config
        self._say_handler: SayHandler | None = None
        self._session_handler: SessionHandler | None = None
        self._state_provider: StateProvider | None = None
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"qnet-{config.device_id}",
            protocol=mqtt.MQTTv311,
        )
        if config.mqtt_username:
            self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    @property
    def status_topic(self) -> str:
        return f"qnet/{self.config.room_id}/status"

    @property
    def ask_topic(self) -> str:
        return f"qnet/{self.config.room_id}/ask"

    @property
    def heard_topic(self) -> str:
        return f"qnet/{self.config.room_id}/heard"

    @property
    def say_topic(self) -> str:
        return f"qnet/{self.config.room_id}/say"

    def set_say_handler(self, handler: SayHandler) -> None:
        self._say_handler = handler

    def set_tts_handler(self, handler: SayHandler) -> None:
        """Compatibility alias for the pre-Phase-1 application."""
        self.set_say_handler(handler)

    def set_session_handler(self, handler: SessionHandler) -> None:
        self._session_handler = handler

    def set_state_provider(self, provider: StateProvider) -> None:
        """The heartbeat asks this for the node's current voice state."""
        self._state_provider = provider

    def start(self) -> None:
        self.client.connect_async(self.config.mqtt_host, self.config.mqtt_port, keepalive=30)
        self.client.loop_start()
        self.start_heartbeat()

    def close(self) -> None:
        self.stop_heartbeat()
        self.client.disconnect()
        self.client.loop_stop()

    # --- heartbeat (B3c) --------------------------------------------------

    def start_heartbeat(self) -> None:
        if self._heartbeat_thread is not None and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name="qnet-voice-heartbeat", daemon=True
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        self._heartbeat_stop.set()

    def publish_heartbeat(self) -> None:
        self.publish_voice_status(self._current_state())

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self.config.heartbeat_interval_seconds):
            try:
                self.publish_heartbeat()
            except Exception:
                # QoS 0 and periodic: the next beat is seconds away, and a
                # publish failure here just means the broker is unreachable.
                LOGGER.debug("Heartbeat publish failed; broker unreachable?", exc_info=True)

    def _current_state(self) -> str:
        state = "idle"
        if self._state_provider is not None:
            try:
                state = self._state_provider()
            except Exception:
                state = "error"
        return state if state in HEARTBEAT_STATES else "idle"

    # --- publishes --------------------------------------------------------

    def publish_query(self, text: str) -> str:
        return self._publish_ask("query", text)

    def publish_request(self, text: str) -> str:
        """Compatibility alias used by older host tests."""
        return self.publish_query(text)

    def publish_responder_brief(self) -> str:
        return self._publish_ask("responder_brief", "")

    def publish_heard(self, *, text: str, silence: bool) -> str:
        text = text.strip()
        if bool(silence) != (text == ""):
            raise ValueError("heard text and silence disagree")
        # Exactly the frozen fixture shape (contracts/fixtures/heard.json):
        # {text, silence}, nothing else. The returned id is log-local only.
        self._publish_json(self.heard_topic, {"text": text, "silence": bool(silence)})
        return str(uuid.uuid4())

    def publish_voice_status(
        self,
        voice_state: str,
        *,
        error: str | None = None,
        say_id: str | None = None,
    ) -> None:
        state = voice_state if voice_state in HEARTBEAT_STATES else "idle"
        payload = {
            "node": self.config.device_id,
            "room": self.config.room_id,
            "ts": time.time(),
            "state": state,
        }
        if error:
            payload["error"] = error
        if say_id:
            payload["say_id"] = say_id
        # Never retained, QoS 0: liveness is proven by arrival, not storage.
        self._publish_json(self.status_topic, payload, qos=0)

    def _publish_ask(self, kind: str, text: str) -> str:
        message_id = str(uuid.uuid4())
        self._publish_json(
            self.ask_topic,
            {
                "id": message_id,
                "ts": time.time(),
                "room": self.config.room_id,
                "kind": kind,
                "text": text.strip(),
            },
        )
        return message_id

    def _publish_json(self, topic: str, payload: dict, *, qos: int = 1) -> None:
        result = self.client.publish(
            topic,
            json.dumps(payload, separators=(",", ":")),
            qos=qos,
            retain=False,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish to {topic} failed with rc={result.rc}")

    # --- callbacks --------------------------------------------------------

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code != 0:
            LOGGER.error("MQTT connection failed: %s", reason_code)
            return
        self.connected = True
        client.subscribe(self.say_topic, qos=1)
        client.subscribe("qnet/session/+", qos=1)
        self.publish_heartbeat()
        LOGGER.info("Connected to IQ9; subscribed to %s and qnet/session/+", self.say_topic)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties) -> None:
        self.connected = False
        LOGGER.warning("Disconnected from MQTT: %s", reason_code)

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            if message.topic == self.say_topic:
                command = SayCommand.from_payload(message.payload)
                # B2: room is optional on the wire; cross-check only when sent.
                if command.room is not None and command.room != self.config.room_id:
                    raise ValueError("say payload room does not match topic room")
                if self._say_handler:
                    self._say_handler(command)
                return
            if message.topic.startswith("qnet/session/"):
                session = SessionEvent.from_payload(message.payload)
                topic_id = message.topic.removeprefix("qnet/session/")
                if session.session_id != topic_id:
                    raise ValueError("session payload id does not match topic id")
                if session.room == self.config.room_id and self._session_handler:
                    self._session_handler(session)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.warning("Rejected invalid message on %s: %s", message.topic, exc)
