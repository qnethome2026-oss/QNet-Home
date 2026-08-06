# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""The vision node's pure logic - decode, N-of-M window, re-arm - off-device (T4.2).

No camera, no NPU, no cv2: the decode tests run against raw ``(1, 7, 8400)``
output tensors recorded from the real Hexagon NPU on the Ventuno Q
(``tests/fixtures/fix_*.npz``, from UR Fall dataset frames - real footage, real
silicon), so what is asserted here is the exact decode path the board runs, fed
by the exact bytes the board produced. The gate tests drive the temporal state
machine frame by frame with a fake clock. Everything needs numpy alone.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qnet.node.vision import (
    CLS_FALLEN,
    FallGate,
    classify_frame,
    decode,
    letterbox_params,
    nms,
    parse_source,
    unletterbox_box,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name: str):
    return np.load(FIXTURES / name)


# --- decode, against tensors the real NPU produced -------------------------


def test_decode_fallen_fixture():
    """A person on the floor (UR Fall fall-02 frame 100) decodes as fallen."""
    fix = fixture("fix_fallen.npz")
    dets = decode(fix["output"], conf_floor=0.5)
    fallen = [d for d in dets if d.cls == CLS_FALLEN]
    assert fallen, f"expected a fallen detection, got {[(d.name, d.conf) for d in dets]}"
    best = max(fallen, key=lambda d: d.conf)
    assert best.conf > 0.9
    # Plausible geometry: inside the 640 canvas, in the letterboxed image band,
    # person-sized - not a sliver, not the whole frame.
    x1, y1, x2, y2 = best.box
    assert 0 <= x1 < x2 <= 640 and 0 <= y1 < y2 <= 640
    assert 50 < (x2 - x1) < 500 and 50 < (y2 - y1) < 500


def test_decode_standing_fixture():
    """An upright person (UR Fall fall-01 frame 60) is standing, never fallen."""
    fix = fixture("fix_standing.npz")
    dets = decode(fix["output"], conf_floor=0.5)
    names = {d.name for d in dets}
    assert "standing" in names
    assert not any(d.cls == CLS_FALLEN for d in dets)


def test_decode_respects_conf_floor():
    fix = fixture("fix_fallen.npz")
    assert decode(fix["output"], conf_floor=0.99) == []
    assert len(decode(fix["output"], conf_floor=0.3)) >= len(decode(fix["output"], conf_floor=0.6))


def test_classify_frame_verdicts():
    fallen = decode(fixture("fix_fallen.npz")["output"], conf_floor=0.5)
    standing = decode(fixture("fix_standing.npz")["output"], conf_floor=0.5)
    conf, upright = classify_frame(fallen)
    assert conf is not None and conf > 0.9 and not upright  # fallen wins over the chair's "sitting"
    conf, upright = classify_frame(standing)
    assert conf is None and upright
    assert classify_frame([]) == (None, False)  # empty room: neither fallen nor upright


# --- NMS + letterbox, synthetic --------------------------------------------


def test_nms_suppresses_same_object():
    boxes = np.array([[100, 100, 200, 200], [105, 105, 205, 205], [400, 400, 500, 500]], dtype=np.float32)
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    keep = nms(boxes, scores, iou_floor=0.45)
    assert 0 in keep and 2 in keep and 1 not in keep  # near-duplicate loses to the stronger box


def test_decode_nms_is_class_aware():
    """Two overlapping candidates of different classes both survive."""
    raw = np.zeros((1, 7, 8400), dtype=np.float32)
    raw[0, :4, 0] = [320, 320, 100, 200]  # cx, cy, w, h
    raw[0, 4, 0] = 0.9  # fallen
    raw[0, :4, 1] = [325, 325, 100, 200]
    raw[0, 6, 1] = 0.8  # standing, same spot
    dets = decode(raw, conf_floor=0.5)
    assert {d.name for d in dets} == {"fallen", "standing"}


def test_letterbox_roundtrip():
    scale, pad_x, pad_y = letterbox_params(320, 240, 640)
    assert (scale, pad_x, pad_y) == (2.0, 0, 80)  # 320x240 -> 640x480, centred vertically
    box = (100.0, 180.0, 300.0, 400.0)
    x1, y1, x2, y2 = unletterbox_box(box, scale, pad_x, pad_y)
    assert (x1, y1, x2, y2) == (50.0, 50.0, 150.0, 160.0)


