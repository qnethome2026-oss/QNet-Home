# IM SDK fall-detection engine (EXPERIMENTAL, feature-flagged — T8.1)

An alternative engine for kitchen fall detection that moves the **front half**
of the pipeline — camera/clip capture, hardware decode, letterbox resize,
dashboard preview export — into a [Qualcomm IM SDK](https://imsdkdocs.qualcomm.com/)
GStreamer pipeline, while everything from the NPU call onward stays
byte-for-byte the mainline path (`qnn-net-run` → numpy decode → `FallGate` →
the frozen MQTT contract).

**This is not the demo path.** It ships disabled, swaps in only via the flag
below, and mainline (`qnet-vision.service`) is what every default bring-up
restores. It exists because it removes the per-batch process-spawn overhead
of `qnn-net-run` from the capture side, replaces our flakiest interface
(`cv2.VideoCapture`) with `v4l2src`, and proves the official IM SDK plugin
path on this board — with the full investigation recorded so the next step
(the all-GStreamer pipeline) starts from evidence.

## Enable / disable

| Action | Command |
|---|---|
| Deploy (installs, enables **nothing**) | `sh scripts/deploy_vision_imsdk.sh ventuno` |
| Switch the house to the experimental engine | `bash scripts/bring_up.sh --imsdk` |
| Switch back to mainline | `bash scripts/bring_up.sh` (every default run asserts mainline — a forgotten experiment cannot survive a bring-up) |
| Manual toggle, on the board | `sudo systemctl disable --now qnet-vision && sudo systemctl enable --now qnet-vision-imsdk` (reverse to go back) |
| Which engine is running? | The heartbeat says so: `detector: fall-yolo11n@imsdk-gst` vs `fall-yolo11n@hexagon-npu`; events carry `meta.engine: "imsdk"` |

Both units carry `Conflicts=` on each other — both open the same camera, so
**systemd itself guarantees only one engine ever runs**.

## Architecture

```
IM SDK / GStreamer                              Python (mainline logic, imported)
v4l2src <by-id> ! decodebin ! videoconvert      read 1,228,800-byte frames off the pipe
  (camera)  — or —                              → float32/255 + HWC→CHW   (~2 ms)
filesrc ! qtdemux ! h264parse ! v4l2h264dec     → QnnRunner (qnn-net-run, best.bin, HTP)
  (clips: H.264 only — see Limitations)         → decode() + classify_frame()
 ! NV12 ! tee                                   → FallGate 5-of-8, fire-once
   ├─ qtimlvconverter image-disposition=centre  → qnet/<room>/event  (QoS 1)
   │   ! UINT8 (1,640,640,3) ! fdsink ────────►   + status heartbeats
   └─ jpegenc ! multifilesink (preview .jpg,      + /dev/shm frame mirror
        os.replace'd onto the canonical path)
```

Module: [`qnet/node/vision_imsdk.py`](../../qnet/node/vision_imsdk.py) ·
unit: [`infra/systemd/qnet-vision-imsdk.service`](../../infra/systemd/qnet-vision-imsdk.service) ·
tests: [`tests/test_vision_imsdk.py`](../../tests/test_vision_imsdk.py) ·
evidence: [`verify/T-imsdk-fall.txt`](../../verify/T-imsdk-fall.txt).

### The confidence floor is 0.45, not 0.5 — measured, not arbitrary

The IM SDK preprocessing reads systematically **~0.03–0.05 lower** fallen
confidences than mainline's (pad-0 vs pad-114 letterbox fill, NV12 chroma
subsampling, a different scaler). At mainline's 0.5 floor one borderline
detection dropped out and a gate fire was lost; at **0.45 the engine
reproduces mainline's gate fires exactly** on both regression clips
(fall-01: fires at frames 4+104 both engines; adl-01: exactly one fire both
engines; per-frame verdict agreement 134/160 and 147/150). If you change
either floor, re-run the Stage 2 parity script before trusting the gate.

