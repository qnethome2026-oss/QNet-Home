# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""Generate the MSIX tile/logo PNGs (T5.3, packaging/).

An MSIX manifest must point at real PNGs or the package will not install, so
these have to exist. They are drawn here in ~40 lines of stdlib (``zlib`` +
``struct`` write a valid PNG) rather than by adding Pillow, because a build-only
image dependency for four flat-colour tiles is not a trade worth making - and
Pillow would then also have to install on whatever machine builds the package.

The mark is the mesh itself: four node dots around one brain dot, joined by
spokes, on the dashboard's own background colour. It is a placeholder in the
sense that a designer would do better, not in the sense that it is a grey box.

    python packaging/make_logo.py dist/QNetHome/Assets
"""

from __future__ import annotations

import math
import struct
import sys
import zlib
from pathlib import Path

BACKGROUND = (0x0B, 0x12, 0x20)  # dashboard chrome navy
BRAIN = (0x4C, 0xC2, 0xFF)  # the "say" blue of the live feed
NODE = (0x8B, 0xE0, 0xC0)  # a calm mint for the leaf nodes
SPOKE = (0x2A, 0x3C, 0x55)  # dim link lines

# What the manifest references. name -> pixel size.
SIZES = {
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
    "StoreLogo.png": 50,
    "Wide310x150Logo.png": (310, 150),
}


def write_png(path: Path, width: int, height: int, pixels: list[list[tuple[int, int, int]]]) -> None:
    """Write a truecolour 8-bit PNG. No filtering (filter byte 0 per scanline)."""
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("3B", *px) for px in row) for row in pixels
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def draw(width: int, height: int) -> list[list[tuple[int, int, int]]]:
    """The mesh mark, centred and scaled to fit whatever tile size is asked for."""
    px = [[BACKGROUND for _ in range(width)] for _ in range(height)]
    cx, cy = (width - 1) / 2, (height - 1) / 2
    span = min(width, height)
    radius = span * 0.30  # how far the node dots sit from the brain
    r_brain = max(1.6, span * 0.10)
    r_node = max(1.0, span * 0.062)
    half_spoke = max(0.5, span * 0.012)

    nodes = [
        (cx + radius * math.cos(a), cy + radius * math.sin(a))
        for a in (math.radians(d) for d in (-90, -18, 54, 126, 198))
    ]

    def blend(x: int, y: int, colour: tuple[int, int, int], coverage: float) -> None:
        if coverage <= 0:
            return
        cov = min(1.0, coverage)
        base = px[y][x]
        px[y][x] = tuple(round(b + (c - b) * cov) for b, c in zip(base, colour))  # type: ignore[assignment]

    for y in range(height):
        for x in range(width):
            # Spokes first so the dots draw over them.
            for nx, ny in nodes:
                dx, dy = nx - cx, ny - cy
                length = math.hypot(dx, dy) or 1.0
                t = ((x - cx) * dx + (y - cy) * dy) / (length * length)
                if 0.0 <= t <= 1.0:
                    px_, py_ = cx + dx * t, cy + dy * t
                    blend(x, y, SPOKE, half_spoke + 0.5 - math.hypot(x - px_, y - py_))
            for nx, ny in nodes:
                blend(x, y, NODE, r_node + 0.5 - math.hypot(x - nx, y - ny))
            blend(x, y, BRAIN, r_brain + 0.5 - math.hypot(x - cx, y - cy))
    return px


def main(argv: list[str]) -> int:
    out = Path(argv[1] if len(argv) > 1 else "dist/QNetHome/Assets")
    out.mkdir(parents=True, exist_ok=True)
    for name, size in SIZES.items():
        w, h = size if isinstance(size, tuple) else (size, size)
        path = out / name
        write_png(path, w, h, draw(w, h))
        print(f"  wrote {path} ({w}x{h}, {path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
