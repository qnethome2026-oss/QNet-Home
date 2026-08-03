# Local AI Inference Stack on Snapdragon X Elite (Windows on ARM) — Aug 2026

**Research date:** 2026-08-03 · **Audience:** QNet Home hackathon team · **Optimizing for:** Judging criterion "Technical Implementation 40 pts (resource utilization, optimization, latency/performance, energy efficiency)" + "Deployment & Accessibility 20 pts (packaged .EXE/.MSIX)"

> Everything marked **[verified on our machine]** was executed live on the dev kit during this research, not read from docs.

---

## 0. TL;DR — Recommended stack

| Layer | Pick | Why |
|---|---|---|
| **LLM orchestrator brain** | **Qwen3-4B-Instruct-2507** via **GenieX** (`qairt` runtime, w4a16, NPU) — **23.1 tok/s, TTFT 0.098–3.15 s** on X Elite | Fastest 4B-class NPU path that exists today on X Elite; OpenAI-compatible local server in one command; ships as a signed Windows ARM64 installer |
| **Fast reflex model** (event triage, classification, routing) | **Qwen3-1.7B** (42.2 tok/s) or **Qwen3-0.6B** (82.9 tok/s, TTFT 30 ms) on NPU | Sub-100 ms TTFT makes "instant" responses possible; use as a router in front of the 4B |
| **VLM (snapshot reasoning)** | **Qwen3-VL-4B-Instruct** via GenieX `qairt` — **20.9 tok/s** NPU (vs **7.6 tok/s** on llama.cpp-Hexagon → **2.75× win** for QAIRT) | Only needs a single JPEG from the edge node; keeps "no video leaves the room" story intact |
| **STT** | **Windows AI Speech Recognition API** (Windows App SDK, preinstalled NPU model, zero download) as primary; **AI Hub Whisper-Base** via `qai-hub-apps fetch whisper_windows_py` as the "we measured it" fallback | Windows API is free/instant/streaming; Whisper-Base gives publishable NPU numbers (encoder 49.0 ms, decoder 3.7 ms per step) |
| **TTS (normal voice)** | **Kokoro-82M ONNX** (`kokoro-onnx`, ARM64 wheel OK) or **Piper** (GPL-3 now — check license) on CPU | Windows' built-in voices on this box are only legacy David/Zira/Mark **[verified]** — unusable for a demo |
| **TTS (parent's cloned voice)** | **Chatterbox-Nano** (110M, MIT, zero-shot clone from ~10 s reference, "3× faster than realtime on 8 CPU cores") on torch-CPU ARM64 | The only credible zero-shot cloner that runs real-time on Oryon CPU; MIT license lets us ship it |
| **Event/audio classifier on edge nodes** | **YamNet** (AudioSet, 521 classes) — **0.097 ms/inference** w8a8 on X Elite NPU | Glass-break/scream/fall-thud detection; also runs on Dragonwing |
| **Pose (fall detection)** | **MediaPipe-Pose** — detector **0.307 ms** + landmark **0.292 ms** w8a8 on X Elite NPU | 0.6 ms total per frame → >1000 fps headroom; enormous "resource utilization" talking point |
| **NPU utilization proof** | `Get-Counter '\GPU Engine(*luid_<npu>*engtype_Compute)\Utilization Percentage'` **[verified working]** + `wpr -start NeuralProcessing` **[verified present]** | Live per-PID NPU % in a PowerShell one-liner — a killer live-demo widget |
| **Energy proof** | `Get-CimInstance -Namespace root\wmi BatteryStatus` → `DischargeRate` (mW) **[verified]** + `powercfg /srumutil /csv` (needs elevation) + `powercfg /batteryreport` | Report **mW during inference** and **tokens per joule**, NPU vs CPU |
| **Packaging** | PyInstaller **6.21.0 win_arm64 wheel [verified available]** → `.exe`, then MSIX via `makeappx.exe` + `signtool.exe` from **Windows SDK 10.0.26100.0 arm64 [verified present]** | Both requirements (EXE and MSIX) satisfiable with tooling already on the box |
| **Agent framework** | **OpenClaw** (Node/TS, MIT) pointed at `http://127.0.0.1:18181/v1` | GenieX's own docs name OpenClaw as a supported client — free credibility |

**Headline numbers to put on a slide:**
- Orchestrator LLM: **23 tok/s, ~100 ms TTFT, on NPU, 0 W of GPU**
- Pose estimation: **0.6 ms/frame** on NPU (detector + landmark, w8a8)
- Audio event classification: **0.097 ms/inference**
- Whisper-Base ASR encoder: **49 ms per 30 s window** = **~600× realtime**
- Self-speculative decoding on Llama-3.2-3B: **19.73 → 31.70 tok/s = +61 %** with bit-identical output

---

## 1. Verified baseline of our dev kit

**[verified on our machine, 2026-08-03]**

| Property | Value |
|---|---|
| CPU | `Snapdragon(R) X Elite - X1E80100 - Qualcomm(R) Oryon(TM) CPU` |
| Arch | ARM64 (`PROCESSOR_ARCHITECTURE=ARM64`) |
| Chassis | Dell Latitude, battery `DELL RXF9T487` |
| RAM | 31.6 GB (enough for the 16 GB-class 4B/8B bundles) |
| OS | Windows 11 build **10.0.26200.0** (25H2 class) |
| NPU device | PnP class **`ComputeAccelerator`**, name `Snapdragon(R) X Elite - X1E80100 - Qualcomm(R) Hexagon(TM) NPU`, status OK |
| NPU driver | **30.0.219.1000** (2025-11-08) — comfortably above the **30.0.140.0** minimum the Windows ML QNN EP requires |
| Hexagon arch | **v73** (X Elite = v73; X2 Elite = v81) |
| Python | **3.12.10, native ARM64** |
| Node | **v22.20.0, arm64** |
| .NET SDK | **not installed** (only runtime bits) — install if we want C#/WinUI |
| Visual Studio | **2022** installed |
| Windows SDK | 10.0.26100.0 with **arm64** `makeappx.exe` and `signtool.exe` present |
| winget | present; `Microsoft.FoundryLocal` **0.10.2.0** available |
| Already installed | **Ollama 0.32.5** (no models pulled) |
| TTS voices | only `Microsoft David/Zira Desktop` (SAPI) + `MSTTS_V110_enUS_{DavidM,MarkM,ZiraM}` (OneCore) — **legacy, robotic** |
| WPR profiles | `CPU`, `GPU`, **`NeuralProcessing`** all present |
| powercfg | `/ENERGY`, `/BATTERYREPORT`, `/SLEEPSTUDY`, `/SRUMUTIL` all present |

**Python wheel availability on win_arm64 [verified via `pip install --dry-run`]:**

| Package | ARM64 status |
|---|---|
| `onnxruntime` | ✅ 1.28.0 `cp312-win_arm64` |
| `onnxruntime-qnn` | ✅ **2.4.0** `cp312-win_arm64` (57 MB), released 2026-07-14 |
| `onnxruntime-genai` | ✅ 0.15.1 `cp312-win_arm64` |
| `onnxruntime-genai-winml` | ✅ 0.15.1 `cp312-win_arm64` |
| `foundry-local-sdk-winml` | ✅ 1.2.4 (pure py) |
| `qai-hub-models` | ✅ 0.59.0 · `qai-hub-apps` ✅ 0.33.0 |
| `numpy` | ✅ 2.5.1 win_arm64 · `soundfile` ✅ · `sounddevice` ✅ 0.5.5 win_arm64 |
| `silero-vad` | ✅ 6.2.1 (ONNX-based) · `misaki` ✅ (Kokoro G2P) · `kokoro-onnx` ✅ 0.5.0 |
| `pyinstaller` | ✅ **6.21.0 `py3-none-win_arm64`** |
| `olive-ai` | ✅ 0.13.0 |
| **`torch`** | ❌ **not on PyPI for win_arm64** — ✅ **available as `torch-2.13.0+cpu-cp312-cp312-win_arm64.whl` from `--index-url https://download.pytorch.org/whl/cpu`** |
| **`ctranslate2`** | ❌ no win_arm64 → **`faster-whisper` is unusable** |
| **`opencv-python` / `-headless`** | ❌ sdist only (5.0.0.93, 82 MB) and the source build **fails** on ARM64 → use GStreamer / `Pillow` / `imageio`, or pin an older OpenCV, or do vision on the edge nodes |
| `nuitka` | sdist only (compiles with VS2022) |
| `piper-tts` | sdist 1.6.0 (needs espeak-ng build) — risk |

> **Planning consequence:** on Windows-on-ARM, treat the Python stack as **ONNX Runtime-first**. Anything that assumes PyTorch-from-PyPI, CTranslate2, or `opencv-python` wheels will burn half a day. The one PyTorch escape hatch is the `download.pytorch.org/whl/cpu` index (needed for Chatterbox voice cloning).

---

## 2. Running LLMs/SLMs locally — the five real paths

### 2.1 GenieX (Qualcomm) — **the recommended path** ⭐

**What it is:** `github.com/qualcomm/GenieX` — "the community version of Qualcomm GENIE." An on-device GenAI inference runtime for Snapdragon only. BSD-3-Clause. Developer preview but *extremely* active: **8,294 stars, latest release v0.3.18 on 2026-07-31, repo updated the day of this research**. Docs: <https://geniex.aihub.qualcomm.com/>.

**Architecture:** one C SDK → CLI, Python (`pip install geniex`), Kotlin/Java, Docker, and an **OpenAI-compatible HTTP server**. It dispatches to **two runtimes**:

| | `llama_cpp` | `qairt` (Qualcomm AI Engine Direct) |
|---|---|---|
| Models | any GGUF from Hugging Face / Docker Hub `docker.io/ai/*` | pre-compiled per-chipset bundles from Qualcomm AI Hub |
| Compute units | NPU (`HTP0`) / GPU (Adreno OpenCL) / CPU / **`hybrid`** | **NPU only** |
| Precision | you choose (`Q4_0` = only one with good Hexagon support) | baked in (`w4a16` typical, `w4` alternative) |
| Speed | ~2.7× slower on the same model | **fastest NPU path** |

**Install on Windows ARM64:** download `geniex-cli-setup-windows-arm64-v0.3.18.exe` (64.5 MB) from GitHub releases, run it, open a new terminal. **This matters enormously** — see §2.2 for why the raw llama.cpp Hexagon path is a trap.

```powershell
geniex pull ai-hub-models/Qwen3-4B-Instruct-2507
geniex serve                      # -> http://127.0.0.1:18181/v1  (+ built-in Swagger UI at /)
geniex infer ai-hub-models/Qwen3-VL-4B-Instruct --compute npu
```

Useful flags for us (`geniex infer`): `--compute {npu|gpu|cpu|hybrid}`, `--think=false` (kill Qwen3's `<think>` prefix), `--nctx`, `--max-tokens`, `--system-prompt`, **`--grammar-path` / `--grammar-string` (GBNF)**, **`--enable-json`**, `--sliding-window` (qairt: evict oldest context instead of erroring when full — important for a long-running always-on agent), `--seed`.

**Tool calling on the GenieX server** (from its own docs): uses the standard OpenAI `tools` schema. The server parses `<tool_call>…</tool_call>` tags or a fenced ```` ```json ```` block out of the generated text and re-emits proper OpenAI `tool_calls`. Two documented caveats:
- **Only one tool call per assistant turn is parsed** — parallel tool calls are not supported.
- For VLMs (Qwen3-VL), you must (a) prime with a system message spelling out the exact `<tool_call>{...}</tool_call>` shape, and (b) on the follow-up turn **drop `tools=` and drop the image content** so the model doesn't re-invoke the tool or re-run the vision encoder.

The docs explicitly name **LangChain and OpenClaw** as intended clients of `geniex serve`. That is a direct endorsement of our seed architecture.

**`geniex-bench`** — a standalone benchmark binary published per release (`geniex-bench-windows-arm64.zip`, ~84 MB, also a stable "latest" S3 URL). It runs 1 warmup + 3 measured reps per cell across a context-size matrix (512/1024/4096) and emits per-cell JSON with **median/stdev/min/max of TTFT, prefill tok/s, decode tok/s**. **Use this verbatim for our numbers table** — it is Qualcomm's own harness, so judges can't argue with the methodology.

### 2.2 llama.cpp with the Hexagon (HTP) backend — real, but a packaging trap on Windows

Mainline llama.cpp now has a first-party **Hexagon backend** (`ggml/src/ggml-hexagon`, docs at `docs/backend/snapdragon/`), contributed by Qualcomm. It builds `libggml-htp-v73/v75/v79/v81.so` (X Elite = **v73**) and treats each NPU session as a pseudo-GPU device (`HTP0..HTP3`) so `-ngl`, `--device`, and multi-device layer splitting all work. Each Hexagon process domain is capped at **~3.5 GB** of mapping, so >4B models need `GGML_HEXAGON_NDEV=2` (8B) or `4` (20B).

Great built-in instrumentation: `GGML_HEXAGON_PROFILE=1|2` gives per-op µsecs/cycles/PMU counters pipeable into `scripts/snapdragon/ggml-hexagon-profile.py`; `GGML_HEXAGON_VERBOSE=1` logs every offloaded matmul; `GGML_HEXAGON_OPFILTER=<regex>` selectively disables ops (e.g. force FLASH_ATTN_EXT back to CPU) — this is exactly the kind of ablation that scores "optimization."

**❗ The blocker for us:** on Windows on Snapdragon the HTP op libraries must be listed in a `libggml-htp.cat` catalog **signed with a trusted certificate**. If you build it yourself you must:
1. `bcdedit /set TESTSIGNING ON` (**and likely disable Secure Boot**), reboot;
2. `makecert` a self-signed cert, `pvk2pfx` it, import into *Trusted Root CAs* **and** *Trusted Publishers*;
3. set `HEXAGON_HTP_CERT` and rebuild.

That is a non-starter for a **judged .MSIX install-in-one-click** deliverable, and disabling Secure Boot on a loaner laptop is a bad idea. **GenieX solves this for us**: its Windows releases ship a **Microsoft-signed** HTP flavour (`geniex-sdk-windows-arm64-<tag>.zip` = "Microsoft-signed → None — skip to Run"; only a `-selfsigned` variant needs the test-signing dance). *Use GenieX; do not hand-build llama.cpp-Hexagon.*

Reference throughput from the llama.cpp Hexagon docs (Android v79 device, not X Elite): Llama-3.2-1B Q4_0 → pp128 **169 t/s**, tg64 **51.5 t/s**; gpt-oss-20B Q4_0 across 4 HTP devices → prefill 51 t/s, decode 18.4 t/s.

### 2.3 Foundry Local + Windows ML (Microsoft's path)

- **Windows ML** is now Microsoft's official local-inference framework: "the Windows-supported and maintained copy of ONNX Runtime," with **execution providers delivered and auto-updated by Windows Update** so your app doesn't bundle them. Requires Win11 24H2 (26100)+ for hardware EPs; ARM64 supported.
- **QNN EP status (as of the 2026-07-30 doc revision):** Windows ML 2.x → MSIX `2.2450.47.0`, **QAIRT 2.45**, released "2026 5D"; next `2.2451.48.0` / QAIRT 2.45.41 GA "2026 7D". `EpName = "QNNExecutionProvider"`. Requires Snapdragon X Elite (X1Exxxxx) or X Plus (X1Pxxxxx) with **Hexagon NPU driver ≥ 30.0.140.0** (we have 30.0.219.1000 ✅).
- Acquisition API: `ExecutionProviderCatalog.GetDefault()` → `FindAllProviders()` (a fresh Qualcomm box prints `QNNExecutionProvider: NotPresent`) → `EnsureReadyAsync()` (with progress callback, "multiple seconds to minutes" on first run) → `TryRegister()`. Or one-shot `EnsureAndRegisterCertifiedAsync()`. **Python note from the docs: the one-shot API is explicitly "DO NOT use" from Python** — Python must use `find_all_providers()` + `ensure_ready_async()` + ORT's `register_execution_provider_library`.
- **Pre-compile your models.** Windows ML "highly recommends" it: EP compilation on an NPU takes "tens of seconds to minutes" for larger models. Use ORT's **EPContext** mechanism (`*_ctx.onnx` + sidecar `.bin`) via `OrtModelCompilationOptions.CompileModel()` / Python `ort.ModelCompiler(...).compile_to_file()` (ORT ≥ 1.22). Cache per device; catch `INVALID_GRAPH` and recompile when the EP or NPU driver updates. **This is a very cheap, very visible optimization to demo: cold-start N seconds → milliseconds.**
- **Foundry Local**: `winget install Microsoft.FoundryLocal` (v0.10.2.0 available here). ~20 MB runtime, curated catalog (GPT-OSS, Qwen, DeepSeek, Mistral, Phi + Whisper), OpenAI-compatible incl. the Responses API, and on Windows the SDK ships as **`foundry-local-sdk-winml`** / `Microsoft.AI.Foundry.Local.WinML` which routes through Windows ML for the wider EP set. Its docs confirm Qualcomm NPU support obliquely via a troubleshooting row: *"Qnn error code 5005: Failed to load from EpContext model" → install the Qualcomm NPU driver (softwarecenter.qualcomm.com/catalog/item/QHND) and reboot to clear NPU resource conflicts, especially after using Windows Copilot+ features."* ← **Note that last clause. Windows Copilot+ features can hog the NPU. Reboot before the demo.**
- **BYO models:** `pip install olive-ai` then `olive optimize --model_name_or_path <hf-id> --device npu --provider QNNExecutionProvider --precision int4 ...`, drop an `inference_model.json` next to it, point `ModelCacheDir` at it. Start from <https://github.com/microsoft/olive-recipes>. Budget for this to be fiddly ("a single command line example might not work for every model, device, or execution provider").

### 2.4 ONNX Runtime GenAI directly

- Latest **v0.15.0 (2026-07-30)**; v0.14.0 added "**Support QNN stateful models**" and Qualcomm continuous-decoding optimizations. Recent releases added Mistral3 VLM multi-image, Qwen3-VL / Qwen3.5-VL, Gemma4 multimodal, audio content blocks, Whisper ASR.
- ARM64 wheels exist (`onnxruntime_genai-0.15.1-cp312-cp312-win_arm64.whl` **[verified]**).
- **But:** the `onnxruntime_genai.models.builder` tool's `-e` (execution provider) options are cpu / cuda / dml / webgpu — **QNN is not a supported build target** for the model builder. And the standalone QNN EP itself "exclusively supports quantized models," rejects dynamic shapes, and its **quantization tooling only runs on x86-64**.
- **Conclusion:** do **not** try to produce your own NPU-accelerated LLM through ORT-GenAI in 4 days. ORT-GenAI is the right tool for **small fixed-shape models** (Whisper, embeddings, vision), not for the chat model. Get the chat model from AI Hub, pre-compiled.

### 2.5 Turnkey apps: AnythingLLM, Ollama, LM Studio

| App | NPU on X Elite? | Notes |
|---|---|---|
| **AnythingLLM Desktop** | ✅ Yes, via bundled QNN models | Ships native Windows ARM builds. NPU-capable model list is exactly four: **Llama-3.2-3B-Chat (8k)**, **Llama-3.2-3B-Chat (16k)**, **Llama-3.1-8B-Chat (8k)**, **Phi-3.5-mini-instruct (4k)** — downloaded to `models/QNN` (manual ZIPs from their CDN if auto-download fails). Good as a *baseline comparison* in our benchmark table; too closed to be our runtime. |
| **Ollama** (installed here) | ❌ No | Ollama's accelerator docs list NVIDIA/CUDA, AMD/ROCm, Apple Metal, and Vulkan. **No Snapdragon/Hexagon/Adreno.** On WoA it is **Oryon CPU only.** Useful only as a "CPU-only baseline" row. |
| **LM Studio** | ❌ No Snapdragon NPU | Its blog shows Linux-on-ARM support (DGX Spark, Oct 2025) but nothing for Windows-on-ARM NPU. |

### 2.6 Windows AI Foundry / Phi Silica — ⚠️ **being deleted, do not build on it**

Phi Silica (the OS-preinstalled SLM on the NPU, with speculative decoding + prompt compression) is a Limited Access Feature requiring an unlock token, **and Microsoft has announced its replacement**:

> "**Phi Silica is being replaced by Aion Instruct.** … **Early October 2026** — standalone sideloadable package for testing and LoRA training. **October 2026** — Aion Instruct rolls out to Windows Insider Preview; the active model is controlled by a Windows CFR. **November 2026** — Aion Instruct rolls out to retail devices and **Phi Silica is removed**."
> — <https://learn.microsoft.com/en-us/windows/ai/apis/phi-silica> (ms.date 2026-07-15)

Aion-1.0-Instruct is described in the Edge blog as smaller/faster/more efficient than Phi-4-mini (4B), with a planned open-source Hugging Face release. **Verdict: mentioning Aion in the pitch = "we know where the platform is going" credibility; *depending* on Phi Silica = building on something that gets deleted in 3 months, plus a LAF token request that won't clear in 4 days.** Skip it for the chat model.

Phi Silica also has no documented function-calling surface — only `GenerateResponseAsync` plus fixed "Text Intelligence Skills" (Summarize / Rewrite / Text-to-table). Useless for our agentic tool loop.

### 2.7 Measured throughput table — Snapdragon X Elite

All from Qualcomm's own published model cards on Hugging Face (`huggingface.co/qualcomm/<Model>`); "Response Rate" = decode tok/s after first token; ctx = 4096 unless noted.

| Model | Runtime | Quant | tok/s | TTFT (s) |
|---|---|---|---:|---|
| **Qwen3-0.6B** | GENIEX_QAIRT | w4a16 | **82.94** | 0.030–0.963 |
| Qwen3-0.6B | GENIEX_LLAMACPP | q4_0 | 16.8–31.1 | 0.19–15.0 |
| **Qwen3-1.7B** | GENIEX_QAIRT | w4a16 | **42.15** | 0.052–1.66 |
| **Llama-3.2-3B-Instruct-SSD** (self-spec. decoding) | GENIE / GENIEX_QAIRT | w4a16 | **33.42 / 31.70** | 0.153–4.89 / 0.132–4.22 |
| Llama-3.2-3B-Instruct | GENIEX_QAIRT | w4a16 | 19.73 | 0.131–4.19 |
| Llama-3.2-3B-Instruct | GENIE | w4a16 | 12.13 | 0.118–3.79 |
| Llama-3.2-3B-Instruct | GENIEX_QAIRT | **w4** | 8.89 | 0.270–8.65 |
| **Qwen3-4B-Instruct-2507** | GENIEX_QAIRT | w4a16 | **23.09** | 0.098–3.149 |
| Qwen3-4B-Instruct-2507 | GENIE | w4a16 | 15.66 | 0.117–3.729 |
| Qwen3-4B | GENIEX_QAIRT | w4a16 | 21.77 | 0.098–3.126 |
| **Qwen3-VL-4B-Instruct** | GENIEX_QAIRT | w4a16 | **20.89** | 0.1–3.2 |
| Qwen3-VL-4B-Instruct | GENIEX_LLAMACPP | q4_0 | 7.58 | 0.58–18.48 |
| Qwen3-VL-2B-Instruct | GENIEX_LLAMACPP | q4_0 | 11.6–16.0 | 0.24–14.99 |
| Qwen3.5-2B | GENIEX_LLAMACPP | q4_0 | 21.1–28.4 | 0.32–14.4 |
| Phi-4-Mini-Instruct | GENIEX_LLAMACPP | q4_0 | 9.7–16.0 | 0.41–30.7 |
| Granite-4.0-Micro | GENIEX_LLAMACPP | q4_0 | 11.1–25.3 | 0.37–17.4 |
| Ministral-3-3B-Instruct-2512 | GENIEX_LLAMACPP | q4_0 (X2 Elite data only) | 18.6–25.4 | 0.18–40.7 |

**Four conclusions we should say out loud in the pitch:**
1. **`qairt` (AI Hub pre-compiled, NPU) beats llama.cpp-Hexagon by ~2.7×** on the same model (Qwen3-VL-4B: 20.89 vs 7.58 tok/s) and cuts worst-case TTFT by 6×.
2. **`w4a16` beats `w4` by 2.2×** (Llama-3.2-3B: 19.73 vs 8.89) — a concrete quantization-choice optimization.
3. **GenieX beats the older GENIE runtime by ~47 %** on Qwen3-4B-2507 (23.09 vs 15.66) — free win from using the current runtime.
4. **Self-speculative decoding is the single biggest free win: +61 % (19.73 → 31.70 tok/s) with "guaranteed output accuracy identical to the base model."** If Llama-3.2-3B's tool calling is good enough for our loop, the SSD variant is the best latency/quality point on X Elite.
5. Context: **Snapdragon X2 Elite is ~1.9× faster** than X Elite (Qwen3-4B-2507: 43.26 vs 23.09). Useful to note we're on the *older* silicon.

---

## 3. Tool-calling quality of small local models

Source: Berkeley Function Calling Leaderboard **V4**, results dated **2025-12-16** (`HuanzhiMao/BFCL-Result/2025-12-16/score/data_overall.csv`). ⚠️ V4 added Web-Search and Memory categories that crush small models, so **overall %** understates them badly. **For a QNet-Home-style loop (a handful of local tools, short conversations) the columns that matter are Non-Live AST and Live AST.**

| Model | Overall | Non-Live AST | Live AST | Multi-Turn | Irrelevance det. |
|---|---:|---:|---:|---:|---:|
| Nanbeige4-3B-Thinking-2511 (FC) | 51.40 % | 81.58 | **79.42** | 51.12 | 83.09 |
| xLAM-2-3b-fc-r (FC) | 41.22 % | 82.96 | 62.92 | **58.38** | 63.45 |
| **Qwen3-8B (FC)** | 42.57 % | **87.58** | **80.53** | 41.75 | 79.07 |
| **Qwen3-4B-Instruct-2507 (FC)** | 35.68 % | **87.88** | 76.39 | 22.12 | 84.93 |
| Arch-Agent-3B | 35.36 % | 86.67 | 72.91 | 34.88 | 74.67 |
| Qwen3-1.7B (FC) | 28.41 % | 82.92 | 74.61 | 11.00 | 76.54 |
| Hammer2.1-3b (FC) | 29.71 % | 84.96 | 70.54 | 16.50 | 86.12 |
| Mistral-Small-2506 (FC) | 37.15 % | 73.60 | 77.28 | 11.50 | 87.94 |
| Gemma-3-12b-it (Prompt) | 30.43 % | 79.44 | 74.24 | 5.75 | 70.29 |
| **Phi-4 (Prompt)** | 28.79 % | **69.56** | 60.70 | 3.88 | 87.55 |
| Llama-3.3-70B-Instruct (FC) | 31.90 % | 88.02 | 76.61 | 21.50 | 53.53 |
| *(reference)* Claude-Opus-4-5 (FC) | 77.47 % | 88.58 | 79.79 | 68.38 | 84.72 |

**Decisions this drives:**
- **Qwen3-4B-Instruct-2507 is the right orchestrator.** Its single-turn AST accuracy (87.9 % non-live / 76.4 % live) is within noise of Llama-3.3-**70B** and Qwen3-**8B**, and it is the fastest 4B on our NPU (23.1 tok/s). Its 84.9 % irrelevance detection matters a lot for an always-on home agent that must *not* fire `escalate_to_emergency` on a false positive.
- **Avoid Phi-4/Phi-4-mini for tool calling** — 69.6 % non-live AST is the worst in the table, and Phi-4-mini is llama.cpp-only (slow) on X Elite anyway. This is a notable finding since Phi is the "obvious" Microsoft-on-Windows choice.
- **Multi-turn is where all small models fall apart** (Qwen3-4B: 22 %). **Architect around this:** keep each LLM turn to *one* decision with a *small* tool set, drive the state machine in our own Python/Node code, and re-inject a compact fresh context each turn instead of relying on a long tool-calling dialogue. This also happens to match GenieX's "only one tool call per assistant turn is parsed" limitation.
- **Force the format.** Use `--enable-json` or a **GBNF grammar** (`--grammar-path`) so tool JSON is structurally guaranteed rather than hoped for. Prime with a system message that literally shows `<tool_call>{"name": ..., "arguments": {...}}</tool_call>`, as Qualcomm's own example does.
- **Two-tier routing is a defensible optimization story:** Qwen3-0.6B (82.9 tok/s, 30 ms TTFT) does event triage / intent classification with a 3-way grammar-constrained output; only genuine incidents escalate to Qwen3-4B. Measurable NPU-time and energy savings, easy to graph.

---

## 4. Speech-to-text

### Option A — Windows AI Speech Recognition API (recommended primary)
`Microsoft.Windows.AI.Speech` in the Windows App SDK. **On a Copilot+ PC it always runs on the NPU and the model is preinstalled** (no multi-GB download, unlike the CPU path). Two modes: `BatchRecognition.RecognizeFromFile(path)` and `StreamingRecognition(AudioConfiguration.FromAudioDevice(mic), model)` with a `Recognized` event + `StartContinuousRecognitionAsync()`. Prereqs: Win11 24H2 (26100)+, WinAppSDK ≥ 1.7.1.

**⚠️ Hard requirement:** *"your app must be packaged as an MSIX package with the `systemAIModels` capability declared in `Package.appxmanifest`,"* and `MaxVersionTested` must be ≥ `10.0.26226.0` or you get "Not declared by app" errors. **This is actually a gift: the judging rubric already demands an MSIX, so the MSIX work does double duty.** It does mean the STT path is C#/WinRT, not pure Python.

### Option B — AI Hub Whisper on the NPU (recommended for the *numbers*)
Qualcomm ships a ready-made Windows Python app:
```powershell
pip install qai-hub-apps
qai-hub-apps fetch whisper_windows_py --model whisper_base --chipset qualcomm-snapdragon-x-elite --output-dir ~
cd ~\whisper_windows_py; .\install_runtime.ps1; .venv\Scripts\Activate.ps1
python demo.py --stream-audio-device <n>       # or --audio-file fox.wav
```
Runs Whisper via **ONNX Runtime QNN**. Qualcomm's script installs an **x64 Python** ("ARM64 Python is not supported by all dependencies") — **that guidance is stale**: `onnxruntime-qnn 2.4.0` has a native `cp312-win_arm64` wheel **[verified]**, so try native ARM64 first and only fall back to emulated x64 if a dependency actually breaks.

**Whisper-Base on Snapdragon X Elite NPU** (Qualcomm model card; MHA→SHA + linear→conv re-architected for Hexagon; targets `PRECOMPILED_QNN_ONNX`, `QNN_CONTEXT_BINARY`, `VOICE_AI`; input 80×3000 = 30 s, max 200 decoded tokens):

| Part | Params | Inference time | Peak mem |
|---|---:|---:|---:|
| Encoder | 23.7 M (90.7 MB float) | **48.999 ms** | 67 MB |
| Decoder (per step) | 48.9 M (187 MB float) | **3.722 ms** | 126 MB |

→ A 30 s window transcribes in ~49 ms + (tokens × 3.7 ms). **~600× realtime on the encoder.** For reference, X2 Elite does the same encoder in 22.7 ms.

Larger options on AI Hub if accuracy matters: `whisper_small`, `whisper_small_quantized`, `whisper_medium`, `whisper_large_v3_turbo(_quantized)`, `distil_whisper`, plus `zipformer` and `huggingface_wavlm_base_plus`.

### Option C — whisper.cpp on Oryon CPU
Fine as an emergency fallback (Oryon is a fast ARM core with good SIMD), but it puts zero load on the NPU, which is precisely the opposite of what the 40-pt criterion rewards. **`faster-whisper` is not an option — no `ctranslate2` win_arm64 wheel [verified].**

---

## 5. Text-to-speech on Windows ARM

**The built-in voices are a demo-killer.** Our box only has `Microsoft David/Zira Desktop` (SAPI) and `MSTTS_V110_enUS_{DavidM,MarkM,ZiraM}` (OneCore) **[verified]** — 2013-era concatenative voices. Windows' newer "natural voices" are Narrator add-ons and not reliably exposed to apps. **Windows AI Foundry has no TTS API** (its API list covers Phi Silica, OCR, Speech *Recognition*, Video/Image Super Resolution, Image Description/Segmentation/Erase, Image Generation — **no synthesis**; "Live Translation" is listed as *not yet available*).

### 5.1 Normal voice
| Option | Verdict |
|---|---|
| **`kokoro-onnx` (Kokoro-82M)** | ✅ **Best default.** `pip install kokoro-onnx` (pure-py wheel), `onnxruntime` ARM64 wheel available, `misaki` G2P available **[all verified]**. ~300 MB fp32 / ~80 MB quantized, many voices, "near real-time on macOS M1." Runs on Oryon CPU; can also be pointed at ORT-QNN if we want to chase NPU. |
| **Piper** | ⚠️ Fast VITS+ONNX, huge voice library, but the original `rhasspy/piper` was **archived 2025-10-06** and development moved to `OHF-Voice/piper1-gpl` which is **GPL-3.0** (the old one was MIT). `pip install piper-tts` is an sdist that embeds espeak-ng → build risk on ARM64. **Check whether GPL-3 is acceptable for a Qualcomm-internal submission before using it.** |
| **AI Hub `pipertts_en` / `melotts_en`** | ❌ Both model cards say *"currently not supported on any Compute chipset"* — they're mobile/Dragonwing targets today. (MeloTTS-EN is MIT, 157.9 M params / 603 MB float; PiperTTS-EN ~38 M params across encoder/flow/decoder + T5. Both are viable on **CPU**, and PiperTTS/MeloTTS on the **Arduino UNO Q / Dragonwing** node is a legitimate option if we want TTS at the edge.) |
| SAPI `System.Speech` | Only as a zero-dependency fallback. |

### 5.2 Parent's cloned voice (our differentiator)
| Option | Params | License | ARM64-CPU realtime? |
|---|---:|---|---|
| **Chatterbox-Nano (Resemble AI)** | **110 M** | **MIT** | ✅ **"runs 3× faster than realtime on 8 CPU cores"** — X Elite has 12 Oryon cores. Zero-shot clone from a ~10 s reference clip. `pip install chatterbox-tts` (pure-py wheel) **[verified]**, but it's PyTorch → **install torch from `--index-url https://download.pytorch.org/whl/cpu` (2.13.0+cpu win_arm64) [verified]**, *not* PyPI. |
| Chatterbox-Turbo | 350 M | MIT | Distilled 1-step decoder, paralinguistic tags (`[laugh]`, `[cough]`) — try if Nano quality is thin |
| Chatterbox-Multilingual V3 | 500 M | MIT | 23+ languages; probably too heavy for realtime on CPU |
| **OpenVoice V2 + MeloTTS** | tone-color converter on top of a base TTS | **MIT** | ✅ plausible; `openvoice-cli` wheel available **[verified]**. Nice property: base TTS quality decoupled from cloning, and MeloTTS is the same family Qualcomm already ported. |
| XTTS-v2 (Coqui) | — | **CPML (non-commercial)** | ❌ avoid for a corporate submission |
| F5-TTS / E2-TTS | ~330 M DiT | varies | Heavier; only if Chatterbox fails |

**Recommendation:** **Chatterbox-Nano** for the cloned-parent voice (MIT + realtime on CPU + 10 s enrolment is a *great* demo beat: "record 10 seconds, now the system speaks as you"), with **Kokoro** as the neutral system voice. Splitting them also lets us say *"cloned voice runs on the Oryon CPU while the LLM occupies the NPU and the GPU stays idle — three compute domains, zero contention"* which is a strong resource-utilization narrative.

**Also budget for the consent/ethics slide.** Voice cloning is the highest-risk part of the idea. Have (a) an explicit on-device enrolment consent flow, (b) reference audio never leaving the device, (c) an audible/visible "this is a synthesized voice of <name>" indicator. Judges will ask.

---

## 6. Vision-language models on X Elite

Yes — comfortably. Qualcomm AI Hub's Compute (X Elite) catalog includes **Qwen3-VL-2B/4B/8B-Instruct**, **Qwen2.5-VL-7B-Instruct**, and **Gemma-4-E2B/E4B-it**, plus 461 model variants / 209 models overall.

| VLM | Runtime | tok/s | TTFT |
|---|---|---:|---|
| **Qwen3-VL-4B-Instruct** | GENIEX_QAIRT (NPU, w4a16) | **20.89** | 0.1–3.2 s |
| Qwen3-VL-4B-Instruct | GENIEX_LLAMACPP (q4_0) | 7.58 | 0.58–18.48 s |
| Qwen3-VL-2B-Instruct | GENIEX_LLAMACPP (q4_0) | 11.6–16.0 | 0.24–14.99 s |

Serving a VLM is trivial with GenieX:
```bash
geniex infer ai-hub-models/Qwen3-VL-4B-Instruct
# or via the OpenAI server, with image_url accepting a local path, http(s) URL, or base64 data URL
```
And the server supports **tool calling from a VLM turn** — the documented example has the VLM look at a photo, decide what to search for, and emit a `web_search` tool call. **That maps almost 1:1 onto QNet Home:** edge node ships one JPEG → VLM assesses the scene → VLM calls `notify_caregiver` / `speak_to_room` / `escalate`.

**Architectural warning:** don't put the VLM in the hot path. Its TTFT is up to 3.2 s because the vision encoder must run. Design: cheap NPU detectors on the edge node fire an event in <1 ms → Qwen3-0.6B triages in ~30 ms → *only if ambiguous* do we pull a single frame and pay the VLM's 3 s. That tiered design **is** the "latency/optimization" answer.

**Purpose-built NPU models that beat a VLM on latency for our use cases** (all X Elite, Qualcomm model cards):

| Model | Precision | Inference time | Use in QNet Home |
|---|---|---:|---|
| **MediaPipe-Pose** detector | w8a8, PRECOMPILED_QNN_ONNX | **0.307 ms** | fall detection stage 1 |
| **MediaPipe-Pose** landmark | w8a8 | **0.292 ms** | fall detection stage 2 (keypoint geometry) |
| **YamNet** | w8a8 ONNX | **0.097 ms** | scream / glass-break / thud / crying — 521 AudioSet classes |
| YamNet | float ONNX | 0.166 ms | 14.2 MB, 3.73 M params |

Also on AI Hub and directly relevant: `yolov11_pose`, `yolo26_pose`, `rtmpose_body2d`, `hrnet_pose`, `movenet`, `litehrnet`, `foot_track_net`, **`gear_guard_net`** (PPE detection), `face_det_lite`, `face_attrib_net`, `eyegaze`, **`yolo_world` / `owlv2` (open-vocabulary zero-shot detection — "detect a knife" with no training)**, `sam2`/`sam3`/`edgetam`/`track_anything`, `depth_anything_v3`, and **`nomic_embed_text`** for on-device RAG over house state/history. There are also `pi05` (Physical Intelligence π0.5 VLA) and `grootn15` (NVIDIA GR00T N1.5) if we ever want a robotics angle.

---

## 7. How to MEASURE and SHOW NPU utilization, latency, and energy

This section is worth the most points per hour of effort. Build a **"telemetry HUD"** panel into the app and leave it on screen during the demo.

### 7.1 Live NPU utilization — a PowerShell one-liner ⭐ **[verified working on our machine]**

Windows has **no `NPU Engine` performance-counter set** (I enumerated all counter sets: only `GPU Engine`, `GPU Adapter Memory`, etc.). But the Hexagon NPU is an **MCDM** device and therefore shows up inside the **`GPU Engine`** counter set under its own adapter LUID with a single engine type, `Compute`. On this machine:

```
LUID 0x00000000_0x0000D443 -> 3D, Compute, Decryption, HW, Reserved, VideoDecode, VideoEncode, VideoProcessing   # Adreno GPU
LUID 0x00000000_0x0000D827 -> 3D                                                                                  # Basic Render
LUID 0x00000000_0x0000D85A -> Compute                                                                             # <-- Hexagon NPU
```

Robust discovery + live read:

```powershell
# 1. Find the NPU adapter: the LUID whose ONLY engine type is Compute
$paths = (Get-Counter -ListSet 'GPU Engine').PathsWithInstances
$npuLuid = $paths |
  ForEach-Object { if ($_ -match 'luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+).*engtype_(\w+)') { [pscustomobject]@{L=$matches[1];E=$matches[2]} } } |
  Group-Object L | Where-Object { ($_.Group.E | Sort-Object -Unique).Count -eq 1 -and $_.Group[0].E -eq 'Compute' } |
  Select-Object -First 1 -ExpandProperty Name

# 2. Total NPU utilization % (sum across PIDs), sampled once per second
while ($true) {
  $s = (Get-Counter "\GPU Engine(*luid_${npuLuid}*engtype_Compute)\Utilization Percentage").CounterSamples
  $total = ($s | Measure-Object CookedValue -Sum).Sum
  $top   = $s | Sort-Object CookedValue -Desc | Select-Object -First 1
  "{0:N1}% NPU   top: {1}" -f $total, $top.InstanceName
  Start-Sleep 1
}
```
Instance names are `pid_<PID>_luid_..._engtype_compute`, so you get **per-process NPU utilization** — you can prove *your* process is on the NPU, not just that the NPU is busy. Same data as Task Manager's NPU graph, but scriptable and loggable into a chart.

### 7.2 Task Manager
Windows 11 Task Manager → Performance → **NPU** shows utilization, driver version, physical location. Have it open on a second monitor during the demo (Microsoft's own Copilot+ dev guide points at exactly this).

### 7.3 ETW / Windows Performance Recorder + Analyzer
**WPR ships a `NeuralProcessing` profile [verified present on our machine]** that records MCDM interactions with the NPU. Microsoft's documented recipe:

```powershell
# grab ort.wprp + etw_provider.wprp from github.com/microsoft/onnxruntime
wpr -start ort.wprp -start etw_provider.wprp -start NeuralProcessing -start CPU
#   ... run the scenario ...
wpr -stop onnx_NPU.etl -compress
```
Open in **Windows Performance Analyzer** (Microsoft Store) → graphs **"Neural Processing → NPU Utilization"** and Generic Events for ONNX. WPA also gives you session-creation time, EP config, per-inference times, and per-operator profiling. **GPUView** now covers NPU/MCDM operations too. Get WPT from the Windows ADK (May 2024+).

### 7.4 ONNX Runtime + QNN profiling
- `SessionOptions.enable_profiling = True` → JSON trace, viewable in **Perfetto UI** (ui.perfetto.dev) or `chrome://tracing`.
- **QNN EP profiling** (ORT ≥ 1.17): set `profiling_level` and ORT writes **`qnn-profiling-data.csv`** in QNN SDK's native format to the CWD. Or ETW: enable provider `Microsoft.ML.ONNXRuntime`, keyword `0x100`, level 5 (VERBOSE) — CSV auto-disables when TraceLogging is on.
- `onnxruntime_perf_test.exe -p <profile>` for standalone runs.

### 7.5 llama.cpp Hexagon per-op profiling
If we run any llama.cpp-Hexagon path: `GGML_HEXAGON_PROFILE=1` (µs + cycles) or `=2` (+ PMU counters), piped into `scripts/snapdragon/ggml-hexagon-profile.py`. Plus `GGML_HEXAGON_OPFILTER=<regex>` for ablation studies ("we moved FLASH_ATTN_EXT off the NPU and lost X %").

### 7.6 Qualcomm Snapdragon Profiler (qprof)
System-wide GUI profiler across CPU/GPU/DSP/NPU with **NPU sub-HW metrics and memory bandwidth**. Highest-credibility artifact if we have time to install it: <https://www.qualcomm.com/developer/software/snapdragon-profiler>. Since our team is Qualcomm-internal multimedia, using qprof screenshots signals domain expertise.

### 7.7 Energy — three levels
1. **Instantaneous power, no admin, no tools [verified working]:**
   ```powershell
   Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus |
     Select-Object DischargeRate, Voltage, RemainingCapacity
   ```
   `DischargeRate` is in **mW** (0 while on AC — **unplug for the measurement**). Sample it at 1 Hz around a fixed workload and you get a real power curve. Compute **tokens per joule** = tokens/s ÷ (mW/1000). Run the identical prompt on `--compute npu` vs `--compute cpu` and show the ratio. *This single chart will likely win the energy sub-criterion.*
2. **Per-process energy attribution (elevated):** `powercfg /srumutil /output srum.csv /csv` dumps the Windows **Energy Estimation Engine (E3)** data from the SRUM database. ⚠️ **[verified] it fails non-elevated** (`status 5 / 0x1f`) — run PowerShell as Administrator.
3. **Reports:** `powercfg /batteryreport /output batt.html`, `powercfg /energy` (energy-efficiency issue analysis), `powercfg /sleepstudy`.

### 7.8 The four measurements to actually publish
1. **Latency budget waterfall**, end to end, in ms: edge-node detect (0.6 ms pose) → MQTT/event hop → triage SLM TTFT (30 ms) → orchestrator TTFT (98 ms) → TTS first audio → speaker. Give a single "event-to-voice" number.
2. **Throughput/quality/precision ablation table:** w4a16 vs w4 (19.73 vs 8.89), qairt vs llama.cpp (20.89 vs 7.58), GenieX vs GENIE (23.09 vs 15.66), SSD vs base (31.70 vs 19.73), NPU vs CPU. All from `geniex-bench` so the methodology is Qualcomm's.
3. **NPU utilization trace** during a 60 s scenario, with per-PID attribution, showing the NPU carrying the load and CPU staying low.
4. **Energy:** mW on battery and **tokens/joule**, NPU vs CPU, plus cold-start before/after EPContext pre-compilation.

---

## 8. Packaging a Python/Node app as a Windows ARM64 .EXE / .MSIX

**Good news: everything needed is already on this machine [verified].**

### 8.1 Python → EXE
**PyInstaller 6.21.0 publishes a `py3-none-win_arm64` wheel** — native ARM64 bootloader, no cross-compile games. (Historical note: ARM64 bootloader lookup was fixed in 6.5.0, and 6.4.0 made target arch default to the running Python's arch.)
```powershell
pyinstaller --noconfirm --onedir --name QNetHome app.py `
  --collect-all kokoro_onnx --collect-all onnxruntime `
  --add-binary "C:\path\to\qnn\*.dll;."
```
Prefer `--onedir` over `--onefile`: the ONNX/QNN DLL set is large and onefile pays an extraction cost on every launch (bad for a latency story). Nuitka is the alternative (sdist, compiles fine with the installed VS2022) if you want a harder-to-reverse binary.

### 8.2 EXE → MSIX
```powershell
$sdk = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\arm64"
& "$sdk\makeappx.exe" pack /d .\dist\QNetHome /p QNetHome.msix /o
# self-signed for the demo:
$c = New-SelfSignedCertificate -Type Custom -Subject "CN=QNetHome" `
      -KeyUsage DigitalSignature -CertStoreLocation "Cert:\CurrentUser\My" `
      -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3","2.5.29.19={text}")
& "$sdk\signtool.exe" sign /fd SHA256 /a /f cert.pfx /p <pw> QNetHome.msix
```
`Package.appxmanifest` essentials:
- `ProcessorArchitecture="arm64"`
- `<TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26226.0" />` — **must be ≥ 26226.0** or Windows AI APIs fail with "Not declared by app"
- `<Capability Name="systemAIModels" />` if we use the Speech Recognition (or any Windows AI) API
- `microphone`, `webcam`, `internetClient`/`privateNetworkClientServer` as needed
- `windows.fullTrustProcess` extension for the packaged PyInstaller exe

The `CN=` in the cert **must exactly match** the manifest `Publisher`, and the cert must be imported into *Trusted People*/*Trusted Root* on the demo machine (or use the App Installer flow). Alternatively wrap with a Visual Studio **Windows Application Packaging Project** (VS2022 is installed) which handles manifest + signing + `.msixbundle`.

### 8.3 Node/Electron path
If the UI is Electron (OpenClaw is Node/TS): `electron-builder` supports `--arm64` with `appx` and `nsis` targets on Windows; it invokes the same SDK tools. Tauri v2 also targets `aarch64-pc-windows-msvc` with MSI/NSIS. Either satisfies the ".EXE" requirement; MSIX needs the appx target.

### 8.4 The install story judges will grade
Don't ship a 6 GB MSIX. Ship a **small MSIX (< 200 MB)** that on first run:
1. checks the NPU driver version and warns if < 30.0.140.0;
2. downloads the GenieX CLI (or bundles the **Microsoft-signed** SDK zip) and `geniex pull`s the model with a progress bar;
3. **pre-compiles/EPContext-caches** any ORT models and reports the one-time cost;
4. shows a consent dialog for voice enrolment.
Then say in the pitch: "install is one MSIX double-click; first-run model provisioning is X seconds; every launch after that is Y ms." That directly answers "ease of install" **and** gives you another measured number.

---

## 9. Gotchas / risk register (ranked by how much time they'll cost)

| # | Risk | Mitigation |
|---|---|---|
| 1 | **No `torch` wheel on PyPI for win_arm64** — kills naive installs of Chatterbox, most HF pipelines | Use `pip install torch --index-url https://download.pytorch.org/whl/cpu` (2.13.0+cpu cp312 win_arm64 **[verified]**) |
| 2 | **`opencv-python` won't build on ARM64 [verified failure]**; **`ctranslate2` unavailable** → no `faster-whisper` | Do camera/vision on the edge nodes with GStreamer; on PC use Pillow/imageio + ORT; use AI Hub Whisper or the Windows Speech API |
| 3 | **llama.cpp-Hexagon needs TESTSIGNING + Secure Boot off on Windows** | Use the **Microsoft-signed GenieX** installer; never hand-build HTP libs |
| 4 | **Phi Silica is deprecated (removed Nov 2026) and is a Limited Access Feature needing a token** | Don't build on it. Use GenieX + AI Hub models. Mention Aion Instruct as forward-looking awareness |
| 5 | **Windows Copilot+ features can hold the NPU** ("reboot to clear NPU resource conflicts, especially after using Windows Copilot+ features") | Reboot before the demo; add an NPU-availability check + friendly error |
| 6 | **First EP compile takes seconds→minutes**; a driver/EP update silently invalidates the cache | Pre-compile with EPContext, cache per device, catch `INVALID_GRAPH` and recompile. Turn this into a measured optimization slide |
| 7 | **QAIRT bundle constraints are baked in** — precision, context length, KV size all fixed; `nCtx`/`ngl` rejected | Pick the 4096-ctx bundle up front; use `--sliding-window` so a long-running agent doesn't hard-error on context overflow |
| 8 | **Small models are bad at multi-turn tool calling (22 %)** | One decision per LLM turn, small tool set, our own state machine, GBNF/`--enable-json` constrained output, fresh compact context each turn |
| 9 | **Windows AI Speech Recognition requires MSIX + `systemAIModels` + `MaxVersionTested ≥ 10.0.26226.0`** | Do the MSIX early (it's a rubric requirement anyway); keep a Whisper-ONNX fallback so a manifest problem can't sink the demo |
| 10 | **QAIRT SDK version on device must match the version the bundle was compiled with** (model cards list it; currently 2.45) | Let GenieX manage it (`geniex pull` prepares for your device); don't hand-assemble genie bundles unless you must |
| 11 | **Exporting your own LLM from `qai_hub_models` takes 1–2 hours** per model | Only use **pre-compiled** AI Hub bundles (`ai-hub-models/*` namespace). Do not plan an export inside a 4-day window |
| 12 | **GenieX is "developer preview," pre-1.0** | Pin to v0.3.18, keep the installer offline in the repo, and have a llama.cpp-CPU fallback config so a bad update can't brick the demo |
| 13 | Piper's active fork is **GPL-3.0** (old MIT repo archived 2025-10-06) | Use Kokoro (Apache-ish) / MeloTTS (MIT) / Chatterbox (MIT) instead, or clear GPL with legal |
| 14 | `powercfg /srumutil` fails silently non-elevated **[verified]** | Script an elevation check; capture energy data from an admin shell |

---

## 10. Concrete recommended architecture for QNet Home

```
┌──────────── Arduino UNO Q (Dragonwing) — Room A / Room B ─────────────┐
│ GStreamer pipeline → NPU/DSP:                                        │
│   MediaPipe-Pose  (0.3 ms det + 0.3 ms landmark, w8a8)  → fall/posture│
│   YamNet          (0.097 ms, w8a8)                      → scream/thud │
│   (optional) yolo_world / owlv2 open-vocab              → hazards     │
│ Publishes ONLY semantic events (JSON over MQTT). No video, ever.      │
│ Optionally: PiperTTS/MeloTTS locally for the room speaker.            │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  semantic events
┌───────────────────────────▼─── Snapdragon X Elite Copilot+ PC ───────┐
│ TIER 1  Qwen3-0.6B  (NPU, 82.9 tok/s, 30 ms TTFT, GBNF-constrained)  │
│         → triage: ignore | ask | act                                 │
│ TIER 2  Qwen3-4B-Instruct-2507 (NPU, 23.1 tok/s, 98 ms TTFT)         │
│         → OpenClaw agent loop, one tool call per turn                │
│         tools: speak_to_room, ask_and_listen, notify_caregiver,       │
│                live_connect, flicker_lights, escalate_911            │
│ TIER 3  Qwen3-VL-4B-Instruct (NPU, 20.9 tok/s) — ONLY on ambiguity,  │
│         one still frame, ~3 s TTFT                                   │
│ STT     Windows AI Speech Recognition (NPU, preinstalled, streaming)  │
│         + AI Hub Whisper-Base (NPU: 49 ms enc / 3.7 ms dec) for numbers│
│ TTS     Kokoro-82M (CPU) neutral · Chatterbox-Nano (CPU) cloned parent│
│ SERVE   geniex serve → http://127.0.0.1:18181/v1  (OpenAI protocol)  │
│ HUD     live NPU % per PID, tok/s, TTFT, mW, tokens/joule             │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  (opt-in, non-private) heavy/batch work
                     Qualcomm Cloud AI 100
```
**Compute-domain story for the judges:** NPU runs the LLM/VLM/STT, Oryon CPU runs TTS + orchestration, Adreno GPU stays free for UI — three heterogeneous domains on one SoC with no contention, plus two more device classes (Dragonwing edge, AIC100 cloud). That is the "how systems work together" theme, quantified.

## 11. Day-by-day sequencing (4 build days)

- **Day 0 (today, 3h):** Install `geniex-cli-setup-windows-arm64-v0.3.18.exe`; `geniex pull ai-hub-models/Qwen3-4B-Instruct-2507` + `Qwen3-0.6B` + `Qwen3-VL-4B-Instruct`; `geniex serve`; hit it with `curl` and the `openai` Python client; get a tool call to fire. Download `geniex-bench-windows-arm64.zip` and run one matrix. **Reboot first** to clear NPU conflicts. Ship the NPU-% one-liner as `tools/npu_hud.ps1`.
- **Day 1:** Event bus + edge nodes (pose + YamNet). OpenClaw pointed at `:18181/v1` with 6 tools, GBNF-constrained. First end-to-end "event → spoken response."
- **Day 2:** STT (Windows API in a minimal MSIX-packaged C# helper, Whisper-ONNX fallback) + TTS (Kokoro) + Chatterbox voice enrolment & consent flow. Two-way conversation loop.
- **Day 3:** MSIX packaging + first-run provisioning + the measurement suite (geniex-bench matrix, WPR NeuralProcessing trace, battery mW / tokens-per-joule chart, EPContext cold-start before/after). VLM tier only if time permits.
- **Day 4 (half):** Freeze, rehearse, record a backup video of the demo, finalize the numbers slide.

---

## Sources

**Qualcomm — GenieX / AI Hub / QAIRT**
- GenieX repo (BSD-3, v0.3.18, 2026-07-31): <https://github.com/qualcomm/GenieX>
- GenieX docs: <https://geniex.aihub.qualcomm.com/>
- GenieX local (OpenAI-compatible) server incl. tool calling: <https://github.com/qualcomm/GenieX/blob/main/docs/en/run/cli/local-server.mdx>
- GenieX CLI reference (`--compute`, GBNF, `--enable-json`, `--sliding-window`): <https://github.com/qualcomm/GenieX/blob/main/docs/en/run/cli/reference.mdx>
- GenieX models & precisions (Q4_0 for Hexagon; w4a16/w4 for QAIRT): <https://github.com/qualcomm/GenieX/blob/main/docs/en/models/supported.mdx>
- GenieX platforms & runtime constraints: <https://github.com/qualcomm/GenieX/blob/main/docs/en/get-started/platforms.mdx>
- `geniex-bench` methodology + download URLs: <https://github.com/qualcomm/GenieX/blob/main/notes/bench.md>
- GenieX HTP signing (Microsoft-signed vs self-signed flavours): <https://github.com/qualcomm/GenieX/blob/main/notes/run.md>, <https://github.com/qualcomm/GenieX/blob/main/notes/release.md>
- Qualcomm AI Hub Apps (ChatApp Windows C++, `whisper_windows_py`, `qai-hub-apps` CLI): <https://github.com/qualcomm/ai-hub-apps>
- LLM on Genie tutorial (QAIRT env vars, v73 for X Elite, memory requirements): <https://github.com/qualcomm/ai-hub-apps/blob/main/tutorials/llm_on_genie/README.md>
- GenieX tutorial in ai-hub-apps: <https://github.com/qualcomm/ai-hub-apps/blob/main/tutorials/geniex/README.md>
- AI Hub Models catalog (melotts/pipertts/yamnet/whisper/pose/yolo/…): <https://github.com/qualcomm/ai-hub-models>
- AI Hub Compute model list: <https://aihub.qualcomm.com/compute/models>
- Model cards with X Elite benchmarks: <https://huggingface.co/qualcomm/Qwen3-4B>, <https://huggingface.co/qualcomm/Qwen3-4B-Instruct-2507>, <https://huggingface.co/qualcomm/Qwen3-1.7B>, <https://huggingface.co/qualcomm/Qwen3-0.6B>, <https://huggingface.co/qualcomm/Qwen3-VL-4B-Instruct>, <https://huggingface.co/qualcomm/Qwen3-VL-2B-Instruct>, <https://huggingface.co/qualcomm/Qwen3.5-2B>, <https://huggingface.co/qualcomm/Llama-v3.2-3B-Instruct>, <https://huggingface.co/qualcomm/Llama-v3.2-3B-Instruct-SSD>, <https://huggingface.co/qualcomm/Phi-4-Mini-Instruct>, <https://huggingface.co/qualcomm/Granite-4.0-Micro>, <https://huggingface.co/qualcomm/Ministral-3-3B-Instruct-2512>, <https://huggingface.co/qualcomm/Whisper-Base>, <https://huggingface.co/qualcomm/YamNet>, <https://huggingface.co/qualcomm/MediaPipe-Pose-Estimation>
- MeloTTS-EN / PiperTTS-EN (not yet on Compute chipsets): <https://aihub.qualcomm.com/compute/models/melotts_en>, <https://aihub.qualcomm.com/compute/models/pipertts_en>
- Windows on Snapdragon AI setup scripts (ORT-QNN, QNN, MLC): <https://github.com/quic/wos-ai>
- Snapdragon Profiler: <https://www.qualcomm.com/developer/software/snapdragon-profiler>
- Qualcomm NPU driver (QHND): <https://softwarecenter.qualcomm.com/catalog/item/QHND>

**Microsoft — Windows ML / Windows AI / Foundry Local**
- What is Windows ML (2026-07-14): <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/overview>
- Windows ML execution providers — QNN versions & driver reqs (2026-07-30): <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/supported-execution-providers>
- Accelerate AI models / silicon-to-EP mapping: <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/accelerate-ai-models>
- Model compilation & caching (EPContext): <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/model-compilation>
- Install/register EPs (`ExecutionProviderCatalog`): <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/initialize-execution-providers>
- Get started with Windows ML: <https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/get-started>
- Copilot+ PC developer guide — **how to measure NPU perf** (Task Manager, WPR `NeuralProcessing`, WPA, GPUView, ORT ETW, qprof): <https://learn.microsoft.com/en-us/windows/ai/npu-devices/>
- Windows AI APIs overview (hardware matrix; no TTS API): <https://learn.microsoft.com/en-us/windows/ai/apis/>
- Phi Silica → **Aion Instruct deprecation timeline**: <https://learn.microsoft.com/en-us/windows/ai/apis/phi-silica>
- Aion Instruct announcement: <https://blogs.windows.com/msedgedev/2026/06/02/expanding-on-device-ai-in-microsoft-edge-new-models-and-apis-for-the-web/>
- Speech Recognition API (NPU, MSIX + `systemAIModels`): <https://learn.microsoft.com/en-us/windows/ai/apis/speech-recognition>
- Foundry Local overview / get started / compile HF models / best practices (incl. Qnn 5005 troubleshooting): <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/what-is-foundry-local>, <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started>, <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/how-to/how-to-compile-hugging-face-models>, <https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/reference/reference-best-practice>
- Foundry Local repo: <https://github.com/microsoft/Foundry-Local>
- Foundry Toolkit for VS Code (DeepSeek-R1 distilled NPU build for Snapdragon): <https://learn.microsoft.com/en-us/windows/ai/toolkit/>

**ONNX Runtime**
- QNN Execution Provider (HTP, QDQ, context-binary caching, limitations): <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
- ORT GenAI releases (v0.15.0, 2026-07-30): <https://github.com/microsoft/onnxruntime-genai/releases>
- ORT GenAI model builder (EP options — no QNN): <https://github.com/microsoft/onnxruntime-genai/blob/main/src/python/py/models/README.md>
- Profiling tools (Perfetto, QNN CSV, ETW): <https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html>
- EPContext design: <https://onnxruntime.ai/docs/execution-providers/EP-Context-Design.html>
- `onnxruntime-qnn` 2.4.0 (2026-07-14, win_arm64 wheels): <https://pypi.org/project/onnxruntime-qnn/>

**llama.cpp Hexagon backend**
- Snapdragon backend README (env vars, profiling, NDEV, perf): <https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md>
- Windows-on-Snapdragon build + **test-signing requirement**: <https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/windows.md>
- Developer details (VTCM, 3.5 GB PD limit, multi-device split): <https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/developer.md>

**Tool calling / models / TTS / agents**
- Berkeley Function Calling Leaderboard V4 raw scores (2025-12-16): <https://github.com/HuanzhiMao/BFCL-Result/blob/main/2025-12-16/score/data_overall.csv>, leaderboard: <https://gorilla.cs.berkeley.edu/leaderboard.html>
- AnythingLLM QNN/NPU model list: <https://docs.anythingllm.com/manual-qnn-model-download>; desktop (Windows ARM builds): <https://anythingllm.com/desktop>
- Ollama accelerator support (no Snapdragon NPU): <https://docs.ollama.com/gpu>
- LM Studio blog (no WoA NPU): <https://lmstudio.ai/blog>
- Chatterbox TTS (Nano 110M, MIT, 3× realtime on 8 CPU cores): <https://github.com/resemble-ai/chatterbox>
- Kokoro-ONNX: <https://github.com/thewh1teagle/kokoro-onnx>
- Piper (archived MIT) → piper1-gpl (GPL-3): <https://github.com/rhasspy/piper>, <https://github.com/OHF-Voice/piper1-gpl>
- OpenVoice V2 (MIT, tone-color conversion): <https://github.com/myshell-ai/OpenVoice>
- OpenClaw (Node/TS, MIT, OpenAI-compatible providers, Windows install): <https://github.com/openclaw/openclaw>
- Olive recipes: <https://github.com/microsoft/olive-recipes>
- PyInstaller changelog (ARM64 fixes in 6.4/6.5): <https://pyinstaller.org/en/stable/CHANGES.html>