The **live** calibration is a different pair: mainline runs 0.8 + 6-of-6
(DESIGN §8's calibrated values), so the shipped unit passes `--conf 0.76
--fire-on 6/6` — the same −0.04 correction **extrapolated** to the live
floor. That extrapolation has not been validated on a live camera yet; do
that (side-by-side with mainline on the same scene) before showing this
engine to anyone.

## Why the front half only — the converter findings (2026-08-07)

The obvious design — the full documented pipeline
(`qtimlvconverter ! qtimlqnn ! qtimlpostprocess`) driving our existing QNN
context binary — **fails on this board's host build**, and the reason is
narrow and precisely mapped:

| `qtimlvconverter` output path | Result on the Ventuno host build |
|---|---|
| UINT8, NHWC interleaved — what every stock (quantized tflite) IM SDK model requests | ✅ **works** (920k+ nonzero bytes/frame, unique per frame) |
| FLOAT32, NCHW planar — what our ONNX-lineage `.bin` requests | ❌ silently emits **all-zero tensors**: the GLES engine can't get a GPU context headless (xcb failure, also zero under root+Wayland and surfaceless EGL); `engine=ocv` doesn't implement any→RGBP and **segfaults** on float NHWC; `engine=fcv` isn't compiled in (`assertion 'engine != NULL'`) |

Proof chain: filesink dumps directly off the converter (all-zero for a solid
red frame and for 160 real video frames — 1 unique MD5), corroborated by 160
byte-identical NPU outputs on a moving clip. Meanwhile `qtimlqnn` loads and
runs `best.bin` on the HTP correctly, and `qtimlpostprocess module=yolov8`
explicitly supports our raw `(1,7,8400)` head (`gst-inspect` tensor spec
`1, 5-1005, 21-42840`). Two of three stages fine; the input stage can only
cook the uint8/NHWC recipe — so this engine orders exactly that dish and does
the two remaining steps (float cast + transpose) in numpy.

Also ruled out, for the record:
- **The qimsdk docker container** (the colleague's `qnet-imsdk-face` route):
  no `gst-launch`, no camera support on Ubuntu per the docs (hence RTSP
  side-cars), and headless waylandsink failures. The host apt plugins
  (`gstreamer1.0-plugins-qcom-ml*`) made it unnecessary.
- **Pipeline structure quirks** (also cost real debugging): a software
  `videoconvert` between `v4l2h264dec` and the tee breaks negotiation against
  the decoder's DMA buffers (qtdemux `reason error (-5)`), and plain
  `decodebin ! NV12` fails the same way — files must use the explicit
  `qtdemux ! h264parse ! v4l2h264dec` chain with caps straight off the
  decoder. `gst-launch` status chatter goes to stdout, so tensors travel on a
  dedicated pipe fd, never fd 1.

## The road to the full pipeline (post-hackathon)

The blocker is purely the **model artifact's declared input format**. Options,
best first:

1. **Float TFLite re-export** (2-minute local job, no AI Hub):
   `YOLO("best.pt").export(format="tflite", imgsz=640)` → float32 NHWC →
   under `qtimltflite` with the QNN delegate (`backend_type=htp` — float runs
   as native FP16 on HTP v75, same execution our current `.bin` gets) or
   `delegate=gpu` (the docs' float recipe). Requires the converter's
   float-NHWC path, which is doc-sanctioned but **not yet probed** on this
   build — probe first, one command, pattern in the table above.
2. **Quantized TFLite (w8a8, uint8 NHWC)** — rides the *proven* converter
   path; the exact stock-model recipe; needs a calibration set and an
   accuracy parity check.
3. **FP32 QNN context binary with channel-last input** (AI Hub compile with
   `--force_channel_last_input images`; do NOT channel-last the output —
   `(1,8400,7)` falls outside the yolov8 postproc envelope). Keeps `qtimlqnn`.

With any of those, the tail becomes IM SDK too: `qtimlpostprocess
module=yolov8 labels=fall_labels.json` (template in this folder) emitting
`ObjectDetection` structures, and optionally `qtimsgpub`
(`gstreamer1.0-plugins-qcom-msgbroker`, libmosquitto-based) publishing raw
per-frame detections to MQTT — **plus a small adapter** that applies the
FallGate temporal rule and emits the contract `fall.detected` event; the
gate semantics cannot live in GStreamer.

## Limitations (current, honest)

- **Clip sources must be H.264 mp4** (hardware-decode chain). Transcode
  anything on the board: `gst-launch-1.0 filesrc location=in.mp4 ! decodebin
  ! videoconvert ! video/x-raw,format=NV12 ! v4l2h264enc ! h264parse !
  mp4mux ! filesink location=out.mp4` (~0.2 s per clip).
- **The live-camera chain (`v4l2src ! decodebin ! videoconvert`) is
  code-complete but not yet live-tested** — verification ran on a board with
  no camera attached. First camera run: plug a UVC camera, then
  `bash scripts/bring_up.sh --imsdk` and watch heartbeat fps.
- Preview export is best-effort (multifilesink rewrite + os.replace mirror at
  ≤2 Hz vs mainline's per-frame atomic write).
- fps observed on clips: ~8.8 at `--batch 8`, NPU leg 87 ms/frame — the
  remaining cost is still `qnn-net-run`'s spawn; the next win is `qtimlqnn`
  in-pipeline (needs the re-export above).

## Verification (what was actually run, reproducible)

Full transcript with numbers: [`verify/T-imsdk-fall.txt`](../../verify/T-imsdk-fall.txt).
Stages: (0) element/broker preflight → (1) converter uint8 probe: 160 unique
data-bearing tensors → (2) preproc parity on the NPU, both clips, floors
0.5/0.45: **gate fires match exactly** → (3) 8 hermetic laptop tests, suite
214 green → (4) full module over MQTT: events on the wire with
`meta.engine:"imsdk"`, matching Stage 2; heartbeats; frame export → (6) flag
mechanics: dry-runs, `Conflicts=` both ways, disabled at rest. Stage 5
(live camera) pending hardware, above.
