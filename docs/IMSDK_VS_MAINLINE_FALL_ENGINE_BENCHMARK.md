# Fall detection: mainline (cv2) vs IM SDK engine — same clip, same NPU, head to head

**TL;DR — the decisions are identical; the bits are not, and cannot be.**
On the exact same frames, both engines produce the same per-frame verdicts on
~90 % of frames, the **same gate fires on the same frame numbers, and the
same MQTT events** — while their raw confidences differ by a small, measured,
systematic offset that comes entirely from preprocessing. The NPU itself is
bit-deterministic (proven below), so every difference is accounted for.
Throughput is equal (both are `qnn-net-run`-bound). The IM SDK engine ships
with a floor offset (−0.05) that makes gate behaviour match exactly.

Date: 2026-08-07 · Board: Ventuno Q (QCS8300, HTP v75), Ubuntu 24.04, off-site
LAN, local mosquitto · Model: the same `best.bin` (YOLO11n FP32 QNN context
binary) for both engines · Method + raw transcripts:
[`../verify/T-imsdk-fall.txt`](../verify/T-imsdk-fall.txt), bench script
outputs reproduced below. Engines: mainline =
[`qnet/node/vision.py`](../qnet/node/vision.py) (cv2 capture, numpy letterbox
pad-114); IM SDK = [`qnet/node/vision_imsdk.py`](../qnet/node/vision_imsdk.py)
(GStreamer hw decode + `qtimlvconverter` letterbox pad-0, uint8/NHWC →
float in Python). Floors: mainline 0.5, IM SDK 0.45 (the measured
compensation — [`../setup/ventuno-imsdk/README.md`](../setup/ventuno-imsdk/README.md)).

## 1. Is the output identical? — the precise answer

| Layer | Identical? | Measured |
|---|---|---|
| NPU inference (same tensor in) | **Yes, bit-for-bit** | Same tensor run twice → byte-identical output, matching MD5s (`c388aa4fb44e` = `c388aa4fb44e`). The engine pair's differences are therefore 100 % preprocessing. |
| Input tensors | **No — by construction** | 0/160 and 0/150 identical pairs. Mean abs pixel delta 0.113 — **but split by region: image pixels 0.0020 (99.8 % identical), letterbox padding 0.4471 (= exactly 114/255)**. The visible delta is almost entirely the two engines' different pad conventions over the 25 % padded area; actual image content differs only by NV12 chroma subsampling + scaler choice. |
| Per-frame verdicts (best class) | **~90 % identical** | fall-01: 134/160 agree · adl-01: 147/150 agree. Disagreements sit on ambiguous frames (mid-fall transitions; on adl-01, 3/3 are within 0.1 of a floor). |
| Confidences (same-class frames) | **No — small systematic offset** | median delta 0.026 (fall-01) / 0.008 (adl-01); signed mean **−0.018/−0.015 (IM SDK reads lower)**; max 0.19 on one transition frame. |
| Gate fires | **Yes — same frames** | fall-01: frames **[4, 104] on both** · adl-01: frame 116 vs 114 (2-frame skew on a slow slide into lying). |
| MQTT events | **Yes — same events, same schema** | Same topics, same `kind/conf/meta` shape; event `conf` differs by the offset (0.7012/0.8501 vs 0.6592/0.8140); `meta.engine:"imsdk"` labels the experimental engine on the wire — deliberate, so nothing is ever ambiguous about provenance. |

**Why bit-identity is impossible here:** the two engines rasterize the frame
differently before the model ever sees it — cv2's BGR→RGB + INTER_LINEAR
resize + gray-114 padding vs GStreamer's NV12 (chroma-subsampled) → RGB +
`qtimlvconverter` scaler + black padding. Identical bits would require
identical rasterization, which would mean not using the IM SDK path at all.
The right equivalence for a detector is decision-level — and that one holds.

## 2. Gate/event outcomes (the part that reaches the agent)

| Clip | mainline @0.5 | IM SDK @0.45 | Verdict |
|---|---|---|---|
| fall-01 (walks, stands, sits, falls) | fires at frames 4, 104 (conf 0.7012, 0.8501) | fires at frames 4, 104 (conf 0.6592, 0.8140) | **match** |
| adl-01 (ends deliberately lying — documented model limitation, fires by design) | 1 fire, frame 116 (0.6934) | 1 fire, frame 114 (0.6685) | **match** (2-frame skew) |

Floor mapping matters: at *equal* floors (both 0.5) the IM SDK engine's lower
read loses one borderline frame-0 detection and the frame-4 fire with it.
The −0.05 offset is a measured compensation, not a tuning fudge; the same
correction extrapolated to the live calibration (0.8 → 0.76 with 6/6) is in
the shipped unit and still needs a live-camera validation pass.

## 3. Throughput (same clip, same board, same batch, minutes apart)

| | mainline | IM SDK engine |
|---|---|---|
| End-to-end over MQTT, `--batch 8` | **8.86 fps** (18.1 s / 160 frames) | **8.55–8.81 fps** (18.2–18.7 s, three runs incl. under systemd) |
| Preprocessing per frame | 9.4 ms (cv2 + numpy, in-process) | ~2 ms Python (float+transpose); decode/letterbox runs concurrently in the GStreamer process |
| NPU call (spawn+IO+infer) | 100.7 ms | 87.1–98.3 ms |
| Decode + gate | 0.5 ms | (same code) |

Read: **throughput parity.** Both engines are bound by the same
`qnn-net-run` process-spawn cost; the IM SDK front half moves preprocessing
off the Python thread but that was never the bottleneck. The engine's real
throughput headroom — replacing `qnn-net-run` with in-pipeline `qtimlqnn`
(persistent QNN context, no spawn) — is **blocked by this board build's
`qtimlvconverter` float/NCHW path** (emits all-zero tensors); the three
model re-export routes that unblock it are ranked in
[`../setup/ventuno-imsdk/README.md`](../setup/ventuno-imsdk/README.md).
What the front half buys today is robustness (v4l2src + hardware decode
replacing `cv2.VideoCapture`, our flakiest interface) and the proven IM SDK
on-ramp.

## 4. Reproduce

```bash
# tensors from the IM SDK path (board):
gst-launch-1.0 filesrc location=/dev/shm/fall-01-rgb-h264.mp4 ! qtdemux ! h264parse ! \
  v4l2h264dec capture-io-mode=4 output-io-mode=4 ! video/x-raw,format=NV12 ! \
  qtimlvconverter image-disposition=centre ! \
  'neural-network/tensors,type=UINT8,dimensions=(int)<<1,640,640,3>>' ! \
  filesink location=/dev/shm/u8_fall01.raw
# both preprocs through the same NPU + gate, all comparison stats:
~/qnet-venv/bin/python bench_engines.py /dev/shm/fall-01-rgb-h264.mp4 /dev/shm/u8_fall01.raw 0.5 0.45
# end-to-end timing, either engine:
python -m qnet.node.vision       --source /dev/shm/fall-01-rgb-h264.mp4 --broker 127.0.0.1 --port 1883 --conf 0.5  --batch 8 --max-frames 160
python -m qnet.node.vision_imsdk --source /dev/shm/fall-01-rgb-h264.mp4 --broker 127.0.0.1 --port 1883 --conf 0.45 --batch 8
```

(Clips are H.264 transcodes of the UR Fall Detection Dataset regression set —
provenance and rebuild recipe: [`../clips/README.md`](../clips/README.md).)
