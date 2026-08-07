# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""stream - LAN-only camera preview for the dashboard's room modal (DESIGN §17 O14).

Serves the latest frame that ``vision.py`` already exports to
``/dev/shm/qnet_<room>_frame.jpg`` - this process never touches the camera, so
it cannot fight vision for the device, and if vision is down the preview is
honestly stale/absent rather than silently opening a second capture path.

Privacy boundary, stated plainly: the MQTT fabric still carries no media - this
is a separate, user-enabled HTTP endpoint on the workshop LAN (same trust
domain as the unauthenticated broker, DESIGN §4). The dashboard labels it
"Local preview (LAN only)". Don't port-forward it.

Endpoints:
  /<room>.jpg   latest frame, no-cache (the dashboard polls with a cache-buster)
  /             plain index listing the rooms currently exporting frames
"""

from __future__ import annotations

import argparse
import glob
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

FRAME_DIR = Path("/dev/shm")
FRAME_GLOB = "qnet_*_frame.jpg"
ROOM_RE = re.compile(r"^/([a-z0-9_-]+)\.jpg$")


class FrameHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        # Match on the PATH only: every browser consumer cache-busts with a
        # query string ("...jpg?t=1786..."), and matching the raw request
        # target 404'd all of them - curl without a query worked, so the
        # preview appeared broken only in the dashboard (found 2026-08-06).
        path = urlparse(self.path).path
        match = ROOM_RE.match(path)
        if match:
            frame = FRAME_DIR / f"qnet_{match.group(1)}_frame.jpg"
            try:
                data = frame.read_bytes()
            except OSError:
                self.send_error(404, "no frame for that room (is vision running?)")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")  # file:// dashboard
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/" or path == "/index.html":
            rooms = [Path(p).name[len("qnet_"):-len("_frame.jpg")]
                     for p in sorted(glob.glob(str(FRAME_DIR / FRAME_GLOB)))]
            body = ("QNet Home node camera preview (LAN only)\n"
                    + "".join(f"/{room}.jpg\n" for room in rooms)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, *_args) -> None:
        """Polled twice a second by design - default per-request logging would
        drown the journal."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m qnet.node.stream")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--bind", default="0.0.0.0", help="LAN by design; see module docstring")
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.bind, args.port), FrameHandler)
    print(f"stream: serving {FRAME_DIR}/{FRAME_GLOB} on {args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
