# QNet Home
# Copyright (C) 2026 QNet Home contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any


class FakeMQTTTransport:
    """Records node publications without opening a network connection."""

    def __init__(self):
        self.connected = True
        self.queries: list[str] = []
        self.responder_briefs = 0
        self.heard: list[dict[str, Any]] = []
        self.statuses: list[dict[str, Any]] = []

    def publish_query(self, text: str) -> str:
        self.queries.append(text)
        return f"fake-query-{len(self.queries)}"

    def publish_request(self, text: str) -> str:
        return self.publish_query(text)

    def publish_responder_brief(self) -> str:
        self.responder_briefs += 1
        return f"fake-responder-{self.responder_briefs}"

    def publish_heard(self, *, text: str, silence: bool) -> str:
        self.heard.append({"text": text, "silence": silence})
        return f"fake-heard-{len(self.heard)}"

    def publish_voice_status(self, voice_state: str, **kwargs: Any) -> None:
        self.statuses.append({"voice_state": voice_state, **kwargs})
