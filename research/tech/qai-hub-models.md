# Qualcomm AI Hub Model Catalog — Deep Dive & Mapping to QNet Home
**Research date:** 2026-08-03 · **Catalog version examined:** `qai-hub-models` **v0.59.0** (released 2026-07-28) · **QAIRT in published assets:** 2.45.0 (Workbench also offers 2.46.0 / 2.47.0)

---

## 0. TL;DR — the eight decisions this research forces

1. **The Arduino UNO Q (QRB2210) is NOT an AI Hub target and has NO usable NPU.** It is absent from all 35 AI Hub chipsets and 51 devices. Its "Hexagon DSP" is a sensor/audio aDSP with no HTP/cDSP NN acceleration, FastRPC on Arduino's BSP is documented as broken, and the Adreno 702 has **no proprietary OpenCL driver** on the shipped image (so `onnxruntime-qnn` GPU init fails with `QNN_BACKEND_ERROR_CANNOT_INITIALIZE`). **Plan for CPU-only inference on UNO Q** (quad Kryo A53 @ 2.0 GHz, 2 GB or 4 GB RAM, 16 GB eMMC).
2. Therefore: put **tiny models on UNO Q** (YamNet 14 MB, MediaPipe-Pose 16 MB total, face_det_lite 3.4 MB) and **everything heavy on the X Elite NPU**. Frame that asymmetry as a deliberate architectural decision ("semantic events up, no pixels up"), not a limitation.
3. **Snapdragon X Elite CRD == Dragonwing IQ-X7181** in AI Hub (both `htp_version: 73`, `soc_model: 60`, identical published latencies). Any IQ-X7181 number is an X Elite number — a legitimate way to cite more data points.
4. **Use `qai-hub-models fetch`, not `export`.** Pre-compiled, ready-to-run assets (`.onnx.zip`, `.dlc`, `.tflite`, `.bin`, `.geniex.zip`, `.gguf`) are downloadable from the CLI with **no Workbench account and no compile job**. Reserve compile/profile jobs for the 2–3 numbers you want to quote in the deck.
5. **GenieX is the headline find.** `github.com/qualcomm/geniex` (BSD-3, developer preview) is a public on-device LLM/VLM runtime for **Windows ARM64** that runs *any GGUF from Hugging Face* on **Hexagon NPU / Adreno GPU / CPU**, *or* pre-compiled QAIRT NPU bundles — and exposes an **OpenAI-compatible server on `http://127.0.0.1:18181/v1`**. This is almost certainly the public equivalent of the internal "QUAD"-style GGUF-on-Qualcomm story (no artifact named "QUAD" is public — see §14). Point OpenClaw at that endpoint and the whole LLM problem collapses to one install step.
6. **INT8 has an accuracy cliff on detectors but not on pose.** YOLOv11-Det: 46.2 mAP float → **37.3 at w8a8** (−8.9!) but **45.5 at w8a8_mixed_int16**. HRNetPose: 68.6 float → **68.3 at w8a8**. ResNet-3D: **70.0 Top-1 at w8a8, identical to float**. Quote these; they show you understood quantization instead of just typing `--quantize w8a8`.
7. **AI Hub publishes latency + peak memory but NO energy/power metric.** The 40-pt technical criterion asks for energy efficiency → you must measure it yourself (see §17 for the plan). This is a differentiator nobody else will bother with.
8. **Two blockers to design around now:** (a) TTS on X Elite ships **only** as `voice_ai` runtime assets (Qualcomm Voice AI SDK) — no ONNX/TFLite fallback; (b) **there is no voice-cloning model anywhere in the catalog** — the "parent's cloned voice" feature has zero on-catalog support (§8).

---

## 1. Catalog shape as of Aug 2026

| Fact | Value |
|---|---|
| Repo | `github.com/quic/ai-hub-models` (redirects to `github.com/qualcomm/ai-hub-models`) |
| Version / date | v0.59.0, 2026-07-28 |
| Model directories in `src/qai_hub_models/models/` | **237** |
| Model variants on the IoT catalog page | 466 variants / 213 models |
| Portal rename | `app.aihub.qualcomm.com` → **`workbench.aihub.qualcomm.com`** ("AI Hub **Workbench**") |
| Lightweight CLI (new) | `pip install qai_hub_models_cli` → `qai-hub-models {models,info,perf,numerics,fetch,find,devices,chipsets,runtimes,versions}` |
| Full package | `pip install qai_hub_models` (adds `export`, `evaluate` — needs Workbench API token) |
| License | BSD-3 (repo). Individual models inherit upstream licenses — **YOLOv8/v11 are AGPL-3.0 and flagged `restrict_model_sharing: true`** |

### Supported target runtimes (documented)
| Runtime | Asset ext | OS | Notes |
|---|---|---|---|
| `tflite` (LiteRT) | `.tflite` | Android, Linux | "recommended for Android"; CPU/GPU/NPU |
| `onnx` | `.onnx.zip` | Android, Linux, Windows | **"recommended for Windows developers"**; CPU/GPU(DML)/NPU |
| `qnn_dlc` | `.dlc` | Android, Linux, Windows | hardware-agnostic, forward-compatible across QAIRT versions |
| `qnn_context_binary` | `.bin` | Android, Linux, Windows | **SoC-specific, NPU-only**, fastest cold start |
| `precompiled_qnn_onnx` | `.onnx.zip` | Android, Linux, Windows | QNN context binary wrapped in ONNX |

### Additional runtimes visible in the catalog's own perf data (not in public compile docs)
Found in `devices_and_chipsets.yaml → scorecard_path_to_website_runtime`:
`genie` (`.genie.zip`), **`geniex_qairt`** (`.geniex.zip`), **`geniex_llamacpp`** (`.gguf`), **`voice_ai`** (`.bin`).
→ These are how LLMs/VLMs and TTS/ASR are actually profiled and shipped today. `voice_ai` maps to a **Qualcomm Voice AI SDK**; manifests carry `voice_ai_sdk: asr | tts | translation` on 14 models (all Whisper variants, MeloTTS ×3, OpusMT ×4).

### Chipsets / devices (35 / 51) — the ones that matter to us
| AI Hub chipset | Marketing name | HTP ver | Reference device | World |
|---|---|---|---|---|
| `qualcomm-snapdragon-x-elite` | Snapdragon X Elite (SC8380XP) | **73** | Snapdragon X Elite CRD | Compute |
| `qualcomm-snapdragon-x2-elite` | Snapdragon X2 Elite (SC8480XP) | 81 | Snapdragon X2 Elite CRD | Compute |
| `qualcomm-snapdragon-x-plus-8-core` | X Plus 8-Core | 73 | X Plus 8-Core CRD | Compute |
| `qualcomm-qcs7181` | Dragonwing IQ-X7181 | **73** | IQ-X7181 (Windows 11) | IoT — *proxy for X Elite* |
| `qualcomm-qcs6490` | Dragonwing QCS6490 | 68 | **RB3 Gen 2 Vision Kit** | IoT — *lowest-end target on AI Hub* |
| `qualcomm-qcs8550-proxy` | Dragonwing QCS8550 | 73 | QCS8550 (Proxy) | IoT |
| `qualcomm-qcs8275` | Dragonwing QCS8275 | 75 | IQ-8275 EVK | IoT |
| `qualcomm-qcs9075` | Dragonwing IQ-9075 | 73 | IQ-9075 EVK (2 NPUs) | IoT |
| `qualcomm-qcs8750` | Dragonwing Q-8750 | 79 | Q-8750 | IoT |
| `qualcomm-qcm6690` | Dragonwing Q-6690 | 73 | Q-6690 MTP | IoT |

**No `QRB2210`, no `QCM2290`, no `QRB4210/5165`.** The smallest supported Dragonwing is QCS6490.

---

## 2. Hardware reality check — Arduino UNO Q vs AI Hub

