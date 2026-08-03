# Voice Cloning + TTS Feasibility for QNet Home
### On-device (Snapdragon X Elite / Windows-on-ARM) — evaluated 3 Aug 2026

**Scope:** the "speak in the parent's cloned voice" feature (use case 2) and the "warm, low-latency non-cloned voice" for the elder scenario (use case 1).

**Everything in the "MEASURED" sections below was run on our actual hackathon machine** — `Snapdragon(R) X Elite - X1E80100 - Qualcomm(R) Oryon(TM) CPU`, 12 logical cores, Windows 11 Pro 26200, Python 3.12.10 (native ARM64). Not vendor claims. These are the numbers to put on the slide.

**Reproducible artefacts left in this repo:**
- `shim/` — the verified `torchaudio` + `numba` shim that makes Chatterbox and Perth run on Windows-on-ARM (§4.3)
- `bench_kokoro.py`, `bench_chatterbox.py`, `bench_turbo.py` — the benchmark scripts
- `out/*.wav` — generated audio, including the watermark positive/negative controls (§7.1)
- `.venv-tts/` (Chatterbox stack), `.venv-kokoro/` (ONNX stack), `models/kokoro/` (fp32 + int8 ONNX)

---

## 0. TL;DR — the recommendation

| Role | Choice | Why |
|---|---|---|
| **Primary — cloned parent voice** | **Chatterbox Turbo (350M)**, Resemble AI, **MIT (code + weights)**, **run as a pre-synthesised line cache, not live** | Only credible zero-shot cloner that is truly MIT *including weights*, runs on CPU, and ships its own neural watermark. ⚠️ **MEASURED RTF 3.3 on X Elite CPU — NOT interactive.** Viable only because the cloned lines are a small pre-generatable set (see §4.5). Needs our shim (built & verified, §4). |
| **Fallback — cloned parent voice, free text** | **ElevenLabs Instant Voice Cloning + Flash v2.5** (~75 ms model latency) | Cloud, ~10 min to integrate. Genuinely needed for arbitrary parent-typed text, where on-device RTF 3.3 would mean a 12 s wait. |
| **Primary — elder / system voice (non-cloned)** | **Qualcomm AI Hub `PiperTTS-EN`, MIT** on the Hexagon NPU — **61.5 ms total, 100% NPU (401+620+310+180+461+117 = 1,689/1,689 layers on NPU), ≤4 MB peak per component** on Snapdragon X Elite CRD | This is the 40-point technical criterion in one slide: real NPU offload, official Qualcomm-published numbers, MIT licence, and the *same* model targets Dragonwing. |
| **Primary (pragmatic) — elder voice** | **Kokoro-82M via `kokoro-onnx`, Apache-2.0** | MEASURED on our box: **RTF 0.276 → 3.6× realtime, fp32, ARM64-native, zero compilation, ~15 s to install.** Warmer/nicer than Piper. Use if the NPU path eats too much of the 4 days. |
| **Emergency fallback — any voice** | Windows SAPI5 (`System.Speech`) | MEASURED: **107 ms for 12.1 s of audio (RTF ≈ 0.009)**. Robotic, but zero install, zero download, always works. |

**Do not use:** XTTS-v2 (licence), F5-TTS (licence), Fish Speech/OpenAudio (licence), Zonos (needs 6 GB VRAM), MeloTTS-as-a-python-package (pins `torch<2.0`), Piper's own Python package (GPL-3.0), **Chatterbox base 500M (measured RTF 10.7 — unusable)**.

> **The single most important finding in this report:** *no* open zero-shot voice cloner runs at interactive speed on the X Elite **CPU** — Chatterbox Turbo, the fastest MIT-licensed option, measures **RTF 3.3 (12 s to speak a 4 s line)**. The feature is still shippable, but **only** because the cloned lines are a constrained, pre-generatable set (§4.5). Design around a cache from hour one; do not plan on live cloned synthesis. Meanwhile the *non-cloned* path is the opposite story: **61.5 ms, 100% on the Hexagon NPU** (§3).

---

## 1. The licence table — read this first

Our hackathon requires open-source components and a shippable `.EXE`. Several of the best-known cloners are **non-commercial** and would be a disqualifying-grade mistake if a judge checks.

| Model | Code licence | **Weights licence** | Commercial-use OK? | Verdict |
|---|---|---|---|---|
| **Chatterbox** (Resemble AI) | MIT | **MIT** | ✅ **Yes** | ✅ **USE THIS** |
| Kokoro-82M | Apache-2.0 (`kokoro-onnx` MIT) | **Apache-2.0** | ✅ Yes | ✅ Use (no cloning) |
| Qualcomm AI Hub PiperTTS-EN | BSD-3-Clause (`ai-hub-models`) | **MIT** (from `rhasspy/piper-checkpoints`) | ✅ Yes | ✅ Use (no cloning) |
| ZipVoice (k2-fsa) | Apache-2.0 | Apache-2.0 | ✅ Yes | ⚠️ Interesting (see §6) |
| OpenVoice v1 + v2 | **MIT since Apr 2024** | MIT | ✅ Yes | ⚠️ Stale, bad deps (see §5) |
| Zonos-v0.1 (Zyphra) | Apache-2.0 | Apache-2.0 | ✅ Yes | ❌ 6 GB VRAM, "CPU impractical" |
| **XTTS-v2 (Coqui)** | MPL-2.0 *(code)* | **Coqui Public Model License (CPML)** | ❌ **NO — non-commercial** | ❌ **AVOID** |
| **F5-TTS** | MIT *(code)* | **CC-BY-NC** (trained on Emilia) | ❌ **NO** | ❌ **AVOID** |
| **Fish Speech / OpenAudio** | **"Fish Audio Research License"** | same, proprietary | ❌ **NO** | ❌ **AVOID** |
| **Piper** (`piper1-gpl`, `pip install piper-tts` v1.6.0) | **GPL-3.0-or-later** (espeak-ng) | voices MIT/CC | ⚠️ copyleft | ❌ Avoid the *code*; the *models* are fine |
| MeloTTS (`melotts` 0.1.1 on PyPI) | MIT | MIT | ✅ Yes | ❌ pins `torch<2.0`, `transformers==4.27.4` — dead on ARM64 |
| sherpa-onnx | Apache-2.0 | per-model | ✅ Yes | ⚠️ **no `win_arm64` wheel** (see §6) |
| Perth watermarker | **MIT** | MIT | ✅ Yes | ✅ Use for AI Act marking |
| AudioSeal (Meta) | **MIT incl. weights** | MIT | ✅ Yes | ✅ Alternative watermark |

