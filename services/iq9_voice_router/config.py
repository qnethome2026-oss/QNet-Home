"""Environment configuration for the IQ9 voice router."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    registry_path: str
    history_path: str
    request_topic: str = "qnet/+/ask"

    @classmethod
    def from_env(cls) -> "RouterConfig":
        return cls(
            mqtt_host=os.getenv("QHOME_MQTT_HOST", "mosquitto"),
            mqtt_port=int(os.getenv("QHOME_MQTT_PORT", "1883")),
            mqtt_username=os.getenv("QHOME_MQTT_USERNAME") or None,
            mqtt_password=os.getenv("QHOME_MQTT_PASSWORD") or None,
            registry_path=os.getenv("QHOME_DEVICE_REGISTRY", "/config/home.yaml"),
            history_path=os.getenv("QHOME_HISTORY_PATH", "/data/announcements.jsonl"),
        )
