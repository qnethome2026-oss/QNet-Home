# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hermetic tests for the experimental IM SDK vision engine (T8.1).

Laptop-runnable: no gst, no cv2, no NPU - only the pure pieces (pipe framing,
tensor conversion, pipeline construction). The on-board behaviour is gated by
verify/T-imsdk-fall.txt stages instead.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from qnet.node.vision_imsdk import (
    FRAME_BYTES,
    IMSDK_CONF_FLOOR,
    frames_from_fd,
    gst_command,
    gst_source,
    tensor_from_frame,
)


def _fd_from(data: bytes) -> int:
    # A real file, not os.pipe(): writing a 1.2 MB frame into a pipe with no
    # reader deadlocks on the OS pipe buffer (Windows: ~8 KB). os.read works
    # the same on a file fd, which is all frames_from_fd needs.
    f = tempfile.TemporaryFile()
    f.write(data)
    f.seek(0)
    fd = os.dup(f.fileno())
    f.close()
    return fd


def test_frames_from_fd_chunks_exactly():
    frames = [bytes([i]) * FRAME_BYTES for i in range(3)]
    fd = _fd_from(b"".join(frames))
    assert list(frames_from_fd(fd)) == frames
    os.close(fd)


def test_frames_from_fd_drops_short_tail():
    fd = _fd_from(b"\x01" * FRAME_BYTES + b"\x02" * 100)  # torn final frame
    out = list(frames_from_fd(fd))
    assert out == [b"\x01" * FRAME_BYTES]
    os.close(fd)


def test_frames_from_fd_empty_is_eof():
    fd = _fd_from(b"")
    assert list(frames_from_fd(fd)) == []
    os.close(fd)


def test_tensor_from_frame_layout_and_scale():
    # A frame whose R plane is 255, G is 51, B is 0 - checks channel order,
    # HWC->CHW transpose and /255 scaling in one shot.
    hwc = np.zeros((640, 640, 3), dtype=np.uint8)
    hwc[:, :, 0] = 255
    hwc[:, :, 1] = 51
    t = tensor_from_frame(hwc.tobytes())
    assert t.shape == (1, 3, 640, 640) and t.dtype == np.float32
    assert t[0, 0].min() == t[0, 0].max() == 1.0
    assert abs(float(t[0, 1, 0, 0]) - 51 / 255) < 1e-6
    assert t[0, 2].max() == 0.0
    assert t.flags["C_CONTIGUOUS"]


def test_gst_source_spellings():
    assert gst_source("v4l2src device=/dev/v4l/by-id/cam-video-index0") == \
        "v4l2src device=/dev/v4l/by-id/cam-video-index0 ! decodebin ! videoconvert"
    # files get the explicit hardware H.264 chain (see gst_source docstring)
    assert gst_source("filesrc location=clips/fall01.mp4 ! decodebin") == \
        "filesrc location=clips/fall01.mp4 ! qtdemux ! h264parse ! v4l2h264dec"
    assert gst_source("/dev/video3").startswith("v4l2src device=/dev/video3")
    assert gst_source("clips/fall01.mp4").startswith("filesrc location=clips/fall01.mp4")
    # /dev/shm holds CLIP files, not device nodes - regression for a live bug
    assert gst_source("/dev/shm/fall01.mp4").startswith("filesrc location=/dev/shm/fall01.mp4")


def test_gst_command_wires_fd_and_preview():
    cmd = gst_command("clips/x.mp4", 7, "/dev/shm/prev.jpg")
    assert cmd[0] == "gst-launch-1.0" and "-q" in cmd  # -q: stdout stays clean
    assert "fd=7" in cmd
    assert "location=/dev/shm/prev.jpg" in cmd
    assert any("type=UINT8" in part for part in cmd)  # the proven converter path
    assert "image-disposition=centre" in cmd  # aspect-preserving letterbox


def test_imsdk_floor_is_documented_offset():
    # 0.45 compensates the measured ~0.04 systematic preproc delta vs
    # mainline's 0.5 (Stage 2 parity, verify/T-imsdk-fall.txt). If this
    # changes, re-run the parity clips before shipping.
    assert IMSDK_CONF_FLOOR == pytest.approx(0.45)