**Three gotchas worth saying out loud in the pitch (it shows rigour):**
1. **XTTS-v2 is the "obvious" choice and it is non-commercial.** The *code* is MPL-2.0 but the *weights* on `huggingface.co/coqui/XTTS-v2` are CPML. The original `coqui-ai/TTS` repo is unmaintained; the live fork is `idiap/coqui-ai-TTS` (`pip install coqui-tts`, v0.27.5, MPL-2.0 code) — but the licence problem is in the weights, so the fork does not fix it.
2. **Piper the *package* is GPL-3.0** (it links espeak-ng). Piper the *voice models* are MIT/CC. We get Piper quality with no copyleft by taking the **Qualcomm AI Hub PiperTTS-EN export (MIT)** and running it on the NPU — we never link the GPL code. This is a genuinely clever, defensible move.
3. **F5-TTS's MIT badge is on the code only.** Checkpoints are CC-BY-NC because Emilia is an in-the-wild dataset.

---

## 2. MEASURED: what actually runs on our Snapdragon X Elite

### 2.1 Windows-on-ARM Python/wheel reality check (verified by querying the indexes directly)

| Package | `win_arm64` wheel? | Notes |
|---|---|---|
| **`torch`** | ✅ **YES — but only from `download.pytorch.org`, NOT PyPI** | `torch-2.7.0+cpu` (cp312) was the first; now up to **`2.13.0+cpu` for cp311/312/313**. `pip install torch --index-url https://download.pytorch.org/whl/cpu`. **MEASURED: installed in 79 s, `torch 2.13.0+cpu`, `get_num_threads()=12`.** Zero `win_arm64` torch wheels exist on PyPI — if you `pip install torch` plainly, you get nothing. |
| `torchvision` | ✅ Yes (0.25.0 → 0.28.0) | |
| **`torchaudio`** | ❌ **NO — none, ever, any version** | **This is the single biggest blocker.** See §4 for our shim. |
| `onnxruntime` | ✅ Yes (1.26–1.28, cp311–cp314) | **MEASURED: ORT 1.28.0 native ARM64, providers `['AzureExecutionProvider','CPUExecutionProvider']`.** |
| **`onnxruntime-qnn`** | ✅ **Yes — 2.4.0, cp311–cp314** | The Hexagon NPU path on Windows. |
| `onnxruntime-genai` | ✅ Yes (0.15.1) | For the SLM side of OpenClaw. |
| `numpy` | ✅ **only ≥ 2.3.0** | ⚠️ **No `win_arm64` wheel exists for any numpy 1.x.** Any package pinning `numpy<2` cannot install. |
| `numba` / `llvmlite` | ❌ No | Source build fails (needs LLVM). Blocks `librosa.filters` — fixed with a **~40-line no-op stub**, see §4.3. |
| `kaldi-native-fbank` | ❌ No | |
| `soxr` | ❌ no wheel, ✅ **builds from source OK** | We saw `soxr-1.1.0-cp312-abi3-win_arm64.whl` get built successfully. |
| `soundfile`, `sounddevice` | ✅ Yes | Use these for audio I/O instead of torchaudio. |
| `librosa`, `transformers`, `diffusers`, `s3tokenizer`, `resemble-perth`, `conformer`, `pyloudnorm` | ✅ pure-python | Fine, but watch transitive deps. |
| `sherpa-onnx` | ❌ **No `win_arm64`** (win_amd64/win32 only) | ✅ but **has `manylinux2014_aarch64`** — perfect for the UNO Q. See §6. |

### 2.2 MEASURED: Kokoro-82M via `kokoro-onnx` on X Elite CPU

Install was completely painless — **no PyTorch, no compiler, ~15 s**: `pip install kokoro-onnx soundfile misaki espeakng-loader` pulled ORT 1.28.0 + numpy 2.5.1 as native ARM64 wheels.

| Model file | Size | Text | Audio out | Synth time | **RTF** | **× realtime** |
|---|---|---|---|---|---|---|
| `kokoro-v1.0.int8.onnx` | 92 MB | short | 4.80 s | 2901 ms | 0.604 | 1.65× |
| `kokoro-v1.0.int8.onnx` | 92 MB | long | 7.34 s | 4898 ms | 0.667 | 1.50× |
| **`kokoro-v1.0.onnx` (fp32)** | 326 MB | short | 4.82 s | **1329 ms** | **0.276** | **3.63×** |
| **`kokoro-v1.0.onnx` (fp32)** | 326 MB | long | 7.23 s | **2199 ms** | **0.304** | **3.29×** |

Voice `af_heart`, `speed=1.0`, `lang=en-us`, best of 3 after warm-up, ORT CPU EP, 12 threads. Model load 0.5–0.9 s.

> ### ⚠️ **Counter-intuitive result worth a slide: int8 is 2.2× SLOWER than fp32 on ARM64 CPU.**
> The int8 Kokoro export is QDQ-quantised; ONNX Runtime's CPU EP inserts Quantize/Dequantize pairs it can't fuse for several op types on ARM64, so it de-optimises badly versus fp32 running on NEON. **Ship the 326 MB fp32 model, not the "efficient" 92 MB int8 one.** This is exactly the kind of measured, non-obvious optimisation finding that scores on "resource utilization / optimization", and it's a great 30-second story: *"we measured instead of assuming."*
>
> Caveat: this conclusion is for the **CPU EP**. If you route Kokoro through **QNN EP / Hexagon NPU**, quantised is the *required* format and the conclusion flips. Say that explicitly so it reads as understanding, not luck.

### 2.3 MEASURED: Windows SAPI5 baseline

```
Installed voices: Microsoft David Desktop (en-US, Male), Microsoft Zira Desktop (en-US, Female)
Synthesis: 107 ms for 386,516 bytes @16 kHz mono = 12.08 s audio  →  RTF ≈ 0.009 (≈113× realtime)
```
Only the two legacy SAPI5 voices are present — **no Windows 11 "Natural" voices are installed on this machine**, so don't plan on them being there on a judge's machine either. Quality is 2010-era robotic; unusable as the *warm* elder voice, perfect as a never-fails fallback and as a "degraded mode" demo beat.

---