| | Arduino UNO Q (QRB2210) | RB3 Gen 2 (QCS6490) | Snapdragon X Elite |
|---|---|---|---|
| On AI Hub? | ❌ not a chipset or device | ✅ `Dragonwing RB3 Gen 2 Vision Kit` | ✅ `Snapdragon X Elite CRD` |
| NN accelerator | Adreno 702 GPU + always-on aDSP; **no HTP** | Hexagon HTP v68 | Hexagon HTP v73, ~45 TOPS |
| CPU | 4× Kryo (A53-class) @ 2.0 GHz | 4×A78 + 4×A55 | 12× Oryon |
| RAM | **2 GB / 4 GB** LPDDR4, 16 GB eMMC | 4–8 GB | 16–64 GB |
| GPU compute usable? | **No** — proprietary Adreno OpenCL driver absent from Arduino image; `onnxruntime-qnn` GPU backend fails to initialize | Yes | Yes |
| FastRPC / DSP | Arduino BSP lacks FastRPC reserved-DMA in device tree; `hexagonrpcd` install caused boot instability (EDL recovery required); `0x80000406` session-create failures even after manual `/usr/lib/rfsa/adsp/` setup | Working (`qcom-fastrpc1`) | N/A (Windows QAIRT) |
| Realistic runtime | ONNX Runtime CPU / LiteRT CPU (XNNPACK), Python, Docker "Bricks" in Arduino App Lab | LiteRT + QAIRT TFLite delegate on NPU (GStreamer sample apps exist) | ORT QNN EP, QAIRT, GenieX |

**Consequence for QNet Home:** the UNO Q edge node is a *sensor + feature-extractor + event publisher*, not an inference workhorse. Keep per-node models ≤ ~15 MB and ≤ ~30 MFLOPs/frame class (YamNet, MediaPipe-Pose landmark, face_det_lite), do the GStreamer plumbing your team is expert at, and publish semantic events. If you need NPU numbers from an edge node for the deck, cite **RB3 Gen 2 (QCS6490)** rows as the "next-gen node" and be explicit that UNO Q runs the CPU path.

> **Tactical alternative worth 20 minutes of discussion:** move the *pose/action* leg of the pipeline to the **Android phone** (which *is* an AI Hub target with a real HTP) and keep UNO Q for audio + GPIO + presence. That gives you three genuinely NPU-accelerated tiers (phone HTP → X Elite HTP → AIC100) and still uses the UNO Q as a distinct, physically-embedded node.

---

## 3. Workflow: fetch vs export; compile / profile / inference jobs

### Fast path (no account, use this for the hackathon)
```bash
pip install qai_hub_models_cli
qai-hub-models models --domain "Computer Vision" --use-case "Pose Estimation"
qai-hub-models info MediaPipe-Pose-Estimation          # specs + available assets
qai-hub-models perf  HRNetPose -c qualcomm-snapdragon-x-elite
qai-hub-models numerics YOLOv11-Detection              # accuracy per precision
qai-hub-models fetch HRNetPose --runtime onnx --precision w8a8    # ready-to-run asset
qai-hub-models fetch MediaPipe-Pose-Estimation -r precompiled_qnn_onnx -p w8a8 \
        -c qualcomm-snapdragon-x-elite
qai-hub-models find YamNet -r tflite -s qairt=2.45     # search older releases
```
Two asset shapes exist in `release-assets.yaml`:
* **`universal_assets`** — chipset-agnostic (`onnx`, `qnn_dlc`, `tflite`). Available for LiteHRNet, HRNetPose, RTMPose, YOLOv8/v11, Midas, face_det_lite, ResNet-3D, YamNet, …
* **`chipset_assets`** — per-chipset (`precompiled_qnn_onnx`, `qnn_context_binary`, `voice_ai`, `geniex_*`). Available for MediaPipe-Pose, Whisper, MeloTTS/PiperTTS, LLMs.

Verified X Elite assets exist for: `mediapipe_pose` (float+w8a8 × precompiled_qnn_onnx + qnn_context_binary), `whisper_base` (float × precompiled_qnn_onnx / qnn_context_binary / voice_ai), `melotts_en` & `pipertts_en` (**voice_ai only**), and universal onnx/dlc/tflite for hrnet_pose, litehrnet, rtmpose_body2d, yolov8_det, face_det_lite, midas, resnet_3d.

### Full path (needs Workbench)
```bash
pip install qai_hub_models
qai-hub configure --api_token <token>       # from workbench.aihub.qualcomm.com/account/
qai-hub-models export hrnet_pose --target-runtime onnx --precision w8a8 \
        --device "Snapdragon X Elite CRD"
```
`export` runs 5 stages on a real cloud-hosted device: **compile → quantize → profile → inference (numerics vs PyTorch) → download**. `submit_compile_job` / `submit_profile_job` / `submit_inference_job` / `submit_quantize_job` are also callable directly from the `qai_hub` Python client. Profile output = `inference_time_milliseconds`, `estimated_peak_memory_range_mb`, `layer_counts{npu,gpu,cpu,total}`, `primary_compute_unit`.

### Recent Workbench changes to be aware of (2026)
* **2026-07-06** — AIMET 2.34; compile-job optimizations (Reshape-Transpose-Reshape rank reduction, RMSNorm decomposition, Einsum lowering); `.pt2` accepted without `input_specs`.
* **2026-06-22** — **QAIRT 2.47.0** added (2.45/2.46/2.47 selectable); **ONNX Runtime 1.26.0 with QNN EP 2.2.0**; **TorchScript compilation officially deprecated** → migrate to `.pt2` ExportedProgram.
* **2026-06-09** — Samsung Galaxy S26 (SM8850-AD) added; **LiteRT 1.4.4**; `quantize_bias` on by default.
* **2026-05-28** — QNN context binaries can be embedded inside ONNX by `submit_compile_job()` / `submit_compile_and_link_jobs()`.

### ⚠️ The Windows-on-ARM Python trap (will cost you half a day if you hit it blind)
* `pip install qai_hub_models` **requires AMD64 (x64) Python on Windows** — "Installation will fail when using Windows ARM64 Python."
* Running models with **ONNX Runtime QNN requires native ARM64 Python** — "running x64 Python under emulation breaks NPU access via ONNX Runtime QNN."
* ⇒ **Set up two Python environments on the X Elite box on Day 1:** an x64 venv for `qai_hub_models` export/quantize, and an ARM64 venv (`onnxruntime-qnn`, Python 3.11) for runtime. Qualcomm's own `whisper_windows_py` app ships an `install_runtime.ps1` that installs ARM64 Python for exactly this reason — steal it.

---

## 4. Pose estimation / body landmarks

All numbers = **NPU**, published in `perf.yaml` (QAIRT 2.45). "X Elite" = `Snapdragon X Elite CRD`; "RB3 G2" = `Dragonwing RB3 Gen 2 Vision Kit` (QCS6490); "IQ-8275" = QCS8275 EVK.

| Model | Params / size | Input | Accuracy | X Elite (best) | X2 Elite | RB3 G2 (QCS6490) | IQ-8275 | Type |
|---|---|---|---|---|---|---|---|---|
| **MediaPipe-Pose** (BlazePose, 2-stage) | det 815 K / 3.14 MB + lm 3.36 M / 12.9 MB | 256×256 | — | **1.74 ms** float (0.889+0.849, precompiled_qnn_onnx); **0.60 ms** w8a8 (0.307+0.292) | **0.34 ms** w8a8 | **2.83 ms** w8a8 (1.756+1.077) | 1.79 ms w8a8 | single person, 33 kp + face/hands |
| **LiteHRNet** | 1.11 M / **4.49 MB** | 256×192 | 58.0 mAP COCO-WholeBody | **2.365 ms** qnn_dlc float (onnx 5.61) | 1.23 ms | — (no w8a8 published) | 4.96 ms | top-down, 17 joints |
| **Posenet-Mobilenet** | 3.31 M / 12.7 MB | 513×257 | 47.8 mAP (w8a8 45.3, w8a16_mixed 47.3) | **0.563 ms** w8a8 onnx (float 1.68) | 0.268 ms | **3.088 ms** w8a8 onnx | 1.655 ms | **bottom-up, multi-person** |
| **RTMPose-Body2d** | 17.9 M / 68.5 MB (w8a16 18.2 MB) | 256×192 | 50.5 float → **51.4 w8a16** | **1.711 ms** float onnx / 1.739 ms w8a16 | 0.766 ms | 5.746 ms w8a16 onnx | 3.812 ms | top-down, **133 whole-body kp** |
| **HRNetPose** | 28.5 M / 109 MB (w8a8 28.1 MB) | 256×192 | **68.6 mAP** (w8a16 68.6, w8a8 68.3) | **1.112 ms** w8a8 onnx / 1.741 w8a16 / 2.397 float | 0.646 ms (8E Gen5) | — | 14.13 ms float | top-down, highest accuracy |
| **YOLOv11-Pose** | — | 640×640 | — | **5.83 ms** float qnn_dlc / 5.176 w8a16 | 2.592 ms | 18.088 ms w8a16 onnx | 8.823 ms w8a16 | **single-stage multi-person** person+17 kp |
| **YOLO26-Pose** | — | — | — | in catalog (newest) | | | | single-stage |
| **CenterNet-Pose** | — | — | — | in catalog | | | | bottom-up |
| **SixDRepNet** | — | — | — | in catalog | | | | 6-DoF **head pose** (gaze direction proxy) |
| **Facial-Landmark-Detection** (`facemap_3dmm`) | — | — | — | in catalog | | | | 3DMM face landmarks |

