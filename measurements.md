# Measurements

Every number here was measured on the named hardware, with the method stated —
nothing modelled, nothing quoted from a datasheet. DESIGN.md's rule: nothing
`[?]` goes on a slide until it's measured.

## D3 — voice node RAM gate on the kitchen Ventuno Q (2026-08-06)

Board: kitchen Ventuno Q (10.73.51.123), already running qnet-vision +
qnet-look + qnet-stream + the Qualcomm LLM/VLM container. Method: `free -m` on
the board immediately before `arduino-app-cli app start qnet-voice-node`, and
again after both containers were up, the audio-analytics runner had registered
`['whisper-small', 'whisper-small-quantized']`, float whisper-small had served
a real streaming transcription session, and piper TTS had synthesized one say.

| free -m | total | used | available |
|---|---|---|---|
| Before app start (16:47:06Z) | 15284 | 10080 | **5204** |
| After app + models up (16:49:02Z) | 15284 | 11523 | **3761** |

- Voice node cost: **+1443 MiB** used. Headroom after = 3761 MiB, comfortably
  above the ~800 MiB gate → **float whisper-small stays active**; the
  quantized rollback remains registered (config flip + restart, no copy).
- Evidence: `verify/D3-voice-deploy.txt`.

## T6.3 — look→looked round trip on the Ventuno Q (2026-08-05)

Board: Arduino Ventuno Q, `node/look.py` answering `qnet/look` with
Qwen3-VL-4B (w4a16, Hexagon NPU, Qualcomm LLM/VLM container on :9001), 640 px
frames, broker = the live IQ-9075 Mosquitto at 10.73.51.175:11883 over Wi-Fi.

Method: a paho client **on the board** publishes a `look` (find mode, real
object query) and timestamps until the matching-qid `looked` arrives — the
full path: board → broker → board → frame grab → VLM → broker → board. Five
runs, warm model, vision.py **not** running (so each look pays a direct
camera grab, ~0.6–0.7 s — the worst-case frame path).

| Round trip | Value |
|---|---|
| Median of 5 | **4.13 s** |
| Min / max | 4.11 s / 4.42 s |
| Later single runs, same path | up to 5.4 s (guide mode, camera open 0.67 s) |
| shm frame path (vision.py running), single run | 4.56 s total, frame read 0.02 s |

- Node-side handling alone (frame + VLM + publish, from the service log):
  3.9–5.4 s; the VLM call is ~3.3–4.5 s of it. Consistent with the ~3.4 s
  warm query measured at container setup (`setup/ventuno-vlm/README.md`).
- → `find.look_timeout_s` lowered 8 → **6** in `config/house.yaml`
  (worst observed 5.4 + margin; §13's measured-plus-a-second rule). End-to-end
  ask→say with one of two rooms answering was 9.4 s, dominated by waiting the
  full timeout for the absent bedroom node — the tune cuts that to ~7.5 s.
- Honesty note: during one measurement window every `found` went false because
  a teammate was leaning centimetres from the lens — the VLM correctly
  reported the queried object not visible. Live camera, live workshop.

## T4.2 — fall detection pipeline on the Ventuno Q (2026-08-06)

Board: Arduino Ventuno Q (QCS8300, Hexagon HTP v75), Ubuntu 24.04, sharing the
NPU and 14 GiB RAM with a teammate's live VLM + voice containers. Model: YOLO11n
fall fine-tune, FP32 QNN context binary, run via the `qnn-net-run` CLI (no
onnxruntime on the board — each inference pays process spawn + context reload +
raw-file IO on top of the 34.8 ms pure execute measured in
`models/fall-detection/README.md`).

Method: `python -m qnet.node.vision` over the 110-frame real fall clip
`clips/fall-02-cam0-rgb.mp4` (320×240), broker = live IQ-9075 Mosquitto at
10.73.51.175:11883, conf floor 0.6, rule 5/8. Per-stage wall time accumulated
around each call, printed by the service at EOF.

| Mode | End-to-end | Per frame: preproc | NPU call (spawn+IO+infer) | decode+gate |
|---|---|---|---|---|
| `--batch 1` (frame-at-a-time) | **2.98 fps** (336 ms/frame) | 22.7 ms | 307.7 ms | 1.5 ms |
| `--batch 8` (8 frames per `qnn-net-run`) | **14.55 fps** (69 ms/frame) | 8.9 ms | 56.9 ms | 0.7 ms |

- The CLI overhead dominates batch 1: 307.7 ms per call against 34.8 ms of
  actual NPU execute — ~273 ms is process spawn, context-binary reload and raw
  file IO. Batching 8 frames amortises that to 56.9 ms/frame (~22 ms overhead),
  a 4.9× throughput gain. Both runs produced the identical single
  `fall.detected` with identical confidence — batching changes cadence, not
  decisions. Cost: up to 8 frames (~0.5 s at the achieved rate) of added event
  latency, so `--batch 1` stays the default for the live camera.
- Live camera (`/dev/video0`, 640×480 UVC): 2.56 fps end-to-end at batch 1
  (339 ms NPU call, 19.2 ms preproc); `/dev/shm/qnet_kitchen_frame.jpg` export
  measured 0.3–0.5 s fresh while running.
- 3 fps at batch 1 is comfortably enough for the 5-of-8 rule (a fall stays on
  the floor for many seconds); the real fix if more is ever needed is an
  in-process QNN runtime, not the CLI.
- Reliability: `qnn-net-run` intermittently fails (rc=11, and once a burst of
  fastrpc "Failed to create transport, error 1002" lasting ~1 min) while the
  teammate's VLM/voice containers are active — the NPU is shared and the CLI
  opens a fresh fastrpc session per call. The identical invocation succeeds on
  retry; `vision.py` retries ×3 with 0.2 s backoff and rode through it.
- Detection quality on real footage (floor 0.6): true falls read
  `fallen` 0.67–0.95 sustained; empty office chairs read `sitting` 0.5–0.85
  (irrelevant to the gate — only `fallen` fires it); a person walking in
  close to the camera produced spurious `fallen` 0.84–0.86 for ~10 frames
  (motion blur / partial view) — real flicker the temporal rule exists for,
  and the reason `fall-01` fires an "extra" event if processed from frame 0.
  Threshold/N-of-M tuning against labelled clips is exactly T4.3's job.
- The model reads *deliberate* lying down (UR Fall adl-01) as `fallen` —
  posture, not intent. Known, stated limitation.