## 3. Qualcomm AI Hub: the NPU offload win (the 40-point play)

This is the strongest technical finding in this report. **Qualcomm AI Hub ships production TTS models compiled for the Hexagon NPU, and Snapdragon X Elite is an explicitly supported target.**

Two relevant models, both `domain=Audio`, `useCase=Audio Generation`, `tags=["real-time"]`, runtime asset `voice_ai`:

### 3.1 `PiperTTS-EN` — MIT — **61.5 ms end-to-end, 100% NPU**

Components and **Qualcomm-published measured latency on `Snapdragon X Elite CRD`**:

| Component | Params | Size (float) | NPU layers | **Inference (X Elite)** | Peak mem | **X2 Elite** |
|---|---|---|---|---|---|---|
| `encoder` | 7.51 M | 28.7 MB | 401/401 | **29.714 ms** | 0 MB | 18.606 ms |
| `t5_encoder` | 15.1 M | 57.5 MB | 620/620 | **11.364 ms** | 0 MB | 7.098 ms |
| `flow` | 7.39 M | 28.2 MB | 310/310 | **15.859 ms** | 4 MB | 9.563 ms |
| `decoder` | 1.66 M | 6.37 MB | 461/461 | **1.041 ms** | 0 MB | 0.643 ms |
| `t5_decoder` | 5.72 M | 21.8 MB | 180/180 | **0.440 ms** | 1 MB | 0.341 ms |
| `sdp` | 1.04 K | 6.61 KB | 117/117 | **3.069 ms** | 0 MB | 1.754 ms |
| **TOTAL** | **~37.4 M** | **~143 MB** | **1,689 / 1,689 → `primaryComputeUnit: "NPU"`** | **≈ 61.5 ms** | **≤ 4 MB** | **≈ 38.0 ms** |

**Every single layer runs on the NPU — `cpu: 0, gpu: 0`.** For a typical reassurance sentence (~3–4 s of audio) that's an **RTF of roughly 0.015–0.02, i.e. ~50–65× realtime, at ≤4 MB peak memory**, versus Kokoro's RTF 0.276 on the CPU. That is a **~15× latency improvement and a near-total CPU offload** — a directly quotable, defensible "we used the NPU" number with an honest CPU baseline to compare against, both measured.

- Precision: `mixed_with_float`. Max decoded sequence length **64 tokens** → **you must chunk text per sentence/clause**. Design the event→speech layer around short utterances anyway (which is what a reassurance line is).
- Supported chipsets include `qualcomm-snapdragon-x-elite`, `qualcomm-snapdragon-x2-elite`, `qualcomm-snapdragon-x-plus-8-core`, `qualcomm-snapdragon-8-elite`, and the **Dragonwing/IQ family** (`qcs9075`, `qcs8275`, `qcs7181`, `qcs8550-proxy`, `sa8775p`, …). Device list includes `Snapdragon X Elite CRD` and `Dragonwing IQ-9075 EVK`.
- Also `PiperTTS-DE`, `PiperTTS-IT`.

### 3.2 `MeloTTS-EN` — MIT — 261 ms, 100% NPU (richer prosody, 4× slower)

Components: `encoder` 8.30 M / **39.999 ms**, `flow` 20.1 M / 7.725 ms, `decoder` 14.5 M / 1.076 ms, `bert_wrapper` 94.5 M (360 MB) / **129.112 ms**, `t5_encoder` / **82.775 ms**, `t5_decoder` / 0.420 ms → **≈ 261.1 ms total, ~164 M params, ~603 MB float**, all NPU. Also `MeloTTS-ES`, `MeloTTS-ZH`.

The `bert_wrapper` is what buys MeloTTS better prosody (BERT-conditioned phrasing) and it's also 50% of the latency. **Piper is 4.2× faster and 4× smaller; MeloTTS sounds better.** Both are MIT and both are 100% NPU-resident. If you have time, run both and let the pitch say "we A/B'd two NPU TTS engines and chose on measured latency."

### 3.3 Honest caveat about the Arduino UNO Q
The UNO Q's Dragonwing part (QRB2210-class) is **not** in the `supportedChipsets` list above — the listed Dragonwing parts are the IQ-9075/QCS-series. So on the UNO Q, plan on **Piper/Kokoro as plain ONNX on the Cortex-A CPU** (still fine — Piper is ~37 M params), or better: **don't do TTS on the edge node at all.** Synthesise on the X Elite NPU and ship PCM/Opus to the room speaker. That is also the better architecture story: the edge node stays a *semantic sensor*, exactly as the pitch claims.

### 3.4 Useful adjacent asset
`qualcomm/ai-hub-apps` (BSD-3-Clause, pushed 3 Aug 2026) has a **Whisper speech-to-text Windows app (Python + ONNX Runtime)** and a **ChatApp using the Genie SDK** for local LLM. That covers the ASR half of the two-way conversation and the SLM half of OpenClaw with Qualcomm-blessed sample code. Note the repo moved: `quic/ai-hub-models` → **`qualcomm/ai-hub-models`**.

---

## 4. Chatterbox on Windows-on-ARM: the blockers and the fix (VERIFIED)

Chatterbox is the right answer on licence, quality and safety grounds. It does **not** install out of the box on Windows-on-ARM. We reproduced every failure and built the fix.

### 4.1 The model family

| Variant | Params | Languages | Package support | Notes |
|---|---|---|---|---|
| `ChatterboxTTS` | 500 M | English | ✅ PyPI 0.1.7 | CFG + `exaggeration` controls |
| `ChatterboxMultilingualTTS` (V3) | 500 M | **23+** | ✅ PyPI 0.1.7 | + 6 single-language finetunes |
| **`ChatterboxTurboTTS`** | **350 M** | English | ✅ PyPI 0.1.7 | **Distilled the token→mel decoder from 10 steps to 1.** Paralinguistic tags `[laugh]`, `[cough]`, `[chuckle]`. |
| **`ChatterboxTurboTTS(nano=True)`** | **110 M** | English | ❌ **NOT in PyPI 0.1.7** | Resemble's claim: **"3× faster than realtime on 8 CPU cores."** |

> ⚠️ **`pip install chatterbox-tts` gives you 0.1.7, whose `from_pretrained(cls, device)` has no `nano` argument.** Nano requires `git clone https://github.com/resemble-ai/chatterbox && pip install -e .`. Verified by grepping the installed package. Budget for the git install if you want Nano's speed.