**Not in the catalog:** MoveNet (Google) — closest equivalents are Posenet-Mobilenet (bottom-up multi-person) and MediaPipe-Pose (single-person).

**Recommendation for fall detection:**
* **X Elite side:** `Posenet-Mobilenet w8a8` (0.56 ms, multi-person, 45.3 mAP) or `YOLOv11-Pose w8a16` (5.2 ms, one-shot person+keypoints, no separate detector). At 0.56 ms you can run **8 virtual rooms at 30 fps and still use <15 % of one NPU context** — that is a resource-utilization number worth putting on a slide.
* **UNO Q side (CPU):** MediaPipe-Pose (16 MB total, 256×256) is the only realistic option; note that top-down models (HRNet/LiteHRNet/RTMPose) need an upstream person detector, which doubles cost — a real argument for BlazePose or YOLO-Pose on the node.

---

## 5. Person / object detection

| Model | Params / size | Input | mAP (COCO) | X Elite | X2 Elite | RB3 G2 | IQ-8275 |
|---|---|---|---|---|---|---|---|
| **YOLOv8-Detection** (v8n) ⚠️AGPL | 3.18 M / 12.2 MB | 640×640 | 44.2 f · **37.4 w8a8** · 44.0 w8a16 · 43.9 w8a8_mixed_int16 | **1.598 ms** w8a8 onnx · 3.689 w8a16 dlc · 4.173 f dlc · 6.594 mixed | 0.670 ms w8a8 | 4.264 ms w8a8 tflite · 12.665 w8a16 | 3.045 w8a8 |
| **YOLOv11-Detection** ⚠️AGPL | — | 640×640 | 46.2 f · **37.3 w8a8** · 45.8 w8a16 · **45.5 w8a8_mixed_int16** | **4.494 ms** f dlc · 4.609 w8a16 dlc | 2.113 w8a16 | 4.967 w8a8 tflite · 16.436 w8a16 onnx | 3.398 w8a8 tflite |
| **YOLO26-Detection** | — | — | 47.7 f · 47.2 w8a16 | **4.848 ms** f dlc · 4.781 w8a16 dlc | 2.315 w8a16 | 16.97 w8a16 onnx | 8.101 w8a16 |
| **Yolo-X** | — | — | — | **2.722 ms** w8a8 dlc · 6.111 w8a16 dlc | 1.219 w8a8 | 8.66 w8a8 tflite | 5.835 w8a8 |
| **Person-Foot-Detection** (`foot_track_net`) | — | — | — | **1.409 ms** w8a8 · 3.672 w8a16 · 4.718 f | — | 5.496 w8a8 tflite | 3.535 w8a8 |
| **PPE-Detection** (`gear_guard_net`) | — | — | — | **0.500 ms** w8a8 · 0.947 w8a16 | — | 2.235 w8a8 | 1.249 w8a8 |
| **Lightweight-Face-Detection** (`face_det_lite`) | 878 K / 3.37 MB (**965 KB w8a8**) | 480×640 | — | **0.436 ms** w8a8 onnx · 1.854 w8a16 | 0.225 w8a8 | 1.657 w8a8 tflite | 1.077 w8a8 |
| **DETR-ResNet50** | — | — | — | 17.808 ms f onnx | 8.252 | — | 85.98 |
| **RF-DETR** | — | — | — | 50.836 ms f dlc | 25.076 | — | 135.4 |
| **Conditional-DETR-R50**, DETR-R101(-DC5), Detectron2-Detection, RTMDet, CenterNet-2D, ResNet34-SSD, 3D-Deep-BOX, YOLOv3/5/6/7/9/10, Yolo-R, YOLOv8-OBB | — | — | — | all in catalog | | | |
| **YOLO-WORLD** (open-vocabulary!) | — | — | — | detector **109.8 ms** f onnx + text_encoder **264.7 ms** | 34.8 + 104.7 | 502.5 (w8a16 det) | 193.1 + 657.6 |

### Two sharp technical points to use
1. **The w8a8 cliff is real and avoidable.** YOLOv11 loses 8.9 mAP at w8a8 but only 0.7 at `w8a8_mixed_int16`. Pose models don't have this problem (HRNet −0.3, Posenet −2.5 or 0 with mixed). Saying "we used `w8a16` for the detector and `w8a8` for the pose head because the accuracy/latency Pareto front differs by task" is exactly the kind of statement the technical judges reward.
2. **YOLO-WORLD's text encoder runs once per vocabulary, not per frame.** Precompute the 264.7 ms text embedding for a hazard vocabulary ("knife", "scissors", "stove", "medication bottle", "stairs", "cord") at startup and cache it; then per-frame cost is 109.8 ms. That gives you **open-vocabulary hazard detection with a config file instead of a retrained model** — a strong innovation/uniqueness angle (kid-safety mode: parent types new hazards, no retraining). ⚠️ It is the *only* NPU model in this list that costs >100 ms; budget it as an on-demand tool call, not a continuous stream.

---

## 6. Action / fall recognition — the honest picture

There is **no fall-detection model** and **no fall/violence dataset** in the catalog. Options, in order of pragmatism:

| Approach | Model(s) | X Elite latency | Notes |
|---|---|---|---|
| **A. Pose → hand-rolled temporal classifier** *(recommended)* | Posenet-Mobilenet or YOLOv11-Pose + your own rules/GRU on keypoint trajectories | 0.56–5.8 ms/frame + ~0 | Fully explainable, tiny, tunable live on stage; keypoint-only features are also *inherently privacy-preserving* — a first-class pitch point. Classic features: torso-axis angle vs vertical, hip-center vertical velocity, bbox aspect-ratio flip, post-impact immobility window. |
| **B. Video classification on clips** | **ResNet-3D** (r3d_18, 33.4 M / 127 MB, **112×112** clip, Kinetics-400) | **22.394 ms w8a8 onnx** (float 67.7) · X2 11.6 · **RB3 G2 137.1 ms qnn_dlc** · IQ-8275 75.9 | **Top-1 70.0 at w8a8 = identical to float.** Kinetics-400 has `falling off chair`-adjacent classes but is not a fall detector; use as a *second opinion* / "what is happening" describer. ⚠️ **The TFLite path for 3D convs is catastrophically broken: 1264 ms (QCS8550), 2775 ms (IQ-8275), 9128 ms + 5.2 GB peak (RB3 G2). Use `onnx` or `qnn_dlc` only.** |
| | **ResNet-2Plus1D** | 25.02 ms w8a8 onnx (float 66.9) · RB3 G2 131.6 dlc | same caveat (tflite 4137 ms) |
| | **ResNet-Mixed-Convolution** | in catalog | |
| | **Video-MAE** | **2859 ms** onnx — unusable | do not consider |
| **C. VLM-as-judge on a triggered snapshot** | Qwen3-VL-2B/4B via GenieX (§12) | TTFT 100 ms–3.2 s, 21–24 tok/s | Best *explanation* quality; use only after a cheap trigger fires. |
| **D. Depth as a fall prior** | Midas-V2 w8a8 (§9) | **1.332 ms** | Body-centroid height above floor plane is a very strong, very cheap fall signal and it's nearly free at 1.3 ms. Underused idea. |
| **E. Audio as the trigger** | YamNet (§7) | **0.097 ms** | AudioSet has thump/crash/scream/glass/speech classes. |

**Design recommendation:** cascade **E (YamNet, 0.1 ms) or A (pose, 0.6 ms) as always-on trigger → D (depth, 1.3 ms) + B (ResNet-3D, 22 ms) as confirmation → C (VLM) only for the human-readable narrative**. That cascade is (i) cheap, (ii) measurable, (iii) exactly the "resource utilization / optimization" story worth 40 points. Report the *duty cycle*: e.g. "always-on tier = 0.7 ms/frame = 2.1 % of one NPU at 30 fps; confirmation tier fires <0.1 % of the time."

