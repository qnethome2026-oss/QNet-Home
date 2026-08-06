from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NODE_PYTHON = REPO_ROOT / "apps/ventuno-q/qhome-voice-node/python"
sys.path.insert(0, str(NODE_PYTHON))

from transcript_buffer import RollingTranscriptBuffer  # noqa: E402


def test_buffer_keeps_recent_vad_finals_and_expires_old_context() -> None:
    now = [0.0]
    buffer = RollingTranscriptBuffer(10, clock=lambda: now[0])
    assert buffer.add_final("News is playing.") == "News is playing."
    now[0] = 4
    assert buffer.add_final("Hey Home, where are my spectacles?") == (
        "News is playing. Hey Home, where are my spectacles?"
    )
    now[0] = 11
    assert buffer.add_final("Are they in the bedroom?") == (
        "Hey Home, where are my spectacles? Are they in the bedroom?"
    )


def test_buffer_merges_overlapping_partial_and_final() -> None:
    buffer = RollingTranscriptBuffer()
    buffer.add_partial("Hey Home, where are")
    assert buffer.add_final("where are my glasses?") == "Hey Home, where are my glasses?"


def test_buffer_remembers_wake_phrase_from_an_early_replaced_partial() -> None:
    buffer = RollingTranscriptBuffer()
    buffer.add_partial("Hey Home, where are")
    buffer.add_partial("Where are my spectacles")
    assert buffer.add_final("Where are my spectacles?") == (
        "Hey Home, where are my spectacles?"
    )


def test_buffer_is_cleared_across_tts_boundary() -> None:
    buffer = RollingTranscriptBuffer()
    buffer.add_final("Hey Home, tell me something")
    buffer.clear()
    assert buffer.add_final("new user speech") == "new user speech"
