"""MQTT process that routes room-scoped asks to room-scoped speech topics."""

from __future__ import annotations

import logging
import json

import paho.mqtt.client as mqtt

from .config import RouterConfig
from .device_registry import DeviceRegistry
from .message_store import MessageStore
from .router import RouteError, VoiceRouter
from .schemas import MessageValidationError, VoiceRequest


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("qnet.iq9.voice-router")


def main() -> None:
    config = RouterConfig.from_env()
    registry = DeviceRegistry.from_file(config.registry_path)
    router = VoiceRouter(registry, MessageStore(config.history_path))
    safety_rooms: set[str] = set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qnet-iq9-voice-router")
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)

    def on_connect(_client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code != 0:
            LOGGER.error("MQTT connection failed: %s", reason_code)
            return
        LOGGER.info("Connected to MQTT broker at %s:%s", config.mqtt_host, config.mqtt_port)
        _client.subscribe(config.request_topic, qos=1)
        _client.subscribe("qnet/session/+", qos=1)

    def on_message(_client, _userdata, message) -> None:
        request_id = "unknown"
        try:
            if message.topic.startswith("qnet/session/"):
                session = json.loads(message.payload)
                if not isinstance(session, dict):
                    raise MessageValidationError("session payload must be an object")
                if session.get("urgency") == "safety" and isinstance(session.get("room"), str):
                    if session.get("state") == "active":
                        safety_rooms.add(session["room"])
                    else:
                        safety_rooms.discard(session["room"])
                return
            request = VoiceRequest.from_payload(message.payload)
            request_id = request.message_id
            topic_parts = message.topic.split("/")
            if len(topic_parts) != 3 or topic_parts[0] != "qnet" or topic_parts[2] != "ask":
                raise MessageValidationError("ask arrived on an invalid topic")
            if request.room != topic_parts[1]:
                raise MessageValidationError("ask payload room does not match topic room")
            if request.kind == "query" and request.room in safety_rooms:
                LOGGER.info("Ignored query %s while safety session owns %s", request.message_id, request.room)
                return
            result = router.route(request)
            for publication in result.publications:
                publish = _client.publish(
                    publication.topic, publication.command.to_json(), qos=1, retain=False
                )
                if publish.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise RuntimeError(
                        f"MQTT publish to {publication.topic} failed with rc={publish.rc}"
                    )
            LOGGER.info("Routed %s from %s to %s", request.message_id, request.room, result.topics)
        except (MessageValidationError, RouteError, RuntimeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Rejected voice request %s: %s", request_id, exc)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.mqtt_host, config.mqtt_port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