---

## 7. Audio classification & speech recognition

### Audio event classification
| Model | Params / size | Input | X Elite | X2 Elite | RB3 G2 | IQ-8275 | QCS8550 |
|---|---|---|---|---|---|---|---|
| **YamNet** (AudioSet ontology, MobileNet-v1 DW-sep) | 3.73 M / **14.2 MB** | 1×1×96×64 log-mel (**0.96 s**) | **0.097 ms** w8a8 onnx · 0.099 w8a16 · 0.166 float | **0.059 ms** w8a16 | **0.553 ms** w8a8 tflite · 0.639 dlc · 0.719 onnx | 0.392 w8a8 | 0.134 w8a8 |

YamNet is the only audio classifier in the catalog. It is `imsdk_supported: true`, has a ready-made **Ubuntu Docker + LiteRT sample app** (`apps/yamnet_ubuntu_py`) that runs it "on the Qualcomm NPU via the QAIRT TFLite delegate", and at **0.1 ms / 0.96 s of audio it is ~10,000× realtime on X Elite**. Use it as the always-on ear on every node. **No wake-word/KWS model, no VAD, no sound-source-localization, no speaker-ID model is published** (`HuggingFace-WavLM-Base-Plus`, 95.1 M / 363 MB, WER 6.83 — which *could* give speaker embeddings — is `status: pending`, i.e. not published).

### Speech recognition (all NPU, per-30 s-window encoder + per-token decoder)
| Model | Encoder / decoder params | X Elite enc | X Elite dec (per token) | X2 Elite enc | QCS8550 enc | IQ-8275 enc |
|---|---|---|---|---|---|---|
| **Whisper-Tiny** | 9.39 M / 28.4 M (35.9 + 109 MB) | **26.16 ms** | 2.103 ms | 12.68 | 25.22 | 73.06 |
| **Whisper-Base** | 23.7 M / 48.9 M (90.7 + 187 MB) | **49.00 ms** | 3.722 ms | 22.67 | 48.02 | 142.5 |
| **Whisper-Small** | — | 132.0 ms | 10.10 ms | 60.08 | 131.0 | 449.3 |
| **Whisper-Large-V3-Turbo** | — | 626.9 ms (⚠️ **1677 MB peak** on precompiled path) | 8.15 ms | 269.7 | 664.4 | — |
| **Distil-Whisper** | — | 133.1 ms onnx | 11.39 ms | 60.27 | 130.2 | 438.2 (tflite falls to **GPU, 3107 ms**) |
| **Zipformer** (streaming, zh+en mixed; enc 63.2 M / 242 MB, dec 3.47 M, joiner 3.21 M) | 80×71 = **0.71 s chunk** | **enc 9.402 ms + dec 0.044 + joiner 0.251 = ~9.7 ms per 0.71 s chunk** | — | 5.98 | 8.88 | 23.48 |
| Whisper-Medium, Whisper-Small-Quantized, Whisper-Small-V2, Whisper-Large-V3-Turbo-Quantized | in catalog | | | | | |

**Recommendation — this is a genuinely non-obvious win:** for the two-way "Are you OK?" conversation, **use Zipformer, not Whisper**. Whisper is a 30-second-window batch model: even Whisper-Tiny forces you to buffer up to 30 s before the encoder runs, which destroys conversational turn-taking. Zipformer is a **streaming transducer on 0.71 s chunks at 9.7 ms/chunk on X Elite ≈ 73× realtime**, giving true incremental transcription and **barge-in / interruption support** in a voice loop. Keep Whisper-Base (49 ms/30 s) as the batch fallback for "transcribe this recorded clip for the caregiver log". Ready-made ORT-QNN Windows sample: `apps/whisper_windows_py`.

---

## 8. Text-to-speech — and the voice-cloning gap (⚠️ biggest product risk)

