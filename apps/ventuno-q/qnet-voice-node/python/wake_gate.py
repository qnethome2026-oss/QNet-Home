# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""ASR-based wake phrase detection over the rolling transcript window.

Nothing leaves the node unless the wake phrase appears in the window and a
command follows it. Detection runs over the *rolling* text (the buffer exists
because Whisper can split "Hey Home" across partial/final events), but only
the remainder AFTER the wake phrase is ever returned - background speech
before the phrase stays on the device (DESIGN §9 R5).
"""

from __future__ import annotations

import re


DEFAULT_WAKE_PHRASE = "hey home"


def compile_wake_pattern(phrase: str = DEFAULT_WAKE_PHRASE) -> re.Pattern[str]:
    """Build the detection regex for a configurable wake phrase.

    Two ASR tolerances are preserved for any phrase: Whisper commonly renders
    a clearly spoken "Hey" as "He", so a leading "hey" also accepts "he"; and
    an optional "q" is allowed before the final word so "hey q home" (or a
    run-together "q home" rendering) still wakes the default phrase.
    """
    words = [word for word in phrase.lower().split() if word]
    if not words:
        raise ValueError("wake phrase cannot be empty")
    parts = []
    for index, word in enumerate(words):
        piece = "(?:hey|he)" if word == "hey" else re.escape(word)
        if index == len(words) - 1 and len(words) > 1:
            piece = r"(?:q\s*)?" + piece
        parts.append(piece)
    body = r"\s*[,.!?-]?\s*".join(parts)
    # \b instead of ^: the phrase may sit mid-window after background speech
    # ("News is playing. Hey Home, ..."); the capture starts after it.
    return re.compile(rf"\b{body}\b[\s,.:;!?-]*(.*?)\s*$", re.IGNORECASE)


WAKE_PATTERN = compile_wake_pattern()


def extract_wake_request(transcript: str, pattern: re.Pattern[str] | None = None) -> str | None:
    """The command after the wake phrase, or None - never the full transcript."""
    if not isinstance(transcript, str):
        return None
    match = (pattern or WAKE_PATTERN).search(transcript)
    if not match:
        return None
    # Trailing punctuation is transcription noise, not command content - the
    # frozen ask fixture carries "where are my glasses", not "... glasses?".
    request = re.sub(r"[\s,.:;!?-]+$", "", match.group(1).strip())
    return request or None
