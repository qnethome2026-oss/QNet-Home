"""Deterministic MVP voice-command routing for announcements."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .device_registry import DeviceRegistry, ResolvedTarget
from .message_store import MessageStore
from .schemas import SayCommand, VoiceRequest


class RouteError(ValueError):
    """A valid ask did not match an allowed announcement command."""


@dataclass(frozen=True)
class RoutePublication:
    topic: str
    command: SayCommand


@dataclass(frozen=True)
class RouteResult:
    publications: tuple[RoutePublication, ...]
    replay: bool = False

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(publication.topic for publication in self.publications)


class VoiceRouter:
    def __init__(self, registry: DeviceRegistry, store: MessageStore | None = None):
        self.registry = registry
        self.store = store or MessageStore()

    def route(self, request: VoiceRequest) -> RouteResult:
        if request.kind != "query":
            raise RouteError("responder_brief is handled by the Phase-2 agent, not the voice router")

        text = " ".join(request.text.strip().split())
        lowered = text.lower().rstrip(" .?!")

        replay_match = re.fullmatch(
            r"(?:play|repeat) (?:the )?last (?:broadcast|announcement)"
            r"(?: (?:on|in|to) (?:the )?(.+?))?",
            lowered,
        )
        if replay_match:
            previous = self.store.last()
            if previous is None:
                raise RouteError("there is no previous announcement to replay")
            target = self._resolve_target(replay_match.group(1), default_room=request.room)
            return RouteResult(self._publications(request, target, previous.text), replay=True)

        if lowered.startswith("broadcast"):
            target, message = self._parse_announcement(text[len("broadcast") :], default_all=True)
        elif lowered.startswith("announce"):
            target, message = self._parse_announcement(text[len("announce") :], default_all=False)
        else:
            raise RouteError("request is not a broadcast, announcement, or replay command")

        publications = self._publications(request, target, message)
        self.store.add(publications[0].command)
        return RouteResult(publications)

    def _publications(
        self, request: VoiceRequest, target: ResolvedTarget, text: str
    ) -> tuple[RoutePublication, ...]:
        return tuple(
            RoutePublication(
                f"qnet/{room}/say",
                SayCommand.create(request=request, room=room, text=text, priority="comfort"),
            )
            for room in self.registry.rooms_for(target)
        )

    def _parse_announcement(self, remainder: str, *, default_all: bool) -> tuple[ResolvedTarget, str]:
        remainder = remainder.strip(" ,")
        lowered = remainder.lower()

        if lowered.startswith("that "):
            return ResolvedTarget("all", None), remainder[5:].strip()

        separator = lowered.find(" that ")
        if separator >= 0:
            target_phrase = remainder[:separator].strip()
            message = remainder[separator + 6 :].strip()
            target_phrase = re.sub(r"^(?:on|in|to) (?:the )?", "", target_phrase, flags=re.IGNORECASE)
            target = self._resolve_target(target_phrase)
            return target, self._require_message(message)

        if default_all:
            return ResolvedTarget("all", None), self._require_message(remainder)
        raise RouteError("targeted announcements must use 'that' before the message")

    def _resolve_target(self, hint: str | None, default_room: str | None = None) -> ResolvedTarget:
        if hint is None and default_room:
            try:
                return self.registry.resolve(default_room)
            except KeyError as exc:
                raise RouteError(str(exc)) from exc
        try:
            return self.registry.resolve(hint)
        except KeyError as exc:
            raise RouteError(str(exc)) from exc

    @staticmethod
    def _require_message(message: str) -> str:
        message = message.strip(" ,")
        if not message:
            raise RouteError("announcement message is empty")
        return message