| Model | Components (params / float size) | Max tokens | X Elite total (voice_ai runtime, NPU) | X2 Elite | QCS8550 | IQ-8275 |
|---|---|---|---|---|---|---|
| **PiperTTS-EN** | encoder 7.51 M/28.7 MB · sdp 1.04 K · flow 7.39 M/28.2 MB · decoder 1.66 M/6.37 MB · t5_encoder 15.1 M (g2p) · t5_decoder 5.72 M | **64** | **≈61.5 ms** (29.851 + 11.218 + 15.852 + 3.070 + 1.058 + 0.421) | ≈38.2 ms | ≈61.4 ms | ≈119.8 ms |
| **MeloTTS-EN** | bert_wrapper 94.5 M/**360 MB** · encoder 8.30 M · flow 20.1 M · decoder 14.5 M · t5_encoder 15.1 M · t5_decoder 5.72 M | **512** | **≈262 ms** (7.705 + 40.349 + 129.768 + 82.620 + 1.060 + 0.436) | ≈138 ms | ≈265 ms | ≈481 ms |
| MeloTTS-ES / -ZH, PiperTTS-DE / -IT | | | multilingual variants | | | |

**Critical constraint:** on `qualcomm-snapdragon-x-elite` these models ship **`voice_ai` assets only** (`.bin`) — there is **no `onnx`, `tflite`, or `qnn_dlc` X Elite asset for either TTS model.** You must either obtain the **Qualcomm Voice AI SDK** or bypass AI Hub for TTS. Verify SDK availability on **Day 1**; this is a single point of failure for the "speaks reassurance through the room speaker" demo.

**Fallbacks, ranked:**
1. **Windows built-in SAPI / `System.Speech.Synthesis` / WinRT `SpeechSynthesizer`** — zero-dependency, instant, ships with the EXE. Ugly voice but a *working* demo beats a broken one. Wire this behind an interface on Day 1.
2. **Piper upstream** (`rhasspy/piper`) with its own ONNX voices via ORT CPU/QNN — Piper's own release ONNX models are small (≈20–60 MB per voice) and you already know the architecture from the AI Hub port.
3. **Windows AI Foundry / Windows ML** on-device voices if available on your build.

**Voice cloning: nothing in the catalog.** There is **no** OpenVoice / XTTS / CosyVoice / F5-TTS / VALL-E / speaker-embedding TTS anywhere in the 237 models. MeloTTS is multi-speaker with *fixed* speakers; Piper is a fixed-voice VITS. `WavLM-Base-Plus` (the one model that could yield a speaker embedding) is unpublished. **Concrete recommendations:**
* **Re-frame the feature** from "clone the parent's voice" to **"speak in the parent's registered voice persona"**: (a) a *pre-recorded phrase bank* the parent records at setup (consent-first, and honestly *more* convincing than a cloned TTS on a stage demo), spliced with (b) TTS for the dynamic remainder, plus (c) the parent's *actual typed message* rendered via TTS. This keeps the entire emotional pitch, removes the technical risk, and is arguably a *better* privacy/consent story — which is your whole thesis.
* If you insist on real cloning: run **Piper fine-tuned or an XTTS/OpenVoice tone-color converter on the X Elite CPU/GPU** as an *offline enrollment step* (minutes, not realtime) that bakes a voice at setup time; then realtime inference is a plain VITS decode. Do **not** put realtime cloning on the critical path of a 4-day build.

---

## 9. Depth estimation

| Model | Params / size | Input | Accuracy | X Elite | X2 Elite | RB3 G2 | IQ-8275 |
|---|---|---|---|---|---|---|---|
| **Midas-V2** (`MiDaS_small`) | 16.6 M / 63.2 MB (w8a8 16.9 MB) | 256×256 | δ1 88.1 float / **88.0 w8a8** (NYUv2) | **1.332 ms** w8a8 onnx · 2.774 float onnx | 0.616 | **4.719 ms** w8a8 onnx | 2.508 w8a8 tflite |
| **Depth-Anything** / **-V2** | — | — | — | **27.7 ms w8a16 onnx** · 49.1 float onnx · ⚠️ **w8a16 qnn_dlc regresses to 137.8 ms** | 12.1 w8a16 onnx | 106.8 w8a16 onnx | 142.3 f / 258.8 w8a16 (2002 MB peak!) |
| **Depth-Anything-V3** | — | — | — | in catalog (newest) | | | |
| **CREStereo**, **StereoNet** | — | — | — | stereo pairs | | | |

**Use Midas-V2 w8a8.** At **1.332 ms** with **zero accuracy loss** it is nearly free, and metric-relative depth gives you two high-value signals no competitor will have: **(1) body-centroid height above the floor plane → a fall prior far more robust than 2D keypoints alone; (2) "child approaching the stove/stairs" proximity zones defined in 3D instead of 2D pixel polygons.** Note the Depth-Anything `qnn_dlc` w8a16 regression (137.8 ms vs 27.7 ms on onnx) — a concrete example of "we profiled both runtimes and picked the right one", which is precisely what the technical rubric asks for.

---

## 10. Face detection / recognition / attributes

| Model | Params / size | Input | X Elite | X2 Elite | RB3 G2 | IQ-8275 |
|---|---|---|---|---|---|---|
| **Lightweight-Face-Detection** (`face_det_lite`) | 878 K / 3.37 MB (**965 KB w8a8**) | 480×640 | **0.436 ms** w8a8 onnx · 1.854 w8a16 · 2.031 float | 0.225 | 1.657 w8a8 tflite | 1.077 w8a8 |
| **MediaPipe-Face** (det + landmark) | — | — | **0.449 ms** w8a8 (0.268 + 0.181) · 0.967 float | 0.269 w8a8 | 1.236 w8a8 tflite | 1.141 w8a8 |
| **Facial-Attribute-Detection** (`face_attrib_net`) | — | — | **0.393 ms** w8a8 onnx · 0.841 float | 0.179 | 1.408 w8a8 tflite | 1.038 w8a8 |
| **HRNetFace** | — | — | in catalog | | | | 
| **CavaFace** (face recognition / embedding) | — | — | in catalog | | | |
| **Facial-Landmark-Detection** (`facemap_3dmm`) | — | — | in catalog | | | |
| **SixDRepNet** (6-DoF head pose) | — | — | in catalog | | | |
| **EyeGaze** (gaze estimation) | — | — | in catalog | | | |

**Privacy positioning:** run `face_det_lite` (0.44 ms) to **detect** presence/consent and to **blur or crop** before anything leaves the node — never for identification. Then explicitly state that **CavaFace/face recognition is deliberately NOT used**. Turning an available capability *down* on principle is a genuinely differentiating story in a privacy-first pitch, and it's free to say. `SixDRepNet` + `EyeGaze` are cheap and give you "child is watching the TV / looking away from the road" style signals for the kid-monitoring use case (TV time) without any face ID.

---

## 11. LLMs / SLMs on AI Hub + Genie / GenieX

### Catalog (Generative AI → Text Generation, 38 entries)
Qwen3-0.6B / 1.7B / 4B / 4B-Instruct-2507 / 8B · **Qwen3.5-0.8B / 2B** · Qwen2-7B-Instruct · Qwen3-VL-2B / 4B / 8B-Instruct · Qwen2.5-VL-7B-Instruct · **Phi-3.5-Mini-Instruct**, **Phi-4-Mini-Instruct** · Llama-v3-8B, v3.1-8B, **v3.2-1B**, **v3.2-3B (+ -SSD)**, Llama-v3-ELYZA-JP-8B, Llama3-TAIDE-8B, Llama-SEA-LION-v3.5-8B-R · **Gemma-4-E2B-it / E4B-it** · Mistral-7B-Instruct-v0.3, **Ministral-3-3B-Instruct-2512** · Falcon3-7B-Instruct · **GPT-OSS-20B** · IBM-Granite-v3.1-8B, **Granite-4.0-Micro** · JAIS-6p7b-Chat · IndusQ-1.1B · PLaMo-1B · plus BERT-family encoders (Albert, BERT, DistilBERT, Electra, MobileBERT).

### Measured throughput — Snapdragon X Elite CRD, NPU (= Dragonwing IQ-X7181)

**`geniex_qairt` — pre-compiled QAIRT NPU bundles, w4a16, ctx 4096** *(fastest path)*
| Model | decode tok/s | prefill tok/s | TTFT (min–max) |
|---|---|---|---|
| **Qwen3-0.6B** | **82.9** | **4252.6** | **30.1 – 963 ms** |
| **Llama-3.2-1B-Instruct** | **43.8** | 2112.2 | 60.6 – 1939 ms |
| **Qwen3-1.7B** | **42.2** | 617.7 | 51.8 – 1658 ms |
| **Qwen3-4B** | 21.8 | 1310.1 | 97.7 – 3126 ms |
| **Llama-3.2-3B-Instruct** | 19.7 | 977.1 | 131 – 4192 ms |
| Llama-3.2-1B (w4, not w4a16) | 19.7 | 986.1 | 129.8 – 4154 ms |
| Llama-3.2-3B (w4) | 8.9 | 473.5 | 270 – 8650 ms |

**Old `genie` runtime, same models/precision:** Llama-3.2-3B **12.1** tok/s, Qwen3-4B **17.5** tok/s, Llama-3.2-1B **24.2** tok/s, Qwen2.5-VL-7B **4.9** tok/s.
→ **GenieX is 1.6–2.6× faster than Genie on identical models.** Use GenieX.

**`geniex_llamacpp` — GGUF q4_0 from Hugging Face, compute-unit selectable**
| Model | ctx | NPU decode | GPU decode | CPU decode | NPU prefill | CPU prefill |
|---|---|---|---|---|---|---|
| Qwen3-0.6B | 512 | 43.0 | 72.5 | **70.2** | **1239.8** | 927.6 |
| Qwen3.5-0.8B | 512 | 30.0 | 63.0 | **64.7** | 506.7 | **1012.3** |
| Qwen3.5-0.8B | 4096 | 28.4 | 48.8 | **51.5** | 497.7 | **598.4** |
| Qwen3.5-2B | 512 | 22.0 | 33.8 | **32.8** | **404.4** | 382.8 |
| Gemma-4-E2B-it | 512 | 18.7 | 20.0 | **27.3** | **567.5** | 360.1 |
| Phi-4-Mini-Instruct | 512 | 16.0 | 27.1 | **28.0** | **508.5** | 313.6 |
| Qwen3-4B | 512 | 12.5 | 22.7 | **22.9** | **345.4** | 171.7 |
| Qwen3-4B | 4096 | 7.7 | 5.7 | **10.6** | **222.0** | 88.7 |
| Granite-4.0-Micro | 4096 | 11.1 | 24.7 | **25.3** | **345.8** | 248.2 |

**Non-obvious, quotable insight:** on X Elite's 12 Oryon cores, **llama.cpp CPU decode frequently beats NPU decode** (memory-bandwidth-bound autoregressive step), while **NPU prefill is 1.3–2.5× faster than CPU** (compute-bound). For an *agentic* workload like ours — long system prompt + event context, short reply — prefill dominates, so **NPU is the right choice and the win is larger than a naive tok/s comparison suggests**. Best of all: `geniex_qairt` w4a16 Qwen3-0.6B does **4252 tok/s prefill / 82.9 tok/s decode / 30 ms TTFT**, i.e. ~9× the llama.cpp NPU prefill. Measure and show all three (CPU / NPU-GGUF / NPU-QAIRT) on one chart — that single chart is worth a lot of the 40 technical points.

### Genie SDK requirements (if you go the raw-Genie route instead of GenieX)
* Hexagon **v73 or newer** (X Elite = v73 ✅, X2 Elite = v81, RB3 Gen 2 = v68 ❌).
* **≥12 GB RAM for 3B-class**, **≥16 GB for 7B+ or 4096 ctx**.
* Android 15+ / Windows 11; **QAIRT SDK v2.29.0+** installed on target (match the version on the model card — assets here are 2.45.0).
* Windows PowerShell env: `$env:Path += "$QAIRT_HOME\bin\aarch64-windows-msvc"`, `...\lib\aarch64-windows-msvc`, and **`$env:ADSP_LIBRARY_PATH = "$QAIRT_HOME\lib\hexagon-v73\unsigned"`** (v73 for X Elite, v81 for X2 Elite).
* Sample apps: `apps/chatapp_windows_cpp` (C++, Genie SDK), `apps/chatapp_android` (Java/C++).

---

## 12. VLMs / image captioning / multimodal

| Model | Runtime | X Elite decode tok/s | X Elite prefill tok/s | TTFT | Notes |
|---|---|---|---|---|---|
| **Qwen3-VL-2B-Instruct** | geniex_llamacpp q4_0, ctx512 | **24.3 NPU** / 21.2 CPU | 797.5 NPU | 161–642 ms | smallest VLM; best fit for "describe this snapshot" |
| **Qwen3-VL-4B-Instruct** | **geniex_qairt w4a16, ctx4096** | **20.9** | **1280.0** | 100 – 3200 ms | best quality/latency balance on X Elite |
| Qwen3-VL-4B-Instruct | geniex_llamacpp q4_0, ctx512 | 11.5 NPU / 21.9 CPU | 341.3 NPU | 375–1500 ms | |
| **Qwen2.5-VL-7B-Instruct** | geniex_qairt w4a16, ctx2048 | 12.5 | 855.0 | 150 – 2395 ms | needs 16 GB; `genie` runtime only 4.9 tok/s |
| **Qwen3-VL-8B-Instruct** | in catalog | — | — | — | |
| **Gemma-4-E2B-it / E4B-it** | multimodal, geniex_llamacpp | 18.7 (E2B, NPU, ctx512) | 567.5 | 226–903 ms | |
| **OpenAI-Clip** | qnn_dlc float | — | — | **21.473 ms** (X Elite); 20.49 QCS8550; 59.3 IQ-8275 | zero-shot image↔text similarity; **cheapest possible "is this scene dangerous?" scorer** |
| **EasyOCR** (det + rec) | onnx | — | — | **58.3 ms** float (38.158 + 20.124); w8a8 det 13.5 ms | read medication labels / signage |
| **TrOCR** | in catalog | | | | handwriting |
| **Nomic-Embed-Text**, **MiniLM-v2** | in catalog | | | | RAG / semantic event memory embeddings |
| **SAM2 / SAM3 / EdgeTAM / MobileSam / FastSam-S/X** | | | | | segmentation; `apps/sam3_segmentation_windows_py` sample exists |
| **Track-Anything** | | | | | video object tracking |

**No LLaVA and no Florence-2 in the catalog** — Qwen3-VL is the replacement, and it's better. GenieX supports VLMs directly: `geniex infer <model>` accepts an image by absolute path.

**Design recommendation:** two-tier vision-language. **CLIP (21.5 ms)** continuously scores a small fixed set of natural-language hazard prompts on the snapshot (open-vocabulary, config-driven, 50× cheaper than YOLO-WORLD's detector); only when CLIP crosses threshold do you spend **Qwen3-VL-4B (TTFT 100 ms–3.2 s)** to generate the human-readable narrative that goes to the caregiver and drives the agent's tool choice. That's a clean, measurable, defensible cascade.

---

## 13. Runtime deep dive

### ONNX Runtime QNN Execution Provider (the Windows path)
* `pip install onnxruntime-qnn` — **QNN SDK deps are bundled since ORT 1.18.0**. Workbench currently pairs **ORT 1.26.0 + QNN EP 2.2.0** (published assets used ORT 1.27.1).
* **Python 3.11.x**; NumPy 1.25.2 or ≥1.26.4.
* **ARM64 Windows Python required for NPU inference.** x64 quantization tooling only (`qnn_preprocess_model()`, `get_qnn_qdq_config()`) — these run on x86_64, and context binaries can even be *generated* on an x64 machine without HTP hardware.
* Backends: **HTP** (default, NPU), GPU (fp, no quantization), CPU (reference).
* **HTP requires QDQ-quantized int8/int16 models with static shapes.** No dynamic shapes, no unsupported ops. Recommended QDQ config: **uint8 weights + uint16 activations**.
* Provider options worth setting: `backend_path="QnnHtp.dll"`, **`htp_performance_mode="burst"`** (for latency demos) vs `"balanced"`/`"low_power"` (for the energy slide — *show both*), `htp_graph_finalization_optimization_mode=0..3`.
* Session options for cold start: **`ep.context_enable="1"`, `ep.context_file_path=...`, `ep.context_embed_mode="1"`** → serializes a QNN context binary so subsequent launches skip graph finalization. **This is your "app opens instantly" story for the 20-pt Deployment criterion — cache context binaries at install time, not first run.**

### LiteRT / TFLite + QAIRT delegate (the Dragonwing/Linux path)
* On Dragonwing Linux, Qualcomm's own sample apps run the **QAIRT TFLite delegate on the NPU** inside Docker.
* Host prerequisites (from the sample READMEs) — memorize these:
  ```bash
  sudo apt-add-repository -y ppa:ubuntu-qcom-iot/qcom-ppa
  sudo apt-get update
  sudo apt-get install qcom-fastrpc1 qcom-fastrpc-dev
  sudo apt-get install qcom-camera-server     # for built-in camera on RB3
  # reboot
  ```
* **⚠️ Do not use TFLite for 3D-conv / transformer-heavy models** — measured fallbacks to CPU/GPU with 20–100× penalties (ResNet-3D tflite 1264–9128 ms; Distil-Whisper encoder tflite 3107 ms on GPU; EasyOCR recognizer tflite lands on CPU at 141–174 ms).
* `.tflite` and `.onnx`/`.dlc` assets are **universal** (chipset-agnostic) for most CV models — download once, run anywhere.

### QNN asset flavors — when to use which
| Flavor | Portable across chipsets? | Portable across QAIRT versions? | Cold start | Best for |
|---|---|---|---|---|
| `onnx` | ✅ | ✅ | slow (graph finalization) | dev iteration, Windows default |
| `qnn_dlc` | ✅ | ✅ | medium | ship-once-run-everywhere |
| `qnn_context_binary` | ❌ SoC-specific | ❌ | **fastest** | the shipped EXE, generated at install |
| `precompiled_qnn_onnx` | ❌ SoC-specific | ❌ | fast | ORT integration with baked context |

### Qualcomm IM SDK (GStreamer) — direct hit for your team's expertise
**88 of the 237 models carry `imsdk_supported: true`** in their manifests, i.e. they're wired into the Qualcomm **Intelligent Multimedia SDK** GStreamer plugin set. Ones relevant to us: `yamnet`, `hrnet_pose`, `posenet_mobilenet`, `face_det_lite`, `foot_track_net`, `gear_guard_net`, `midas`, `depth_anything(_v2)`, `yolov8_det`, `yolov11_det`, `yolo26_det`, `yolox`, `yolo_world`, `rf_detr`, `detr_resnet50`, `rtmdet`, `easyocr`, `deeplabv3_plus_mobilenet`, `ffnet_*`, `segformer_base`, `video_mae`. Sample GStreamer apps: **`apps/posenet_ubuntu_py`** (GStreamer + OpenCV + LiteRT, multi-person pose on a live camera) and **`apps/mediapipe_hand_gesture_ubuntu_py`**. Start from `posenet_ubuntu_py` for the edge node — it is literally the app you were going to write.

---

## 14. "QUAD framework for GGUF on Qualcomm" — resolved as **GenieX**

**No public artifact named "QUAD" exists** (no repo, no doc, no package under that name; GitHub code search across `org:quic` and `quic/ai-hub-models` returns nothing). If it is an internal codename, the public, shipping, BSD-3-licensed thing that does exactly what you described is:

### GenieX — `github.com/qualcomm/geniex` · docs `geniex.aihub.qualcomm.com` · status: **Developer Preview**
> "GenieX is an on-device Gen AI inference runtime for Qualcomm devices. Bring almost any GGUF model from Hugging Face — or a pre-compiled bundle from Qualcomm AI Hub — and run it locally on the **Hexagon NPU, Adreno GPU, or CPU**… **It is the community version of Qualcomm GENIE.**"

| Aspect | Detail |
|---|---|
| Platforms | **Windows ARM64** (X / X Elite / X2 Elite), Android (8 Elite, 8 Elite Gen 5), **Linux ARM64** (Dragonwing QCS9075) |
| Two runtimes | `llama_cpp` — any GGUF from HF/Docker Hub, GGML over CPU/GPU/**Hexagon HTP kernels**; `qairt` — pre-compiled AI Hub bundle, **NPU only** |
| Interfaces | CLI · **Python (`pip install geniex`)** · Kotlin/Java (`com.qualcomm.qti:geniex-android:0.3.1`) · **C SDK (`sdk/include/geniex.h`)** · Docker (`docker.io/qualcomm/geniex`) · **OpenAI-compatible HTTP server** |
| Install (Windows) | download the installer from GitHub Releases, open a new terminal. Linux: `curl -fsSL …/qai-hub-geniex/install.sh \| sh` (no sudo) |
| Key CLI | `geniex pull` (`--model-hub aihub\|hf\|localfs`, `--local-path`) · `geniex infer <model> [image]` · **`geniex serve` → `http://127.0.0.1:18181/v1`** · `geniex list/remove/clean` |
| Key flags | **`--compute npu\|gpu\|cpu`** (llama.cpp only; AI Hub bundles are NPU-only and error otherwise) · `--nctx` (default 4096) · `--max-tokens` (2048) · `--ngl` · `--temperature/--top-p/--top-k/--min-p/--repetition-penalty/--seed` · **`--enable-json`** (constrained output) · **`--think` / `--think=false`** |
| Precisions | GGUF: **`Q4_0` = best Hexagon NPU support** (Q8_0/F16/Q4_K_M/Q5_K_M are GPU/CPU only). QAIRT: `w4a16` (most common) or `w4` (higher accuracy) |
| VLM | supported; pass an image by absolute path |

### Why this is the single most important find for QNet Home
1. **`--enable-json` gives you constrained/structured output natively** → reliable tool-calling from a 0.6B–4B model without a fragile parser. This is exactly what an agentic orchestrator needs.
2. **`geniex serve` is OpenAI-compatible** → OpenClaw (or any OpenAI SDK client) points at `http://127.0.0.1:18181/v1` with **zero code changes**, and you get NPU acceleration for free. No custom QNN integration work on your critical path.
3. **One installer + one `geniex pull`** is a *very* strong answer to the 20-pt "ease of install" criterion, and it's a Qualcomm-first-party component (good optics in a Qualcomm-internal hackathon).
4. **`--compute npu|gpu|cpu` on the same GGUF** is a free, built-in A/B harness: run the identical model on CPU vs GPU vs NPU, chart tok/s and Watts. That is a ready-made technical-implementation slide.
5. Risk to note: **Developer Preview**. Pin the release you test with, vendor the installer into your submission, and keep a `--compute cpu` fallback path.

---

## 15. Qualcomm Cloud AI 100 (AIC100) — the fourth tier

Path: **`github.com/quic/efficient-transformers`** (the `QEfficient` library).
* Converts HuggingFace models → inference-optimized form for **Qualcomm Cloud AI AI100 / AI200**.
* **100+ models**: Llama 3.x/4, Mistral, Qwen 2.5/3.x, Gemma, Phi, Granite, CodeGemma; MoE (Mixtral); quantized **AWQ/GPTQ/FP8**; **VLMs** (InternVL, Llava, Mllama); audio (wav2vec2); diffusion (FLUX, WAN 2.2); embeddings; **GGUF format support**.
* API shape: `QEFFAutoModelForCausalLM.export()` → ONNX → `qaic` compile; PyTorch-vs-device validation built in; QNN compilation for multi-model and embedding models; ONNX Runtime compatible.
* Advanced features that make good slide bullets: **speculative decoding** (draft-based + post-attention projections), **SwiftKV**, continuous & non-continuous batching, **disaggregated serving**, separate prefill/decode compilation for encoder-decoder, finetuning with gradient checkpointing.
* Requires the "Cloud AIxxx Apps SDK" on the host (version not published in the README). **No benchmark numbers in the repo** — measure your own.

**How to use AIC100 in QNet Home without it looking bolted on.** The theme is *multi-device orchestration*, so the honest, defensible role for AIC100 is the **offline / batch / cold tier** that the on-device tier deliberately doesn't do:
* **Nightly semantic digest.** Ship only the day's *event log* (text/JSON, no media) to AIC100 and have a big model (Qwen3-8B / Llama-3.1-8B) produce a weekly caregiver report, trend detection, and personalized threshold tuning. Privacy story stays intact — only semantic events cross the boundary, which is the same invariant as node→hub.
* **Escalation-only "second opinion."** When the local SLM is below a confidence threshold *and* the user has consented for that incident, escalate the (text) situation summary to the cloud model. Log every escalation.
* **Voice-enrollment / model-prep jobs** at setup time (§8 fallback 3).
* **Design the boundary as a first-class artifact:** a single `EscalationPolicy` with an explicit data-minimization contract (what fields, what retention, what consent) + a counter on the dashboard showing "0 media bytes left the home today." That converts a "we also used the cloud accelerator" checkbox into an architectural argument.

---

## 16. Recommended model stack for QNet Home

### Tier 1 — UNO Q edge node (CPU only, ≤4 GB RAM, GStreamer)
| Job | Model | Size | Why |
|---|---|---|---|
| Sound events (always on) | **YamNet** w8a8 tflite | 14 MB → ~4 MB int8 | only audio classifier; ~0.96 s hop; reference GStreamer-adjacent app exists |
| Presence / consent gate | **face_det_lite** w8a8 | **965 KB** | 0.44 ms on NPU-class HW; tiny enough for A53 CPU; used to *blur*, not identify |
| Pose (if node-side vision needed) | **MediaPipe-Pose** (det + landmark) | 16 MB total float | smallest full pose pipeline; single-person |
| Alternative pose | **LiteHRNet** | **4.49 MB** | smallest keypoint model at 58.0 mAP, but top-down (needs detector) |
| Transport | semantic events only (JSON over MQTT/WS) | — | zero pixels leave the room |

### Tier 2 — Snapdragon X Elite hub (NPU, ORT QNN / QAIRT / GenieX)
| Job | Model | X Elite latency | Precision |
|---|---|---|---|
| Multi-person pose (continuous) | **Posenet-Mobilenet** | **0.563 ms** | w8a8 (45.3 mAP) |
| or single-stage pose+person | **YOLOv11-Pose** | 5.176 ms | w8a16 |
| High-accuracy pose (on trigger) | **HRNetPose** | **1.112 ms** | w8a8 (68.3 mAP, −0.3 vs float) |
| Object / hazard detection | **YOLOv11-Det** | 4.609 ms | **w8a16** (45.8 mAP) — *not* w8a8 (37.3) |
| Open-vocab hazards (on demand) | **YOLO-WORLD** | 109.8 ms + 264.7 ms text (cached) | float |
| Depth / floor-plane fall prior | **Midas-V2** | **1.332 ms** | w8a8 (δ1 88.0, −0.1) |
| Action confirmation | **ResNet-3D** | **22.394 ms** | w8a8 (**70.0 Top-1 = float**) — onnx/dlc only |
| Face presence (privacy gate) | **face_det_lite** | 0.436 ms | w8a8 |
| Sound events | **YamNet** | **0.097 ms** | w8a8 |
| **Streaming ASR (conversation)** | **Zipformer** | **9.7 ms / 0.71 s chunk (~73× RT)** | float |
| Batch ASR (logs) | **Whisper-Base** | 49.0 ms enc + 3.7 ms/tok | float |
| **Agent / orchestrator LLM** | **Qwen3-0.6B** via `geniex_qairt` | **82.9 tok/s, 4253 prefill, 30 ms TTFT** | w4a16 |
| Better reasoning if needed | **Qwen3-1.7B** / **Llama-3.2-1B** | 42.2 / 43.8 tok/s | w4a16 |
| Scene narration (on trigger) | **Qwen3-VL-4B** via `geniex_qairt` | 20.9 tok/s, 1280 prefill, TTFT 100 ms–3.2 s | w4a16 |
| Cheap open-vocab scene scoring | **OpenAI-Clip** | **21.473 ms** | float qnn_dlc |
| Read labels / signage | **EasyOCR** | 58.3 ms | float (w8a8 det 13.5 ms) |
| TTS | **PiperTTS-EN** ≈61.5 ms *(voice_ai)*, MeloTTS-EN ≈262 ms | | ⚠️ verify Voice AI SDK; SAPI fallback |
| Event memory / RAG | Nomic-Embed-Text or MiniLM-v2 | | |

**Always-on budget on X Elite:** YamNet 0.097 + Posenet 0.563 + Midas 1.332 + face_det_lite 0.436 = **2.43 ms per frame-tick**. At 30 fps that's **7.3 % of one NPU's wall-clock**, leaving ~92 % headroom for the LLM/VLM/TTS tiers. **Put that number on a slide.**

### Tier 3 — Android phone
It *is* an AI Hub target with a real HTP. Cite Samsung Galaxy S25 rows (e.g. Posenet w8a8 **0.316 ms**, MediaPipe-Pose w8a8 **0.385 ms** total, YOLOv11-Pose float **2.61 ms**) if you add phone-side inference. Also serves as the caregiver client.

### Tier 4 — AIC100
Nightly digest / escalation-only second opinion / enrollment jobs, via `QEfficient` (§15).

---

## 17. Gotchas, risks, and the energy-measurement plan

**Hard blockers / verify Day 1**
1. **Qualcomm Voice AI SDK availability** — TTS on X Elite ships as `voice_ai` only. Wire a Windows SAPI fallback behind an interface *before* you depend on it.
2. **Voice cloning does not exist in the catalog.** Re-frame per §8 or move it off the critical path.
3. **UNO Q has no NPU/GPU compute.** CPU-only. Do not promise NPU numbers for the edge node.
4. **x64 vs ARM64 Python on X Elite** — two venvs, Day 1 (§3).
5. **GenieX is Developer Preview** — pin a release, vendor the installer, keep `--compute cpu` fallback.
6. **Genie needs Hexagon v73+ and 12–16 GB RAM.** X Elite qualifies; RB3 Gen 2 (v68) does not.

**Performance traps (each one is also a slide)**
7. **TFLite is a trap for 3D convs & transformers** — 20–100× slowdowns from CPU/GPU fallback. Use `onnx`/`qnn_dlc`.
8. **`qnn_dlc` can be *slower* than `onnx`** for some quantized models (Depth-Anything w8a16: 137.8 ms dlc vs 27.7 ms onnx). Always profile both.
9. **w8a8 accuracy cliff on detectors** (YOLOv11 −8.9 mAP) but not on pose/depth/action. Use `w8a16` or `w8a8_mixed_int16` for detection.
10. **Whisper-Large-V3-Turbo peaks at 1677 MB** on the precompiled path on X Elite. Whisper-Base is 90.7 + 187 MB.
11. **Whisper's 30 s window kills conversational latency.** Use Zipformer for the live loop.
12. **YOLOv8/v11 are AGPL-3.0** with `restrict_model_sharing: true`. For a Qualcomm-internal demo this is likely fine, but if anything gets open-sourced, prefer **YOLO26-Det** (47.7 mAP) or **Yolo-X** or the BSD-3 Qualcomm-authored `face_det_lite` / `foot_track_net` / `gear_guard_net`.
13. **TorchScript compilation is deprecated** on Workbench (2026-06-22) → use `.pt2` ExportedProgram.

**Energy efficiency: AI Hub gives you nothing — so own it**
`perf.yaml` contains only `inference_time_milliseconds`, `estimated_peak_memory_range_mb`, `layer_counts`, `primary_compute_unit`. **There is no energy or power field anywhere in the catalog.** Since the 40-pt rubric explicitly names energy efficiency, a self-measured number is nearly free differentiation:
* Sweep ORT QNN **`htp_performance_mode`** across `burst` / `balanced` / `low_power` (and `htp_graph_finalization_optimization_mode` 0–3) and report latency **and** energy at each point — a real Pareto curve, not a single number.
* Use GenieX's **`--compute npu|gpu|cpu`** on one identical GGUF to produce a 3-bar CPU-vs-GPU-vs-NPU energy chart. Nobody else will do this.
* Measurement options on Windows on ARM: `powercfg /batteryreport` and `powercfg /srumutil` (SRUM per-process energy), Windows `EnergyEstimationEngine` counters, HWiNFO/`pcm`-style rails if exposed, or the crude-but-effective **battery-drain-per-1000-inferences** with the charger unplugged and screen brightness pinned. Report **mJ per inference** and **inferences per Wh** — those units read as engineering, not marketing.
* Bonus framing: the whole architecture *is* an energy argument. "No video streams leave the room" also means "no H.264 encode + Wi-Fi TX per frame per node." Measure the node's power with and without video streaming to quantify the privacy-architecture's energy dividend. That's a genuinely novel number.

---

## 18. Sources

**Qualcomm AI Hub / models**
- https://aihub.qualcomm.com/ · https://aihub.qualcomm.com/models · https://aihub.qualcomm.com/iot/models
- https://github.com/quic/ai-hub-models (→ https://github.com/qualcomm/ai-hub-models), README + `src/qai_hub_models/devices_and_chipsets.yaml` + per-model `manifest.yaml` / `perf.yaml` / `numerics.yaml` / `release-assets.yaml` (v0.59.0, 2026-07-28)
- https://github.com/quic/ai-hub-models/blob/main/cli/README.md
- https://github.com/qualcomm/ai-hub-apps — app directory (Windows/Android/Ubuntu), incl. `apps/posenet_ubuntu_py`, `apps/yamnet_ubuntu_py`, `apps/whisper_windows_py`, `apps/chatapp_windows_cpp`, `apps/sam3_segmentation_windows_py`
- https://github.com/qualcomm/ai-hub-apps/tree/main/tutorials/llm_on_genie · https://github.com/qualcomm/ai-hub-apps/tree/main/tutorials/geniex
- https://workbench.aihub.qualcomm.com/docs/hub/release_notes.html
- https://workbench.aihub.qualcomm.com/docs/hub/compile_examples.html
- https://workbench.aihub.qualcomm.com/docs/hub/devices.html · .../generated/qai_hub.get_devices.html · .../generated/qai_hub.submit_compile_job.html
- Model pages: https://aihub.qualcomm.com/models/hrnet_pose · /litehrnet · /mediapipe_pose · /yamnet · /melotts_en · /pipertts_en · /zipformer · /resnet_3d · /midas · /depth_anything_v2 · /face_det_lite · /foot_track_net · /yolo_world · /openai_clip · /qwen3_0_6b · /qwen3_4b · /qwen3_vl_4b_instruct · /llama_v3_2_3b_instruct
- Hugging Face mirrors (being deprecated in favor of aihub): https://huggingface.co/qualcomm/MediaPipe-Pose-Estimation · https://huggingface.co/qualcomm/HRNetPose · https://huggingface.co/qualcomm/YamNet

**GenieX**
- https://github.com/qualcomm/geniex · https://geniex.aihub.qualcomm.com/ · https://geniex.aihub.qualcomm.com/en/models/supported · https://geniex.aihub.qualcomm.com/en/run/cli/reference · https://geniex.aihub.qualcomm.com/en/run/cli/local-server

**Runtimes / SDKs**
- https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- https://softwarecenter.qualcomm.com/catalog/item/Qualcomm_AI_Runtime_Community · https://qpm.qualcomm.com/#/main/tools/details/Qualcomm_AI_Runtime_SDK
- https://docs.qualcomm.com/bundle/publicresource/topics/80-63442-50/overview.html#supported-snapdragon-devices

**Cloud AI 100**
- https://github.com/quic/efficient-transformers

**Arduino UNO Q / QRB2210**
- https://docs.arduino.cc/hardware/uno-q/ · https://www.arduino.cc/product-uno-q/ · https://store-usa.arduino.cc/products/uno-q
- https://www.qualcomm.com/developer/hardware/arduino-uno-q · https://www.qualcomm.com/developer/blog/2026/05/the-arduino-uno-q-board--unpack-the-dual-brain-power-for-next-ge
- https://docs.qualcomm.com/doc/87-61720-1/87-61720-1_REV_D_Qualcomm_Dragonwing_QRB2210_Processor_Product_Brief.pdf · https://www.qualcomm.com/internet-of-things/products/q2-series/qrb2210
- https://forum.arduino.cc/t/ai-inference-on-uno-q-adreno-702-gpu-without-app-lab/1449276 (no Adreno OpenCL driver; `QNN_BACKEND_ERROR_CANNOT_INITIALIZE`)
- https://forum.arduino.cc/t/bug-report-installing-hexagonrpcd-causes-boot-instability-shell-hangs-on-arduino-uno-q-qrb2210/1449187 (FastRPC/RFSA breakage)
- https://linuxgizmos.com/arduino-uno-q-combines-qualcomm-dragonwing-qrb2210-and-stm32-mcu/
- https://docs.arduino.cc/software/app-lab/integrations/ai-models/ · https://blog.arduino.cc/2026/04/29/arduino-app-lab-0-7-custom-bricks-are-here/ · https://github.com/arduino/app-bricks-examples
- https://www.edge-ai-vision.com/2026/07/the-arduino-uno-q-board-unpack-the-dual-brain-power-for-next-gen-edge-ai/
