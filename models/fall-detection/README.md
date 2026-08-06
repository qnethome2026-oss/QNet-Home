# Fall Detection Model — Setup, Conversion & NPU Deployment Notes

Everything learned getting `melihuzunoglu/human-fall-detection` running end-to-end
on real Hexagon NPU hardware — both the IQ-9075 and the Ventuno Q — so it
doesn't have to be re-discovered. Written after a working session on 2026-08-05.

## Model

- **Source:** [melihuzunoglu/human-fall-detection](https://huggingface.co/melihuzunoglu/human-fall-detection)
- **Architecture:** YOLO11n (Ultralytics), 2,582,737 params
- **Input:** `images`, float32, NCHW `[1, 3, 640, 640]`
- **Output:** `output0`, float32, `[1, 7, 8400]` (raw YOLO head, no NMS baked in — 3 classes + 4 box coords = 7)
- **Classes:** `0: fallen`, `1: sitting`, `2: standing`
- **License:** AGPL-3.0 (Ultralytics default). Fine for this hackathon demo — flag it if QNet Home goes beyond that, since AGPL's copyleft triggers on network use.
- **Accuracy:** not published anywhere, including the model card. Verified only structurally (100% op support on target HTP) and via a random-input smoke test, not against labeled data. If there's time before the demo, hand-labeling ~50–100 held-out frames for a real accuracy number is higher value than anything else left to do here.
- We searched HF / Roboflow Universe / GitHub / academic literature for alternatives (2026-08-05) — **nothing beat this model** for this use case. Everything with better *published* accuracy collapses "sitting" into a binary fall/no-fall class, which defeats the point per `docs/DESIGN.md` §8. Full ranked comparison is in this conversation's history if it needs to be reproduced later.

## Files in this folder

| File | What it is |
|---|---|
| `best.pt` (5.5 MB) | Original Ultralytics checkpoint, as downloaded from HF |
| `best.onnx` (10.6 MB) | ONNX export, opset 17, **`simplify=False`** — see gotcha below |

Exported via:
```python
from ultralytics import YOLO
model = YOLO("best.pt")
model.export(format="onnx", imgsz=640, opset=17, simplify=False)
```

**Gotcha:** exporting with the default `simplify=True` (onnxslim) produces an
ONNX graph where `output0` is declared in both `value_info` and the graph
outputs — invalid per the ONNX IR spec, and it breaks Qualcomm AI Hub's
compiler with `Tensors {'output0'} occur in value_info but also in model IO`.
Always export with `simplify=False` for this model.

## Compiled NPU artifacts

| Artifact | Format | Size | Path (this folder) | Status |
|---|---|---|---|---|
| `best_iq9075.bin` | QNN context binary, **FP32**, compiled for `aihub_device="Dragonwing IQ-9075 EVK"` (HTP v73) | 6.35 MB | `models/fall-detection/best_iq9075.bin` | **Verified running on the real IQ-9075 NPU** |
| `best_ventuno_qcs8300.bin` | QNN context binary, **FP32**, compiled for `aihub_device="QCS8550 (Proxy)"` (HTP v75 — see Ventuno Q section) | 6.37 MB | `models/fall-detection/best_ventuno_qcs8300.bin` | **Verified running on the real Ventuno Q NPU** |
| `best-qdq.onnx` | QDQ ONNX, **INT8** | 4.7 MB | Still only in `QUAD-Client-main\quad_artifacts\best-qdq\best-qdq.onnx` (not copied here yet) | Compiled successfully, **never run on-device** (neither board has `onnxruntime`/QNN EP installed — see Known Issues) |

Both `.bin` files were compiled via the QUAD MCP server
(`https://quad.infra.foundries.io/mcp`), `convert_model` tool, routed
through **Qualcomm AI Hub Models cloud** (`aihub="force"`) rather than the
server's local `qairt-converter`, which is broken (see Known Issues).
`aihub_device` must always be passed explicitly — left unset, `convert_model`
silently defaults to compiling for **Snapdragon X Elite CRD**, the wrong chip
for either board. The IQ-9075's correct device string was found from a
pre-existing export already in the QUAD-Client repo
(`export_assets/mobilenet_v2_iq9075_qnn/.../metadata.json`, `reference_device:
"Dragonwing IQ-9075 EVK"`); the Ventuno Q's required a different approach
entirely — see that section below.

## The IQ-9075 board

| | |
|---|---|
| Board | Dragonwing IQ-9075 EVK |
| SoC | QCS9075 (device-tree also reports `qcom,sa8775p` compatible — shared automotive-class silicon) |
| NPU | Hexagon HTP **v73** |
| OS | Ubuntu 24.04.4 LTS, kernel `6.8.0-1080-qcom`, aarch64 |
| QNN SDK on-device | v2.46.0.260424121129 |
| IP (at time of writing — corp DHCP, will change) | `10.73.51.175` |
| SSH user | `ubuntu` |
| SSH auth | Password auth on first connect; a dedicated Ed25519 keypair (`~/.ssh/id_iq9075` on the Windows host, comment `quad-client-iq9075`) was provisioned into the board's `~/.ssh/authorized_keys` so future connections don't need the password |
| SSH password | `Qcom@2026` |
| Credentials (full set) | Also stored in `QUAD-Client-main\.env_boards` (gitignored, not in this repo) — `IQ9075_HOST`, `IQ9075_SSH_USER`, `IQ9075_SSH_PASSWORD`, `IQ9075_PLINK_PATH`, `IQ9075_SSH_HOST_KEY_FINGERPRINT` |
| Windows SSH tooling | Windows OpenSSH can't do password auth non-interactively — installed PuTTY (`winget install PuTTY.PuTTY`) for `plink.exe`/`pscp.exe` |

## The Ventuno Q board (Arduino UNO Q / QCS8300)

| | |
|---|---|
| Board | Arduino "Ventuno Q" (device-tree: `arduino,monza qcom,monaco-monza qcom,qcs8300`, hostname `ventunoq`) |
| SoC | **QCS8300** — not the QCS2210 assumed by some older docs in this repo/QUAD-Client; verify per-board, don't assume |
| NPU | Hexagon HTP **v75** (confirmed via active on-device skel `/usr/lib/dsp/cdsp/libQnnHtpV75Skel.so`, not just guessed) |
| RAM / cores | 14 GiB / 8 cores |
| OS | Ubuntu 24.04.4 LTS, kernel `6.8.0-1080-qcom`, aarch64 — same kernel build as the IQ-9075, different device tree |
| QNN SDK on-device | **Not installed by default** — installed manually this session: `sudo apt-get install -y qairt-tools qairt-libs qairt-dsp-binaries qairt-headers` → pulled QAIRT 2.46.0 (same version as IQ-9075) from the board's own apt repos |
| IP (at time of writing — corp DHCP, will change) | `10.73.51.123` |
| SSH user | `arduino` |
| SSH password | `oelinux@123` |
| SSH auth | Password auth used directly this session; no dedicated key was provisioned yet (unlike the IQ-9075) — do that if this becomes a recurring target |

**Important — QCS8300 is not in Qualcomm AI Hub's device catalog.** Checked
`qai_hub_models` perf.yaml files on GitHub; the closest IQ-8-series entry is
`Dragonwing IQ-8275 EVK` (a different chip, QCS8275). There is no
`aihub_device` string that names QCS8300 directly.

**Workaround that worked:** HTP context binaries are compiled per Hexagon
*architecture version* (v73, v75, ...), not per exact chip SKU. Compiled
against **`aihub_device="QCS8550 (Proxy)"`** (a cataloged device also on HTP
v75) and it **loaded and executed correctly** on the real QCS8300 board —
confirmed empirically, not just by version-number matching, by actually
pushing the binary and running it. If AI Hub ever adds QCS8300 natively,
switch to that instead — this is a same-arch substitute, not a guarantee for
every model (an op that behaves differently across v75 chip implementations
could theoretically diverge, though none did here).

## On-device paths (IQ-9075)

```
/data/local/tmp/quad/models/          # workspace (hardcoded default in quad-client's device_agent — see Known Issues)
├── best.bin                          # the compiled context binary
├── input_0.raw                       # synthetic float32 input, shape (1,3,640,640), random values
├── input_list.txt                    # contents: "images:=input_0.raw"
└── out/                              # --output_dir
    ├── execution_metadata.yaml       # graph I/O shapes, tensor names
    ├── qnn-profiling-data_0.log      # binary profiling log
    └── Result_0/output_0.raw         # inference output, shape (1,7,8400) float32
```

Backend libraries on-device: `/usr/lib/libQnnHtp.so` (+ arch-specific stubs
`libQnnHtpV73Stub.so` etc., also duplicated under
`/home/ubuntu/.local/share/geniex/qairt/htp-files/`).

Same layout under `/data/local/tmp/quad/models/` on the Ventuno Q (user
`arduino`, group `arduino` instead of `ubuntu`). Backend library there is
also `/usr/lib/libQnnHtp.so`.

## Running inference on-device

Identical command on both boards:

```bash
cd /data/local/tmp/quad/models
qnn-net-run \
  --backend /usr/lib/libQnnHtp.so \
  --retrieve_context best.bin \
  --input_list input_list.txt \
  --output_dir out \
  --profiling_level detailed
```

`--retrieve_context` (not `--model`) because `best.bin` is a pre-compiled
context binary, not a `.so` graph.

## Decoding the profiling log (on the Windows host, not the board)

The board doesn't have `qnn-profile-viewer`. Run it on the host instead,
using the **arm64** build (this dev machine is win-arm64):

```bash
C:\Qualcomm\AIStack\QAIRT\2.36.0.250627\bin\aarch64-windows-msvc\qnn-profile-viewer.exe \
  --input_log=<path to qnn-profiling-data_0.log>
```

## Measured results (FP32, single inference)

| Metric | IQ-9075 (HTP v73) | Ventuno Q (HTP v75) |
|---|---|---|
| Model load (init) | 32.3 ms | 53.2 ms |
| Inference (execute) | **47.9 ms** | **34.8 ms** |
| Throughput | **19.2 inf/sec** | **18.8 inf/sec** (overall NetRun IPS, includes IO/misc — not 1/execute) |
| HVX threads used | 4 | 4 |
| Output sanity | shape `(1,7,8400)`, no NaNs | shape `(1,7,8400)`, no NaNs |
| Op support | 100% | 100% |

Both confirmed genuinely NPU (not CPU/GPU fallback) via: backend was
`libQnnHtp.so`, profiling log reported `Backend (Number of HVX threads
used): 4`, and per-op HVX/HMX cycle counts — none of which appear for a CPU
backend. Ventuno Q's faster raw execute time despite slower init is
consistent with HTP v75 being a newer/higher-throughput architecture than
v73.

**Not yet measured on either board: INT8 on-device latency.** The INT8
`qdq_onnx` artifact exists (`best-qdq.onnx`, see table above) but was never
run — neither board has `onnxruntime` installed.

## Known issues hit along the way

1. **Server-side `qairt-converter` is broken** on `quad.infra.foundries.io`
   (`ImportError: libpython3.10.so.1.0` in `qti.aisw.dlc_utils`). Any
   `convert_model` call with default `aihub="auto"` for `target_sdk="qnn"`
   will hit this. Workaround: pass `aihub="force"` to route through AI Hub
   Models cloud instead. This needs a server admin fix, not fixable
   client-side.
2. **AI Hub's INT8 quantize job fails for `output_format="qnn_context_binary"`**
   with `Incorrect archived model. Expecting only one model asset at base
   path {...}` — a bug in the AI Hub adapter's archive handling, not a model
   problem (FP32 compiles fine via the same path; INT8 via `output_format="qdq_onnx"`
   also works fine — it's specifically the INT8 + context-binary combination
   that's broken).
3. **`aihub_device` defaults to the wrong chip and never errors loudly about
   it.** Must explicitly pass `aihub_device=`. Default silently targets
   Snapdragon X Elite instead of the actual board's HTP arch.
4. **`onnxslim` (export `simplify=True`) produces invalid ONNX** for this
   model — see the ONNX export gotcha above.
5. **`/data/local/tmp/quad/` (the quad-client tool's hardcoded workspace
   default) doesn't exist on either board by default** — it's an
   Android-style path baked into `profile-device`/`device_agent.py`, but
   both boards run plain Ubuntu. `/data` isn't writable by the login user by
   default. Fixed on each board with `sudo mkdir -p
   /data/local/tmp/quad/models && sudo chown -R <user>:<user>
   /data/local/tmp/quad` (`ubuntu:ubuntu` on IQ-9075, `arduino:arduino` on
   Ventuno Q). Do this once per fresh board image.
6. **Neither board has `onnxruntime` installed**, so the INT8 `qdq_onnx`
   artifact can't run on either yet. Would need `pip install onnxruntime`
   (ideally the QNN execution-provider build) on-device to test it.
7. **`quad_mcp_client`'s `profile-device --transport ssh` requires key-only
   auth** (`BatchMode=yes` hardcoded) — doesn't work against a password-auth
   board until a key is provisioned (done for IQ-9075, not yet for Ventuno
   Q). The automated tool's `qnn-net-run` invocation also doesn't supply a
   valid input for a context binary built without a companion
   `model_net.json` (which AI Hub's compile doesn't produce) — that's why
   the actual runs above were done manually rather than through
   `profile-device`.
8. **QCS8300 isn't in Qualcomm AI Hub's device catalog** — see the Ventuno Q
   section above. Worked around by compiling against a different cataloged
   device (`QCS8550 (Proxy)`) that shares the same HTP v75 architecture, and
   confirming empirically on real hardware that it loads and runs.
9. **QAIRT SDK isn't preinstalled on the Ventuno Q image** (unlike the
   IQ-9075, which ships it) — installed manually via `apt-get install
   qairt-tools qairt-libs qairt-dsp-binaries qairt-headers`. Fresh Ventuno Q
   boards will need this step too.

## Local test web app (not part of the NPU pipeline — CPU sanity check only)

`QUAD-Client-main\samples\fall_detection_demo\` — Flask app, single-image
upload **and** a live webcam MJPEG stream (`/webcam`), both running
inference on CPU via Ultralytics (not the NPU path). Auto-downloads
`best.pt` from HF into its own `model_cache/` on first run. Useful for
eyeballing detections quickly; not representative of on-device NPU latency.

## Suggested next steps

1. Get real accuracy numbers — label a small held-out set.
2. Get INT8 actually running on-device: install `onnxruntime` (QNN EP) on
   the board and run `best-qdq.onnx`, or retry the native INT8
   `qnn_context_binary` path once/if the AI Hub archive bug above is fixed
   server-side — should be ~2-4x faster than the 47.9ms FP32 number.
3. Swap the synthetic random `input_0.raw` for a real captured frame to
   sanity-check detections are meaningful, not just structurally valid.
4. Wire into the room-node pipeline described in `docs/DESIGN.md` §8 (YOLO
   "Fallen" in 5 of 8 frames → event).
