"""Friendly room, device, and group name resolution for IQ9."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def normalize_name(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").replace("_", " ").split())


@dataclass(frozen=True)
class ResolvedTarget:
    kind: str
    identifier: str | None


class DeviceRegistry:
    def __init__(self, *, devices: dict[str, dict[str, Any]], groups: set[str] | None = None):
        self.devices = devices
        self.alias_to_device: dict[str, str] = {}
        self.alias_to_group: dict[str, str] = {}

        configured_groups = set(groups or set())
        for device_id, config in devices.items():
            aliases = {device_id, config.get("room", ""), *(config.get("aliases") or [])}
            for alias in aliases:
                if alias:
                    self.alias_to_device[normalize_name(str(alias))] = device_id
            for group in config.get("groups") or []:
                configured_groups.add(str(group))

        for group in configured_groups:
            self.alias_to_group[normalize_name(group)] = group

    @classmethod
    def from_file(cls, path: str | Path) -> "DeviceRegistry":
        import yaml

        with Path(path).open("r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        devices = data.get("devices")
        if not isinstance(devices, dict) or not devices:
            raise ValueError("device registry must contain a non-empty devices mapping")
        return cls(devices=devices, groups=set(data.get("groups") or []))

    def resolve(self, hint: str | None) -> ResolvedTarget:
        if hint is None:
            return ResolvedTarget("all", None)

        normalized = normalize_name(hint)
        for suffix in (" device", " speaker", " room"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()

        if normalized in {"all", "all devices", "everywhere", "whole home", "entire home"}:
            return ResolvedTarget("all", None)
        if normalized in self.alias_to_device:
            return ResolvedTarget("device", self.alias_to_device[normalized])
        if normalized in self.alias_to_group:
            return ResolvedTarget("group", self.alias_to_group[normalized])
        raise KeyError(f"unknown target: {hint}")

    def room_for_device(self, device_id: str) -> str:
        try:
            room = self.devices[device_id].get("room")
        except KeyError as exc:
            raise KeyError(f"unknown device: {device_id}") from exc
        if not isinstance(room, str) or not room.strip():
            raise ValueError(f"device {device_id} has no room")
        return room.strip()

    def rooms_for(self, target: ResolvedTarget) -> tuple[str, ...]:
        if target.kind == "all":
            device_ids = self.devices
        elif target.kind == "device" and target.identifier:
            device_ids = (target.identifier,)
        elif target.kind == "group" and target.identifier:
            device_ids = tuple(
                device_id
                for device_id, config in self.devices.items()
                if target.identifier in (config.get("groups") or [])
            )
        else:
            raise ValueError(f"unsupported target: {target}")

        rooms = tuple(sorted({self.room_for_device(device_id) for device_id in device_ids}))
        if not rooms:
            raise ValueError(f"target has no configured rooms: {target.identifier}")
        return rooms

    def topics_for(self, target: ResolvedTarget) -> tuple[str, ...]:
        return tuple(f"qnet/{room}/say" for room in self.rooms_for(target))
