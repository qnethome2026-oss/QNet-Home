"""Short rolling ASR context that preserves wake words lost at VAD boundaries."""

from __future__ import annotations

import re
import time
from collections import deque
from typing import Callable


class RollingTranscriptBuffer:
    def __init__(
        self,
        window_seconds: float = 10,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.window_seconds = window_seconds
        self.clock = clock
        self._finals: deque[tuple[float, str]] = deque()
        self._partial = ""
        self._wake_partial = ""

    def add_partial(self, text: str) -> None:
        self._partial = text.strip()
        # Whisper partials are revisions, not guaranteed cumulative strings.
        # Once a partial contains the wake phrase, retain the strongest such
        # revision even when later partials replace it with command-only text.
        if self._has_wake_hint(self._partial) and len(self._partial) > len(self._wake_partial):
            self._wake_partial = self._partial

    def add_final(self, text: str) -> str:
        now = self.clock()
        final = self._merge_partial(self._partial, text.strip())
        if self._wake_partial and not self._has_wake_hint(final):
            final = self._merge_partial(self._wake_partial, final)
        self._partial = ""
        self._wake_partial = ""
        self._prune(now)
        if final and (not self._finals or self._normalize(self._finals[-1][1]) != self._normalize(final)):
            self._finals.append((now, final))
        return " ".join(item for _, item in self._finals).strip()

    def clear(self) -> None:
        self._finals.clear()
        self._partial = ""
        self._wake_partial = ""

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._finals and self._finals[0][0] < cutoff:
            self._finals.popleft()

    @classmethod
    def _merge_partial(cls, partial: str, final: str) -> str:
        if not partial:
            return final
        if not final:
            return partial
        partial_words = partial.split()
        final_words = final.split()
        partial_norm = [cls._normalize(word) for word in partial_words]
        final_norm = [cls._normalize(word) for word in final_words]

        if " ".join(partial_norm) in " ".join(final_norm):
            return final
        if " ".join(final_norm) in " ".join(partial_norm):
            return partial

        for overlap in range(min(len(partial_words), len(final_words)), 0, -1):
            if partial_norm[-overlap:] == final_norm[:overlap]:
                return " ".join(partial_words + final_words[overlap:])

        # Whisper can drop a short wake phrase from its final event even after
        # emitting it in a partial. Preserve that evidence for the IQ9 LLM.
        if cls._has_wake_hint(partial) and not cls._has_wake_hint(final):
            return f"{partial} {final}".strip()
        return final

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _has_wake_hint(value: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        return bool(re.search(r"\b(?:hey|he)\s+(?:q\s*)?home\b", normalized))