Reference audio: **~10 s clip** is what Resemble documents (`your_10s_ref_clip.wav`). Our 30–60 s registration recording is *more* than enough — and the extra length is a UX/consent asset, not a technical need. (Contrast: XTTS-v2 claims 6 s, Fish 10–30 s, ZipVoice <3 s.)

### 4.2 The four blockers (all reproduced on this machine)

1. **`numpy<2.0.0` pin → hard fail.** `chatterbox-tts` requires `numpy<2.0.0,>=1.24.0` for py<3.13. No numpy 1.x has a `win_arm64` wheel, so pip tries a source build and dies:
   ```
   AttributeError: module 'pkgutil' has no attribute 'ImpImporter'
   ERROR: Failed to build 'numpy' when getting requirements to build wheel
   ```
2. **`torch==2.6.0` pin → unsatisfiable.** Earliest `win_arm64` torch is **2.7.0**.
3. **`torchaudio==2.6.0` → no `win_arm64` wheel exists for any version.** Hard blocker.
4. **`librosa` → `numba`/`llvmlite` → no wheels, source build fails.**
   ```
   ERROR: Failed building wheel for llvmlite
   Failed to build numba llvmlite
   ```

### 4.3 The fix — VERIFIED WORKING

**Blocker 4 needs a stub (and this bit is subtle).** `import librosa` on its own succeeds with numba absent, because librosa 0.11.0 uses `lazy_loader`:
```
librosa import OK 0.11.0     (numba absent: ModuleNotFoundError)
```
**But that is misleading** — Chatterbox does `from librosa.filters import mel`, and `librosa/filters.py:52` does `from numba import jit` at module scope, which still explodes:
```
chatterbox/models/s3gen/utils/mel.py:3  from librosa.filters import mel as librosa_mel_fn
librosa/filters.py:52                   from numba import jit
ModuleNotFoundError: No module named 'numba'
```
Fix: a **~40-line no-op `numba` stub** with pass-through `jit`/`njit`/`vectorize`/`guvectorize`/`stencil` decorators, `prange = range`, and stub `numba.core.errors`. The JIT is pure optimisation, so pass-through gives **numerically identical** results, just slower — and only for a few small helpers in `librosa.filters`/`librosa.util`, never the hot path (which is torch). Verified correct:
```
numba stub 0.0.0-qnet-stub
mel filterbank shape (80, 961)  sum 6.3999  finite True
```

**Blocker 3 is much smaller than it looks.** Chatterbox's *entire* torchaudio surface is two call sites:
```
models/s3gen/s3gen.py:44    return ta.transforms.Resample(src_sr, dst_sr).to(device)
models/s3gen/xvector.py:50  feature = Kaldi.fbank(au.unsqueeze(0), num_mel_bins=80)
```
And **`torchaudio/compliance/kaldi.py` is 813 lines of pure Python + pure `torch`** — no C++ extension, no `_torchaudio.pyd`. Its only import of torchaudio itself is one incidental line (delete it). So we **vendor that single file** (pytorch/audio, **BSD-2-Clause — verified**, © 2017 Facebook Inc.) and implement `Resample` with `scipy.signal.resample_poly`. Total shim: **~880 lines, of which we wrote ~64.**

