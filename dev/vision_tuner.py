# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
"""vision_tuner - an ISOLATED calibration portal for the fall model.

Runs ON a room node beside the production services and touches nothing they
own: frames come from vision.py's existing /dev/shm export (no second camera
client), inference runs with the PORTAL's slider values on its own QnnRunner,
and nothing is ever published to MQTT - production keeps its own floor and
keeps firing (or not) exactly as configured. Close the tab, kill the process,
and no trace remains.

    ~/qnet-venv/bin/python -m dev.vision_tuner --room kitchen --port 8095

Then open http://<board>:8095/ - live feed with prediction overlays, a
confidence-floor slider applied per request, an N-of-M would-fire simulator
computed client-side over the streamed detections, and per-frame class/conf
readouts. One NPU inference per poll (~1/s) rides alongside vision's ~3/s,
the same sharing detwatch used.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from qnet.node.vision import (  # noqa: E402
    CLASSES,
    QnnRunner,
    decode,
    letterbox_params,
    preprocess,
    unletterbox_box,
)

PAGE = """<!doctype html><meta charset="utf-8"><title>QNet fall-model tuner</title>
<style>
 body{font-family:system-ui;margin:0;background:#0f1116;color:#e6e6ef;display:flex;gap:18px;padding:18px}
 #left{position:relative} img{display:block;border-radius:10px;max-width:640px}
 canvas{position:absolute;left:0;top:0;pointer-events:none}
 #panel{min-width:320px;max-width:380px}
 h1{font-size:1.1rem;margin:0 0 6px} .sub{color:#9aa0b0;font-size:.85rem;margin-bottom:14px}
 label{display:block;margin:14px 0 4px;font-size:.9rem} input[type=range]{width:100%}
 .val{font-variant-numeric:tabular-nums;color:#7dd3fc}
 #dets{font-family:ui-monospace,monospace;font-size:.85rem;line-height:1.6;margin-top:12px;
       background:#171a22;border-radius:10px;padding:10px 12px;min-height:80px}
 #fire{margin-top:12px;padding:12px;border-radius:10px;text-align:center;font-weight:700;
       background:#1d212b;transition:background .2s}
 #fire.on{background:#b91c1c}
 .fallen{color:#f87171}.sitting{color:#fbbf24}.standing{color:#4ade80}
 .note{color:#9aa0b0;font-size:.78rem;margin-top:14px;line-height:1.5}
</style>
<div id="left"><img id="feed"><canvas id="ol"></canvas></div>
<div id="panel">
 <h1>Fall-model tuner</h1>
 <div class="sub">Isolated: portal-only parameters, nothing published, production untouched.</div>
 <label>Confidence floor <span class="val" id="floorV">0.35</span></label>
 <input type="range" id="floor" min="0.05" max="0.95" step="0.05" value="0.35">
 <label>Fire rule: fallen in <span class="val" id="nV">5</span> of <span class="val" id="mV">8</span> frames</label>
 <input type="range" id="n" min="1" max="8" step="1" value="5">
 <input type="range" id="m" min="2" max="12" step="1" value="8">
 <div id="fire">would not fire</div>
 <div id="dets">waiting for first inference…</div>
 <div class="note">Feed = the same frame export production uses. Boxes/labels are THIS page's
 inference at YOUR floor. The fire indicator simulates N-of-M over the last M polls (~1/s here vs
 ~3/s in production - directionally right, not tick-exact). Production floor stays whatever
 config/house.yaml says.</div>
</div>
<script>
const $=id=>document.getElementById(id);
let hist=[];
function draw(dets, fw, fh){
  const img=$("feed"), c=$("ol");
  c.width=img.clientWidth; c.height=img.clientHeight;
  const g=c.getContext("2d"); g.clearRect(0,0,c.width,c.height);
  const sx=c.width/fw, sy=c.height/fh;
  const col={fallen:"#f87171",sitting:"#fbbf24",standing:"#4ade80"};
  for(const d of dets){
    g.strokeStyle=col[d.name]||"#ddd"; g.lineWidth=2.5;
    g.strokeRect(d.box[0]*sx,d.box[1]*sy,(d.box[2]-d.box[0])*sx,(d.box[3]-d.box[1])*sy);
    g.fillStyle=col[d.name]||"#ddd"; g.font="600 13px system-ui";
    g.fillText(`${d.name} ${d.conf.toFixed(2)}`, d.box[0]*sx+3, Math.max(12,d.box[1]*sy-4));
  }
}
async function tick(){
  $("feed").src = "/frame.jpg?t=" + Date.now();
  try{
    const r = await fetch("/predict?floor=" + $("floor").value);
    const j = await r.json();
    draw(j.dets, j.w, j.h);
    $("dets").innerHTML = j.dets.length
      ? j.dets.map(d=>`<span class="${d.name}">${d.name}</span> ${d.conf.toFixed(2)}`).join("<br>")
      : "<span style='color:#9aa0b0'>nothing above floor</span>";
    const m=+$("m").value, n=+$("n").value;
    hist.push(j.dets.some(d=>d.name==="fallen")); if(hist.length>m) hist=hist.slice(-m);
    const hits=hist.filter(Boolean).length, would=hits>=n;
    $("fire").textContent = would? `WOULD FIRE (${hits}/${m} fallen)` : `would not fire (${hits}/${m} fallen)`;
    $("fire").className = would? "on":"";
  }catch(e){ $("dets").textContent = "predict error: "+e; }
}
for(const id of ["floor","n","m"]) $(id).oninput=()=>{ $(id+"V").textContent=$(id).value; if(id!=="floor") hist=[]; };
setInterval(tick, 1100); tick();
</script>"""


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m dev.vision_tuner")
    ap.add_argument("--room", default="kitchen")
    ap.add_argument("--port", type=int, default=8095)
    args = ap.parse_args()
    frame_path = Path(f"/dev/shm/qnet_{args.room}_frame.jpg")
    runner = QnnRunner(workdir="/tmp/tuner-qnn")

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/":
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif u.path == "/frame.jpg":
                try:
                    data = frame_path.read_bytes()
                except OSError:
                    self.send_error(404, "no frame (is vision running?)")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            elif u.path == "/predict":
                floor = float((parse_qs(u.query).get("floor") or ["0.35"])[0])
                frame = cv2.imread(str(frame_path))
                if frame is None:
                    self.send_error(404, "no frame")
                    return
                h, w = frame.shape[:2]
                inp, _ = preprocess(frame)
                dets = decode(runner.infer([inp])[0], conf_floor=floor)
                scale, px, py = letterbox_params(w, h)
                out = [
                    {"name": d.name, "conf": round(float(d.conf), 3),
                     "box": [round(v, 1) for v in unletterbox_box(d.box, scale, px, py)]}
                    for d in dets[:8]
                ]
                body = json.dumps({"dets": out, "w": w, "h": h, "ts": time.time()}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, *_a) -> None:
            """Polled every second - keep the console quiet."""

    server = ThreadingHTTPServer(("0.0.0.0", args.port), H)
    print(f"tuner: http://0.0.0.0:{args.port}/ frames={frame_path} (isolated - publishes nothing)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