def test_parse_source_spellings():
    assert parse_source("v4l2src device=/dev/video0") == "/dev/video0"
    assert parse_source("filesrc location=clips/fall01.mp4 ! decodebin") == "clips/fall01.mp4"
    assert parse_source("2") == 2
    assert parse_source("clips/fall01.mp4") == "clips/fall01.mp4"


# --- the temporal gate: 5-of-8, fire-once, re-arm --------------------------


def gate(**kw) -> FallGate:
    kw.setdefault("n", 5)
    kw.setdefault("m", 8)
    kw.setdefault("rearm_after_s", 60.0)
    kw.setdefault("rearm_frames", 8)
    return FallGate(**kw)


def feed(g: FallGate, seq, t0: float = 0.0, dt: float = 0.5):
    """Drive the gate with 'F' (fallen 0.8), 'U' (upright), '.' (nothing) frames."""
    fired = []
    for i, ch in enumerate(seq):
        conf = 0.8 if ch == "F" else None
        result = g.update(conf, upright=(ch == "U"), now=t0 + i * dt)
        if result:
            fired.append((i, result))
    return fired


def test_fires_on_5_of_8_not_before():
    g = gate()
    # 4 fallen among the last 8: never fires. The 5th fallen fires, exactly once.
    assert feed(g, "...FFFF") == []
    fired = feed(g, "F", t0=4.0)
    assert len(fired) == 1
    assert fired[0][1].frames == "5/8"


def test_flicker_does_not_fire():
    """The single-frame flicker DESIGN §8 exists to remove: 4-of-8 max."""
    assert feed(gate(), "F..F..F..F..F..F..") == []


def test_fire_once_while_they_stay_down():
    """A fallen person keeps matching; the event must not repeat (§8)."""
    fired = feed(gate(), "F" * 100)  # 50 s of continuous fallen frames
    assert len(fired) == 1
    assert fired[0][0] == 4  # the 5th frame


def test_conf_is_median_of_window():
    g = gate()
    confs = [0.9, 0.7, 0.8, 0.6, 0.85]
    fired = [g.update(c, upright=False, now=i * 0.5) for i, c in enumerate(confs)]
    assert fired[:4] == [None] * 4
    assert fired[4].conf == pytest.approx(0.8)  # median, not max, not last


def test_rearm_after_upright_frames_then_second_fall():
    """fall -> recover (8 upright frames) -> fall = two events (the re-arm rule)."""
    g = gate()
    first = feed(g, "F" * 8)
    assert len(first) == 1
    assert feed(g, "U" * 7, t0=10.0) == []  # 7 upright: still in holdoff
    assert g.state == "holdoff"
    assert feed(g, "U", t0=20.0) == []  # 8th consecutive upright re-arms
    assert g.state == "armed"
    second = feed(g, "F" * 8, t0=30.0)
    assert len(second) == 1  # fresh evidence, fresh event


def test_upright_streak_resets_on_fallen_frame():
    g = gate()
    feed(g, "F" * 8)
    # 7 upright, one fallen, 7 upright: the streak never reaches 8.
    assert feed(g, "U" * 7 + "F" + "U" * 7, t0=10.0) == []
    assert g.state == "holdoff"


def test_rearm_after_cooldown_even_if_still_down():
    """§8: armed-but-quiet until upright OR the cooldown - a person still on
    the floor after 60 s produces a fresh (reminder) event."""
    g = gate(rearm_after_s=60.0)
    fired = feed(g, "F" * 20)  # fires at frame 4, holdoff through frame 19
    assert len(fired) == 1
    # 61 s later, still fallen: window restarts clean, fires on the 5th frame.
    fired = feed(g, "F" * 8, t0=100.0)
    assert len(fired) == 1
    assert fired[0][0] == 4


def test_window_cleared_on_rearm():
    """Old fallen frames must not count toward a new event."""
    g = gate()
    feed(g, "F" * 8)
    feed(g, "U" * 8, t0=10.0)  # re-arms
    assert feed(g, "F" * 4, t0=20.0) == []  # 4 fresh fallen: not enough alone


def test_gate_rejects_bad_rule():
    with pytest.raises(ValueError):
        FallGate(n=9, m=8)