**There is a second torchaudio consumer we did not expect: the Perth watermarker itself.** `resemble-perth`'s `audio_processor.py` does `from torchaudio.transforms import Spectrogram, InverseSpectrogram, TimeStretch`, and Chatterbox's constructor calls `perth.PerthImplicitWatermarker()` **unconditionally** — so with an incomplete shim you get a confusing `TypeError: 'NoneType' object is not callable` (perth's `__init__.py` swallows the ImportError and sets the class to `None`). Those three transforms are also pure-torch, so we added them: `torch.stft` / `torch.istft` wrappers plus a vendored `phase_vocoder`.

Final shim:
```
shim/torchaudio/__init__.py               6 lines
shim/torchaudio/transforms.py          ~130 lines   Resample (scipy resample_poly)
                                                    + Spectrogram / InverseSpectrogram / TimeStretch
shim/torchaudio/compliance/__init__.py     1 line
shim/torchaudio/compliance/kaldi.py     812 lines   vendored, BSD-2-Clause
shim/numba/__init__.py                  ~40 lines   no-op JIT decorators
```
The shim lives at `shim/` in this repo, is built, and is **numerically validated**:
```
fbank shape (98, 80)                                  <- Kaldi 80-mel features correct
spec (1, 513, 94)  roundtrip max_abs_err = 9.54e-07   <- STFT/iSTFT numerically exact
timestretch (1, 513, 79)                              <- phase vocoder OK
mel filterbank (80, 961)  sum 6.3999  finite True     <- librosa.filters.mel correct
loaded PerthNet (Implicit) at step 250,000
PERTH WATERMARKER OK -> applied, detector output = 1.0 <- full watermark round-trip
```

> **This last line is the important one.** The complete Article 50 machine-readable-marking pipeline — embed *and* detect — is **verified working natively on Windows-on-ARM**. The §7.1 live-detector demo is therefore not aspirational; the plumbing already runs on this machine.
Verified output with the shim on `PYTHONPATH`:
```
shim torchaudio 0.0.0-qnet-shim
kaldi.fbank present: True
fbank shape (98, 80)          <-- correct Kaldi 80-mel fbank
resample (1, 16000)           <-- 24 kHz -> 16 kHz OK
```

**The working recipe (copy this into the repo README):**
```bash
python -m venv .venv                      # Python 3.12 ARM64
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cpu   # -> 2.13.0+cpu win_arm64
.venv\Scripts\pip install --no-deps chatterbox-tts                                  # bypass numpy<2 / torch==2.6.0 pins
.venv\Scripts\pip install "numpy>=2.3" scipy soundfile sounddevice onnx typer \
    transformers tokenizers safetensors omegaconf conformer einops pyloudnorm \
    resemble-perth s3tokenizer diffusers huggingface_hub Pillow importlib_metadata
.venv\Scripts\pip install --no-deps librosa==0.11.0 lazy_loader audioread pooch msgpack decorator
.venv\Scripts\pip install "antlr4-python3-runtime==4.9.3"   # omegaconf 2.3.x needs 4.9.x, NOT 4.13
set PYTHONPATH=%CD%\shim                  # torchaudio + numba shims
```
Additional pins we hit and fixed, in the order they bit us (all trivial, all pure-python — none are architectural):
1. `transformers` 5.14.1 requires `tokenizers>=0.22,<=0.23.0` — 0.23.1 raises `ImportError`. Also needs `typer`.
2. `s3tokenizer` needs `onnx` (1.22.0 installs fine on ARM64).
3. `diffusers` needs `Pillow` + `importlib_metadata`.
4. `omegaconf` 2.3.1 needs `antlr4-python3-runtime==4.9.3`; with 4.13 you get `Exception: Could not deserialize ATN with version 3 (expected 4)`.
5. `librosa.filters` needs the numba stub (§4.3).

**Weights download is ~4.0 GB for Turbo** (`t3_turbo_v1.safetensors` 1915 MB + `s3gen.safetensors` 1057 MB + `s3gen_meanflow.safetensors` 1065 MB + `ve.safetensors` 5.7 MB; HF card `license: mit`). **Pre-download this before demo day and pin the HF cache into the installer** — a 4 GB first-run download would wreck the "ease of install" score (20 pts). Nano at 110M will be far smaller and is the better shipping choice for the `.EXE` if you can get the git install working.

**Risk assessment:** the shim is verified to produce correct features, and every remaining dependency is pure-python. Call this **~2–4 hours of work, low residual risk** — versus my initial read of "1.5 days, uncertain." Do it. But keep the ElevenLabs flag wired as insurance, and see §4.4 for the zero-risk escape hatch.

### 4.4 Two escape hatches if the shim goes wrong
- **x64 emulation (Prism).** Install an **x64** Python alongside the ARM64 one and `pip install chatterbox-tts` normally — `torch`/`torchaudio` x64 wheels exist and Prism runs them. Expect a ~2–3× slowdown. Since cloned-voice lines are *not* on the latency-critical path (see §7), this is perfectly acceptable and costs ~20 minutes. **This is the real safety net; it needs no patching at all.**
- **AIC100.** You have a Cloud AI 100 in the kit and nothing obvious to run on it. Voice cloning is the *ideal* AIC100 workload: heavy, bursty, invoked rarely. Frame it as **tiered compute**: NPU for always-on reassurance TTS, AIC100 only for the one-time voice-embedding extraction at registration. That upgrades "we used 4 devices" from a checkbox to an argued design — *the heavy, rare job goes to the accelerator; the light, constant job stays on the NPU.*

### 4.5 MEASURED: Chatterbox generation on X Elite CPU — **and this changes the plan**

The shim works, the models load, generation is correct. **But it is far too slow to be interactive.** 12 threads, `device="cpu"`, best-of-3 after warm-up, ~8.8 s reference clip:

| Model | Load | Audio out | **Generation** | **RTF** | × realtime |
|---|---|---|---|---|---|
| `ChatterboxTTS` (500M, base) | 14.4 s | 4.32 s | **46.09 s** | **10.67** | 0.09× |
| `ChatterboxTTS` (500M, base) | — | 4.68 s | **66.50 s** | **14.21** | 0.07× |
| **`ChatterboxTurboTTS` (350M)** | 16.2 s | 3.80 s | **12.27 s** | **3.23** | **0.31×** |
| `ChatterboxTurboTTS` (350M) | — | 3.44 s | 11.62 s | 3.38 | 0.30× |
| `ChatterboxTurboTTS` (350M) | — | 3.72 s | 12.34 s | 3.32 | 0.30× |

**Read this carefully:**
- **Base 500M is unusable — RTF ~10.7–14.2.** A one-second sentence costs 11+ seconds. Roughly **40× too slow** to be interactive.
- **Turbo's single-step decoder distillation is real and large: 3.2× faster than base**, and very consistent (3.23 / 3.38 / 3.32 across runs). But **RTF 3.3 still means ~12 s to speak a 4 s line.**
- **Nano's "3× faster than realtime on 8 cores" (RTF 0.33) implies a further 10× over Turbo from only a 3.2× parameter cut.** On our 12-core Oryon box that looks optimistic; budget for **RTF ~1.0–1.5** and treat the vendor claim as unproven until measured.

> ### 🔧 The fix that makes the feature shippable: **pre-synthesise the cached line set.**
> §7.8 already constrains the cloned voice to a small template set of de-escalation lines. So **generate them all at registration time** — right after consent, while the "creating your voice profile…" progress bar is on screen — and cache the WAVs. Then:
> - **Common case (canned intervention line): 0 ms. Instant playback.** Better than any cloud API.
> - **Rare case (parent types free text): ~12 s on Turbo.** Cover it in the UX — the parent's phone shows "speaking in your voice…" — or fall back to ElevenLabs for free text only.
>
> This turns a fatal latency problem into a non-issue, costs almost nothing to build, and is a *better* answer than brute-force speed because it exploits a constraint the safety design already imposed. **It is also a strong pitch beat: the guardrail that makes the feature safe is the same thing that makes it fast.**

**Also fixed along the way — a float64 leak.** Turbo initially died with `RuntimeError: expected m1 and m2 to have the same dtype, but got: float != double` inside `s3tokenizer.log_mel_spectrogram`. Cause: a `float64` array reaching `torch.stft` while `_mel_filters` is `float32`. Fix is a two-line cast on `librosa.load` / `librosa.resample` output:
```python
librosa.resample = lambda y, **kw: np.ascontiguousarray(_orig(y, **kw)).astype(np.float32)
```
Base 500M did not hit this; only Turbo's `prepare_conditionals` path does.

---

## 5. The rest, briefly (and why they're out)

- **XTTS-v2 / Coqui.** 17 languages, 6 s clone, genuinely good. **CPML weights = non-commercial. Out on licence.** Live fork is `idiap/coqui-ai-TTS` (`coqui-tts` 0.27.5, MPL-2.0, py3.10–3.14, torch 2.2+, has a cloned-voice cache since 0.27.0) — good code, wrong weights.
- **OpenVoice v2.** MIT since April 2024 ("free for commercial use"), en/es/fr/zh/ja/ko. But architecturally it's **MeloTTS base + a tone-colour converter** — and `melotts` pins `torch<2.0`, `transformers==4.27.4`, `mecab-python3`, `gruut`. On ARM64 that's unbuildable. Also ~126 commits, effectively unmaintained since Apr 2024. It's a *timbre* converter, not a prosody cloner, so it wouldn't give you "Dad's delivery" anyway — only "Dad's tone on MeloTTS's rhythm." **Out on dependency hell + weaker fit.**
- **F5-TTS.** MIT code, **CC-BY-NC checkpoints**. RTF 0.0394 on an L20 GPU with 16 NFE — irrelevant, we have no NVIDIA GPU. v1 base Mar 2025. Community `F5-TTS-ONNX` exists. **Out on licence.**
- **Fish Speech / OpenAudio.** S2 Pro 4B, RTF 0.195 and ~100 ms TTFA **on an H200**, 10–30 s reference. **"Fish Audio Research License" — proprietary, commercial restrictions. Out on licence and on hardware.**
- **Zonos-v0.1 (Zyphra).** Apache-2.0 (nice!), 200k+ hours, 10–30 s sample. But **6 GB+ VRAM minimum, "CPU operation possible but impractical for interactive use"**, hybrid variant needs an RTX 3000+, Windows only via a community fork, RTF ~0.5 on a 4090. **Out on hardware.**
- **MeloTTS.** MIT and *does* have a first-class NPU path — but **only via Qualcomm AI Hub (§3.2)**, not via the Python package. Use the AI Hub export; ignore PyPI.
- **Piper.** Fast, no cloning, and the definitive "just works" CPU TTS — but `piper-tts` 1.6.0 is **GPL-3.0-or-later**. Use the AI Hub MIT export instead (§3.1).
- **Kokoro-82M.** Apache-2.0, 82 M params, no cloning. Voice grades: **`af_heart` = A (best overall), `af_bella` = A− (marked 🔥, warm), `af_nicole` = B−**; `am_michael` / `am_fenrir` = C+ for male. `af_heart` or `af_bella` is your elder voice. `kokoro` (PyPI) needs torch + `misaki[en]` and caps at py<3.13; **`kokoro-onnx` needs no torch at all** — use that.
- **Sherpa-ONNX.** Apache-2.0, supports VITS/Matcha/Piper/Kokoro **and** zero-shot cloning via **ZipVoice** and **Pocket TTS**. 12 language bindings, C/C++/C#. **No `win_arm64` Python wheel** (win_amd64/win32 only) — but it *does* ship `manylinux2014_aarch64`. **Verdict: wrong tool for the PC, right tool for the UNO Q and Android.** (C++ is Apache-2.0 + CMake, so a from-source `win_arm64` build is possible but is not a 4-day-budget item.)
- **ZipVoice (k2-fsa).** **Apache-2.0 code *and* weights**, only **123 M params**, zero-shot clone from **<3 s**, official ONNX export with INT8, zh+en, ZipVoice-Dialog released 14 Jul 2025. **This is the dark-horse option:** it's the only Apache-2.0-weights zero-shot cloner small enough to be plausible on ARM64 CPU, and ONNX means no torchaudio problem at all. Downside: no published CPU RTF, less proven than Chatterbox, no built-in watermark. **If the Chatterbox shim fights back, benchmark ZipVoice-ONNX before reaching for the cloud.**

---

## 6. Commercial fallback: ElevenLabs

- **Flash v2.5: ~75 ms model latency** (excl. network/app). Turbo v2.5 is "functionally equivalent" with slightly higher average latency. Multilingual v2 = highest quality, higher latency.
- **Instant Voice Cloning (IVC)** from a short sample; **Professional Voice Cloning (PVC)** requires longer audio *and* identity verification. ⚠️ *Not verified in this session* — the ElevenLabs voice-cloning docs pages 404'd on every URL tried, so treat the IVC/PVC minimum-duration and verification specifics as recalled, not confirmed. Check before quoting in the deck.
- Integration cost: minutes. Keep it behind `QNET_TTS_BACKEND=elevenlabs`.
- **Pitch discipline:** our whole thesis is privacy-first / on-device. If you demo the cloud path, you hand a judge the obvious question. Wire it, don't demo it — and if asked, the answer is *"on-device is the product; the cloud adapter exists so the architecture is provably backend-agnostic."*

---

## 7. Consent-based voice registration — making this read as responsible AI, not creepy

### 7.1 The timing gift: **EU AI Act Article 50 became applicable on 2 August 2026 — the day before the hackathon started.**

Per Article 113, Article 50's transparency obligations apply from **2 Aug 2026**. Our feature is squarely in scope, and that is an *opportunity*: a compliance story that is 24 hours old is a differentiator no other team will have thought about.

What Article 50 requires:
- **Providers** must mark synthetic output in a **machine-readable format** as artificially generated/manipulated, with solutions that are *"effective, interoperable, robust and reliable as far as this is technically feasible."*
- **Deployers** must **disclose** that content is artificially generated **"in a clear and distinguishable manner at the latest at the time of the first interaction."**

We can satisfy **both** limbs, and demonstrate it live:
- **Machine-readable marking:** Chatterbox **already embeds Resemble AI's Perth (Perceptual Threshold) neural watermark in every generated file**, robust to MP3 compression and editing, with ~100% claimed detection accuracy. Perth is **MIT** and runs on CPU. **We verified the full embed→detect round-trip on this ARM64 machine** (`PerthNet (Implicit) at step 250,000`, detector output `1.0`). Note `resemble-perth` 1.0.1 declares **no dependencies at all** but actually imports `torch` *and* `torchaudio.transforms` at runtime — an undeclared-dependency bug that is exactly what produced the misleading `NoneType` error in §4.3.
- **Cleaner alternative — prefer this if you don't want Perth in the loop:** **AudioSeal** (Meta) is **MIT including weights** and its declared deps are just `numpy, omegaconf, torch>=1.13.0, einops` — **no torchaudio**, so it needs *no shim at all* on Windows-on-ARM. Plus sample-level (1/16000 s) localisation and detection ~2 orders of magnitude faster. Chatterbox gives you Perth for free; adding AudioSeal on top costs ~15 minutes and gives a second, independent detector to show a judge.
- **Clear disclosure at first interaction:** the first cloned-voice utterance in any session is prefixed with a spoken tag in the *system* voice — *"Message from Dad, spoken by QNet"* — before switching to the cloned voice.

> ### ✅ Killer demo beat — **already proven on this machine, with a negative control**
> We ran the detector over our own generated audio on the X Elite:
> ```
> out/chatterbox_turbo_run1.wav   3.44s   watermark_detected = 1.0   <- cloned voice: FLAGGED
> out/kokoro_fp32_short.wav       4.82s   watermark_detected = 0.0   <- normal TTS: NOT flagged
> ```
> **That is a positive *and* a negative control, on-device, in one screenshot.** It proves the marking is real and the detector doesn't just always answer "yes" — which is the obvious question a sharp judge will ask, and you can pre-empt it.
>
> **Build `qnet verify <file>` as a CLI subcommand** (≈20 min, the plumbing above already works) and invite a judge to run it on a file of their choosing. Demonstrating EU AI Act Article 50 compliance live, 24 hours after it became applicable, is a differentiator no other team will have.

### 7.2 Also worth one line of awareness
Tennessee's **ELVIS Act** (voice as a protected property right, effective Jul 2024) and the federal **NO FAKES Act** (reintroduced in the 119th Congress; would create a federal right against unauthorised voice/likeness replicas, with consent requirements) show the direction of travel. Mentioning that our consent record is designed to be the artefact these regimes ask for lands well.

### 7.3 The registration flow (design it as a ceremony, not a settings toggle)

The single most important design choice: **make enrolment feel like signing something, and make it visibly hard to do to someone else.**

1. **Physical-presence gate.** Enrolment can only be started from the Copilot+ PC, and only with a **6-digit code shown on the PC screen that must be spoken aloud** into the mic. This proves the person is (a) physically present and (b) not a recording. Cheap to build, immediately legible to a judge.
2. **Spoken consent script, recorded and retained.** The enrollee reads a fixed sentence — *"I am Michael Chen. On the third of August 2026, I consent to QNet Home creating a synthetic model of my voice, to be used only to speak to my own family inside my own home. I understand I can delete it at any time."* This audio **is** the consent record, and conveniently it doubles as part of the 30–60 s reference material. One artefact, two jobs.
3. **Two-party confirmation for the child scenario.** The *other* registered guardian must approve on their phone before the voice goes live. Nothing makes "we thought about abuse" clearer than showing a feature that one adult cannot unilaterally enable.
4. **Scoped, expiring grant.** Store `{speaker_id, purpose, allowed_rooms, allowed_recipients, created_at, expires_at (default 90 days), consent_audio_hash, revocation_token}`. Voice grants **expire and must be renewed** — a decision that costs 5 lines and signals maturity.
5. **Local-only, encrypted at rest.** Reference audio and speaker embedding never leave the PC; encrypt with **Windows DPAPI** (or a TPM-bound key). Say plainly: *"the voice model is bound to this machine's TPM; it does not survive being copied."*
6. **One-tap revocation + real deletion.** A **"Delete my voice"** button that wipes embedding, reference audio and consent record, and is reachable from *any* enrolled phone. Show the file disappearing.
7. **Tamper-evident audit log.** Every cloned-voice utterance appends `{timestamp, text, requester, room, watermark_id}` to a **hash-chained** local log, viewable in the UI. Judges love an append-only log they can scroll.
8. **Hard content guardrails.** The cloned voice is **only** permitted to speak (a) LLM-generated de-escalation lines from a constrained template set, or (b) text the *verified* parent typed from their own enrolled device. It can never read arbitrary text, never take dictation from the LLM unsupervised, and never speak to a non-family listener.
9. **Audible identity, always.** Never impersonate silently. Session-first disclosure (§7.1) plus a subtle recognisable chime under cloned speech.
10. **Child-appropriate framing.** In the kid scenario the line is *"Dad asked me to tell you…"* — assistance relaying a real message from a real parent, **not** deception. This one wording choice is the difference between "warm" and "creepy," and it should be said explicitly on the slide.

**The one-sentence framing for the pitch:** *"We are not synthesising a person — we are giving a consenting parent a way to be present in their own home when they physically can't be. The voice is enrolled in person, watermarked on every utterance, logged immutably, expires in 90 days, and can be deleted from any family phone in one tap."*

### 7.4 Anti-patterns to avoid on stage
- Don't clone a **judge's** or a **celebrity's** voice as a party trick. Use a **team member's own voice**, and show their consent recording. If someone suggests cloning a famous voice for laughs, that is the single fastest way to lose the innovation and presentation points.
- Don't say "deepfake." Say **"consented voice enrolment."**
- Don't let the cloned voice deliver the *emergency* content. Emergencies use the neutral system voice — a familiar voice is for comfort and social influence, not for authority. This distinction is itself a good design point to voice aloud.

---

## 8. Decision summary & what to do in the next 4 days

**Architecture (two TTS paths, one API):**
```
QNet TTS service  (single interface: speak(text, voice_id, priority))
├── voice_id="system"  → PiperTTS-EN on Hexagon NPU  (~61 ms, MIT, 100% NPU)
│                        fallback: Kokoro fp32 ONNX CPU (RTF 0.276)
│                        fallback: Windows SAPI5 (RTF 0.009, always works)
└── voice_id="parent:*" → CACHE FIRST: pre-synthesised line set (0 ms)   <-- the common case
                          miss → Chatterbox Turbo CPU, ARM64 + shim (MIT, RTF 3.3, ~12 s)
                          free text → ElevenLabs Flash v2.5 (~75 ms), feature-flagged
                          (escape hatch: Chatterbox under x64 Prism emulation, no patching)
```
Latency budget — **the asymmetry is the design, so say it out loud:** the elder reassurance line is on the critical path (fall detected → speak) and must be **<1 s**; the NPU path delivers it with ~15× headroom. The cloned parent line is **not** on the critical path, *and* it is drawn from a constrained template set — so it is served from a **pre-generated cache at 0 ms**, with live synthesis only for free text. Two paths, two completely different engineering answers, both justified by measurement rather than taste.

**Ordered task list:**
1. **(2 h, do first)** Kokoro fp32 ONNX behind the `speak()` API. Makes the whole demo work end-to-end today and de-risks everything downstream. Already installed and benchmarked.
2. **(4 h, highest scoring value)** `PiperTTS-EN` from AI Hub via `onnxruntime-qnn` 2.4.0 on the NPU. Reproduce the 61.5 ms on our own box so the deck's number is *ours*, and chart it against the Kokoro CPU baseline. **This is the 40-point slide — do it before the cloning work.**
3. **(3 h)** Chatterbox Turbo + our verified shim + the **pre-synthesised line cache**. The shim and dtype fix are already done; the remaining work is the cache and the registration-time generation pass. Try Nano via git install (`ChatterboxTurboTTS.from_pretrained(device="cpu", nano=True)`) and measure it — if Nano lands near RTF 1.0, live synthesis for short lines becomes viable too.
4. **(2 h)** Consent ceremony + Perth/AudioSeal live detector + `qnet verify` CLI. Watermark round-trip already proven on ARM64 (§4.3).
5. **(1 h)** Wire the ElevenLabs flag for free-text parent messages only.

**The four numbers for the deck:**
- `61.5 ms, 100% NPU (1,689/1,689 layers), ≤4 MB peak` — system TTS on Hexagon.
- `RTF 0.276 on X Elite CPU` — the honest Kokoro baseline the NPU number is measured against (~15× speedup).
- `int8 was 2.2× slower than fp32 on ARM64` — we measured instead of assuming.
- `Chatterbox Turbo RTF 3.3 → 0 ms via pre-synthesis` — we found the wall and engineered around it.

**Framing note for the pitch:** every one of those four is a *measured* number with a *baseline*, and two of them are negative results we turned into design decisions. That reads as engineering maturity, which is worth more on the Technical Implementation criterion than a bigger model would be.

---

## 9. Open items / gaps in this report

Flagging these rather than papering over them:
- **Chatterbox Nano is the biggest open question and it is on the critical path.** Its "3× realtime on 8 cores" (RTF 0.33) is Resemble's claim, **unverified by us**, and it implies a 10× gain over our measured Turbo number from only a 3.2× parameter cut — which is implausible on its face. Nano also isn't reachable from PyPI 0.1.7 (needs `git clone` + `pip install -e .`). **Measure it on day 1**; if it lands near RTF 1.0 the cloning UX gets much better, and if it doesn't, the pre-synthesis cache (§4.5) is load-bearing rather than merely nice.
- **Turbo/base numbers are single-configuration.** `device="cpu"`, 12 threads, one ~8.8 s reference clip, one short sentence, 3 runs. No sweep over thread count, reference length, or sentence length; no attempt at `torch.compile`, quantisation, or KV-cache tuning. There is likely meaningful headroom in Turbo's RTF 3.3 that we did not go after.
- **The reference clip used for cloning was SAPI-generated synthetic speech**, not a real human voice. It exercises the pipeline correctly but says nothing about clone *fidelity* from real audio.
- **AI Hub latencies in §3 are Qualcomm-published, not ours.** They are from `Snapdragon X Elite CRD` (a reference design, not our exact laptop), and the `voice_ai` runtime asset's Windows deployment path is not yet proven by us. Reproduce locally before quoting as our own.
- **Perth's "~100% detection accuracy" is a vendor claim**; the live-detector demo is what makes it credible, so build the demo.
- **Clone *quality* from 30–60 s was not subjectively assessed** — no listening test was run. Do a quick A/B with a real team member's voice on day 2; naturalness is what sells the feature, and no RTF number substitutes for it.
- **TTS Arena V2 ELO rankings could not be retrieved** (the HF Space renders client-side), so no independent quality ordering is cited here. The web-search budget for this session was exhausted at the outset, so all findings above come from direct source fetches and local measurement rather than survey.

---

## Sources

**Models & repos**
- Chatterbox (Resemble AI) — https://github.com/resemble-ai/chatterbox
- Chatterbox on HF — https://huggingface.co/ResembleAI/chatterbox
- Chatterbox Turbo — https://huggingface.co/ResembleAI/chatterbox-turbo
- Chatterbox Nano — https://huggingface.co/ResembleAI/chatterbox-nano
- `chatterbox-tts` on PyPI — https://pypi.org/project/chatterbox-tts/
- Coqui TTS (unmaintained) — https://github.com/coqui-ai/TTS
- XTTS-v2 weights + CPML — https://huggingface.co/coqui/XTTS-v2
- Maintained Coqui fork — https://github.com/idiap/coqui-ai-TTS
- F5-TTS — https://github.com/SWivid/F5-TTS
- Fish Speech / OpenAudio — https://github.com/fishaudio/fish-speech
- OpenVoice — https://github.com/myshell-ai/OpenVoice
- Zonos (Zyphra) — https://github.com/Zyphra/Zonos
- Kokoro — https://github.com/hexgrad/kokoro
- Kokoro voices & grades — https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
- kokoro-onnx (+ model release assets) — https://github.com/thewh1teagle/kokoro-onnx
- Piper (`piper1-gpl`, GPL-3.0) — https://github.com/OHF-Voice/piper1-gpl
- sherpa-onnx — https://github.com/k2-fsa/sherpa-onnx
- ZipVoice — https://github.com/k2-fsa/ZipVoice
- MeloTTS on PyPI — https://pypi.org/project/melotts/

**Qualcomm**
- AI Hub audio models — https://aihub.qualcomm.com/models?domain=Audio
- PiperTTS-EN — https://aihub.qualcomm.com/models/pipertts_en
- MeloTTS-EN — https://aihub.qualcomm.com/models/melotts_en
- ai-hub-models (BSD-3-Clause) — https://github.com/qualcomm/ai-hub-models
- ai-hub-apps (Whisper Windows app, Genie ChatApp) — https://github.com/quic/ai-hub-apps
- `onnxruntime-qnn` — https://pypi.org/project/onnxruntime-qnn/

**Windows-on-ARM toolchain**
- PyTorch CPU wheel index (`win_arm64` lives here, not PyPI) — https://download.pytorch.org/whl/cpu
- PyTorch install matrix — https://pytorch.org/get-started/locally/
- WinRT SpeechSynthesizer — https://learn.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer
- numpy / onnxruntime / librosa wheel availability — https://pypi.org/

**Watermarking, safety & law**
- Perth watermarker (MIT) — https://github.com/resemble-ai/perth
- AudioSeal (MIT incl. weights) — https://github.com/facebookresearch/audioseal
- pytorch/audio LICENSE (BSD-2-Clause, governs the vendored `kaldi.py`) — https://github.com/pytorch/audio/blob/main/LICENSE
- **EU AI Act Article 50 — applicable 2 Aug 2026** — https://artificialintelligenceact.eu/article/50/
- NO FAKES Act (S.1367, 119th Congress) — https://www.congress.gov/bill/119th-congress/senate-bill/1367

**Commercial fallback**
- ElevenLabs models & latency (Flash v2.5 ~75 ms) — https://elevenlabs.io/docs/overview/models
