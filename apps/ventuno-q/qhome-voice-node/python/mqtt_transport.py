"""MQTT transport between one Ventuno voice node and the IQ9 hub."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Callable

import paho.mqtt.client as mqtt

from config import VoiceNodeConfig
from message_schema import SayCommand, SessionEvent


LOGGER = logging.getLogger("qnet.ventuno.mqtt")
SayHandler = Callable[[SayCommand], None]
SessionHandler = Callable[[SessionEvent], None]


class MQTTTransport:
    def __init__(self, config: VoiceNodeConfig):
        self.config = config
        self._say_handler: SayHandler | None = None
        self._session_handler: SessionHandler | None = None
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"qnet-{config.device_id}",
            protocol=mqtt.MQTTv311,
        )
        if config.mqtt_username:
            self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self.client.will_set(
            self.status_topic,
            self._status_json("offline", "idle"),
            qos=1,
            retain=True,
        )
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

    def start(self) -> None:
        self.client.connect_async(self.config.mqtt_host, self.config.mqtt_port, keepalive=30)
        self.client.loop_start()

    def close(self) -> None:
        if self.connected:
            self.publish_voice_status("idle", online=False)
        self.client.disconnect()
        self.client.loop_stop()

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
        message_id = str(uuid.uuid4())
        self._publish_json(
            self.heard_topic,
            {
                "id": message_id,
                "ts": time.time(),
                "room": self.config.room_id,
                "text": text,
                "silence": bool(silence),
            },
        )
        return message_id

    def publish_voice_status(
        self,
        voice_state: str,
        *,
        error: str | None = None,
        say_id: str | None = None,
        online: bool = True,
    ) -> None:
        payload = {
            "ts": time.time(),
            "room": self.config.room_id,
            "node_id": self.config.device_id,
            "state": "online" if online else "offline",
            "voice_state": voice_state,
        }
        if error:
            payload["error"] = error
        if say_id:
            payload["say_id"] = say_id
        self._publish_json(self.status_topic, payload, retain=True)

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

    def _publish_json(self, topic: str, payload: dict, *, retain: bool = False) -> None:
        result = self.client.publish(
            topic,
            json.dumps(payload, separators=(",", ":")),
            qos=1,
            retain=retain,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish to {topic} failed with rc={result.rc}")

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code != 0:
            LOGGER.error("MQTT connection failed: %s", reason_code)
            return
        self.connected = True
        client.subscribe(self.say_topic, qos=1)
        client.subscribe("qnet/session/+", qos=1)
        self.publish_voice_status("starting")
        LOGGER.info("Connected to IQ9; subscribed to %s and qnet/session/+", self.say_topic)

    def _on_disconnect(self, _client, _userdata, _flags, reason_code, _properties) -> None:
        self.connected = False
        LOGGER.warning("Disconnected from MQTT: %s", reason_code)

    def _on_message(self, _client, _userdata, message) -> None:
        try:
            if message.topic == self.say_topic:
                command = SayCommand.from_payload(message.payload)
                if command.room != self.config.room_id:
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

    def _status_json(self, state: str, voice_state: str) -> str:
        return json.dumps(
            {
                "ts": time.time(),
                "room": self.config.room_id,
                "node_id": self.config.device_id,
                "state": state,
                "voice_state": voice_state,
            },
            separators=(",", ":"),
        )
