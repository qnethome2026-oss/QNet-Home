"""MVP ASR-based wake phrase detection.

This intentionally publishes nothing unless a complete final transcript starts
with one of the explicitly supported QHome wake phrases.
"""

from __future__ import annotations

import re


WAKE_PATTERN = re.compile(
    # Whisper commonly renders a clearly spoken "Hey" as "He". Accept only
    # that narrow ASR variant at the beginning of the final transcript; speech
    # without a home wake phrase remains blocked.
    r"^\s*(?:hey|he)\s*[,.!?-]?\s*(?:q\s*)?home\b[\s,.:;!?-]*(.*?)\s*$",
    re.IGNORECASE,
)


def extract_wake_request(transcript: str) -> str | None:
    if not isinstance(transcript, str):
        return None
    match = WAKE_PATTERN.match(transcript)
    if not match:
        return None
    request = match.group(1).strip()
    return request or None
