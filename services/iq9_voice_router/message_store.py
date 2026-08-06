"""Small persistent history used by the 'play last broadcast' command."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .schemas import SayCommand


@dataclass(frozen=True)
class StoredAnnouncement:
    message_id: str
    timestamp: float
    text: str


class MessageStore:
    def __init__(self, path: str | Path | None = None, max_messages: int = 50):
        self.path = Path(path) if path else None
        self.messages: deque[StoredAnnouncement] = deque(maxlen=max_messages)
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                data = json.loads(line)
                self.messages.append(
                    StoredAnnouncement(str(data["id"]), float(data["ts"]), str(data["text"]))
                )
            except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                continue

    def add(self, command: SayCommand) -> None:
        stored = StoredAnnouncement(command.message_id, command.timestamp, command.text)
        self.messages.append(stored)
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            data = {"id": stored.message_id, "ts": stored.timestamp, "text": stored.text}
            stream.write(json.dumps(data, separators=(",", ":")) + "\n")

    def last(self) -> StoredAnnouncement | None:
        return self.messages[-1] if self.messages else None
