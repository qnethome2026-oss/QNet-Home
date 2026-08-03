# Qualcomm Cloud AI 100 (AIC100) for QNet Home — Access, API, and the Right Architectural Role

*Research date: 2026-08-03. All API facts below were verified by fetching live endpoints/specs, not from memory. Where a fact could not be verified without a logged-in account it is marked **[unverified]**.*

> **Note on method:** the WebSearch budget for this session was exhausted before I started, so everything here comes from direct fetches of Qualcomm/Cirrascale/GitHub URLs, the live Imagine OpenAPI spec, the published `python-imagine-sdk` wheel, and the Cirrascale playground's own JS bundles. That is actually *better* evidence than search snippets — several findings below (the exact base URL, the LoRA fine-tuning schema, the proprietary-license landmine) are not documented in any blog post.

---

## 1. TL;DR — the recommendation

**Use AIC100 as QNet Home's factory and test lab, not as its runtime.**

Concretely, three roles, in priority order:

| # | Role | Effort | Why it wins points | Privacy risk |
|---|---|---|---|---|
| **P0** | **Digital-twin scenario generator + agent grader ("QNet Simulator")** — a 70B on AIC100 generates hundreds of adversarial synthetic event traces (falls, near-falls, dropped-pan-not-a-fall, kid fighting vs. playing) and *grades* the local SLM's decisions. Output = a scored eval suite committed to the repo. | ~0.5 day | Hits Technical Implementation (measured correctness + latency numbers), Docs (rubric explicitly rewards tests), and Innovation (nobody else red-teams their agent). | **Zero** — cloud sees only synthetic data, by construction. |
| **P1** | **Opt-in "second opinion" escalation tier** with a *visible redaction diff* — when the local SLM is low-confidence, send a schema-validated, PII-stripped JSON event summary to the 70B. The UI renders the exact bytes that left the house. | ~0.5 day | Turns the cloud call into a privacy *demo* instead of a privacy hole; gives AIC100 a live runtime path so judges see all 4 devices working. | Low + auditable, default OFF, degrades to local-only. |
| **P2** | **Nightly batch care summary** for family, generated at 3 a.m. from aggregated counts (no raw events). | ~0.3 day | "Burst compute off the hot path" is a genuine energy-efficiency argument: the hub NPU stays cold. | Low (aggregates only). |

**Explicitly reject:** voice-clone / TTS fine-tuning on AIC100 (§7.4 — there is no TTS in the served stack at all), and any claim of on-device model distillation from fleet data (§7.2 — no weight-export path off the platform).

**One-line pitch for the deck:** *"The cloud accelerator is where cloud work belongs — big-model batch jobs, offline, at night, on synthetic data. It never sees your home. It's how we prove the home agent is correct, not how it thinks."*

**Blocking action for Day 1 (Aug 3):** ask the organizers, in writing, *which* AIC100 endpoint the team is entitled to (an internal Qualcomm Imagine endpoint, or self-signup on the Cirrascale playground) and get an API key issued. Both paths use the identical API (§3), so build against the public one and swap `IMAGINE_API_ENDPOINT` later. Do not let this block anything else — see the fixture strategy in §9.

---

## 2. How developers get to AIC100 as of Aug 2026 — four paths

### Path A (recommended): Qualcomm AI Inference Suite → "Imagine" playgrounds — free, API-key, minutes to first token

Qualcomm's productized way to *use* AIC100 without owning a card. Three regional playgrounds, all free to test:

| Playground | Region | URL |
|---|---|---|
| **Cirrascale Inference Cloud** | United States | https://aisuite.cirrascale.com/ |
| Core42 | UAE | https://playground.core42.ai/ |
| ALLaM | Saudi Arabia | https://allam-playground.com/ |

The Cirrascale site's own `<title>` is literally **"INFERENCE CLOUD | powered by Qualcomm Cloud AI 100 Ultra"** — so the free playground is AI 100 **Ultra** silicon (§6). Cirrascale's product page says the service offers "API endpoints", "token-based pricing", and "high availability and strict data privacy with no storage of model inputs or outputs" — note the tension with §5.2.

Onboarding, per Qualcomm's own page: (1) `pip install python-imagine-sdk`, (2) "Select an AI inference playground and generate an API key", (3) read the getting-started guide.

The playground app (routes recovered from its Next.js build manifest) includes: `/account/api-keys`, `/account/credits`, `/billing/overview`, `/models/overview` (rate limits), `/models/pricing`, `/models/usage`, `/models/byom`, `/models/fine-tuning`, `/apps/chat`, `/apps/embed`, `/apps/images`, `/developer/get-started`, `/developer/tutorials`, and four ready-made agent demos (`course-creator-agent`, `customer-review-summarizer-agent`, `research-watch-agent`, `stock-watch-agent`). Auth is NextAuth (`/api/auth/signin`).

### Path B: an internal Qualcomm Imagine endpoint

The SDK takes the endpoint from `IMAGINE_API_ENDPOINT` / the `endpoint=` kwarg, with the documented form `https://my-endpoint/api/v2`. Qualcomm-internal Imagine deployments exist and are configured the same way; support contact in the OpenAPI spec is `imagine.support@qualcomm.com`, and Cloud AI support generally is `cloudai@qti.qualcomm.com`. **If the hackathon kit "includes AIC100", this is almost certainly what it means** — an endpoint + key, not a PCIe card. Ask the organizers.

### Path C (do not attempt this week): a real card + the qaic SDK

For completeness, because it is where the "40 points of optimization" vocabulary comes from:

- Instances: **AWS `DL2q`** (Cloud AI 100 Standard) and **Cirrascale Cloud Services** (1–8 accelerators per instance). Qualcomm's docs state *"SDKs are pre-installed on cloud instances."* On-prem installs pull the Platform SDK / Apps SDK from QPM.
- Toolchain: **Cloud AI SDK 1.21** (current docs branch) — `qaic-compile`, `qaic-runner`, `qaic-monitor`, `qaic-util`, `aic-manager` (with Prometheus/Grafana metrics), ONNX Runtime QAIC EP, Triton (qaic / vllm / python-llm / embedding backends), Kubernetes, Docker.
- LLMs: **QEfficient / `quic/efficient-transformers`** (HF → AIC-optimized ONNX → QPC), plus **vLLM with `--device qaic`**.
- Fine-tuning on-card exists ("PyTorch eager mode") but is narrow: **x86 host only, Python 3.10 only, Torch 2.9.1 only, FP32/FP16/Int32/Int64/Bool only.**

Effort to get from zero to a compiled custom model on a card is measured in days, not hours. With 4 build days total, Path C is a losing bet.

### Path D: LoRA fine-tuning and BYOM *on the playground* (no card needed)

This is the sleeper feature and it is real. `/models/fine-tuning` submits a **supervised LoRA SFT job** against any accessible Hugging Face model; `/models/byom` compiles it and deploys it behind the normal inference API. Schema recovered from the page bundle:

```jsonc
{
  "model": "<huggingface/repo-id>",          // autocomplete-searched against HF
  "dataset_input_fields":  ["..."],           // JSONL columns used as input
  "dataset_output_fields": ["..."],           // JSONL columns used as target
  "method": {
    "type": "supervised",
    "supervised": {
      "hyperparameters": {
        "num_epochs": 1,                      // default 1
        "lr": 0.0003,                         // default 3e-4
        "train_batch_size": 1,                // default 1
        "gradient_accumulation_steps": 1,
        "tokenizer_name": "...",
        "peft_config": {                      // omit + use_default_peft_config:true
          "r": 8, "lora_alpha": 16, "lora_dropout": 0.05,
          "target_modules": ["q_proj","v_proj"],
          "bias": "none", "task_type": "CAUSAL_LM", "inference_mode": false
        }
      }
    }
  },
  "seed": 42,
  "hf_token": "hf_...",                       // required
  "use_default_peft_config": true,
  "compile_model": true,                      // compile after training
  "compilation_mode": "...",
  "enable_ddp": false, "nproc_per_node": 1     // DDP for large datasets
}
```

Datasets are uploaded as **JSONL** (the page ships a `Download Sample Dataset` button), split Training/Validation, and are reusable across jobs. Job lifecycle strings: `downloading_model → pre_compilation → compilation_initiated → finetune_completed → compiling → model_compiled → model_started (Active)`. UI text: *"Compiled models are optimized for our AI100 infrastructure"*, *"Your fine-tuned models are only accessible to you"*, *"Access your fine-tuned models through standard API endpoints for inference"*.

**Critical limitation:** every "download" string in the BYOM bundle refers to pulling *from* Hugging Face *into* the platform. **I found no path to export trained weights/adapters back out.** So Path D can give you a better *cloud* model; it cannot hand you a LoRA to run on the X Elite NPU. This kills the naive "cloud distills, edge runs it" story (§7.2).

---

## 3. The API surface (verified against the live OpenAPI spec)

Spec: `https://aisuite.cirrascale.com/imagine-api-docs` (Scalar UI with OpenAPI 3.1.0 embedded in the page as JSON).
Title: **"Qualcomm Imagine APIs"** — *"These APIs provide the capability to run inference on Qualcomm AI100 devices."* Spec version 1.0.0, license MIT, contact `imagine.support@qualcomm.com`. `servers: [{ "url": "/apis" }]`.

**Base URL (verified live): `https://aisuite.cirrascale.com/apis/v2`**

```
$ curl -s https://aisuite.cirrascale.com/apis/v2/models
{"message":"Invalid API key, No Authorization header found","status":"error"}   # HTTP 500
```

Auth: `Authorization: Bearer <API_KEY>` (`securitySchemes: {"Bearer Token": {type: http, scheme: bearer, bearerFormat: JWT}}`).

| Method + path | Purpose |
|---|---|
| `POST /v2/chat/completions` | New conversation (chat, streaming, **tool calling**, multimodal image input) |
| `POST /v2/chat/completions/{id}` | Continue a **server-stored** conversation |
| `GET  /v2/chat/completions` | **Chat completion history** |
| `POST /v2/completions` · `GET` | Raw completion + history |
| `POST /v2/embeddings` · `GET` | Embeddings + history |
| `POST /v2/images/generations` · `GET` | Text-to-image (url or b64_json, streaming) |
| `POST /v2/transcribe` · `GET` | Speech-to-text (multipart `file` + `file_name` + `model`) |
| `POST /v2/translate` · `GET` | NMT (Helsinki opus-mt; also an `IndicTranslationRequest` schema) |
| `POST /v2/reranker` · `GET` | Cross-encoder rerank |
| `GET  /v2/models` | Model list **← call this first; it is the ground truth for what's served today** |
| `GET  /v2/health`, `GET /v2/ping` | Liveness |

Sampling params supported: `max_tokens, temperature, top_p, top_k, do_sample, num_beams, frequency_penalty, presence_penalty, repetition_penalty, stop, stop_token_ids, include_stop_str_in_output, skip_special_tokens, ignore_eos, max_seconds`. `stream`, `stream_options.include_usage`, and `usage {prompt_tokens, completion_tokens, total_tokens}` are present.

### 3.1 OpenAI compatibility — "yes, mostly", with three sharp edges

Qualcomm markets "OpenAI-compatible APIs", and their own SDK docs include a **LiteLLM** tutorial using the OpenAI provider prefix:

```python
import litellm
# litellm.api_base = "https://aisuite.cirrascale.com/apis/v2"
# litellm.api_key  = "<key>"
response = litellm.completion(
    model="openai/Llama-3.1-8B",
    messages=[{"role": "user", "content": "..."}],
    max_tokens=1024,
)
```

So the practical move is: **use the stock `openai` Python client with `base_url=".../apis/v2"`** — no proprietary SDK needed (which matters a lot; see §5.1). Sharp edges found in the spec:

1. **No `/v1` prefix and no `response_format` / JSON-schema guided decoding.** `SamplingParams` has no `response_format`, no `guided_json`. If you need structured output, use **tool calling** or prompt + validate + retry. (Note: guided decoding *does* exist in Qualcomm's vLLM-on-qaic serving stack — just not on the managed Imagine API.)
2. **Tool schema deviation.** The spec's `Function` object is `{name, description, arguments}` — OpenAI uses `parameters`. The official example sends `tools[].function.arguments` containing the JSON Schema. Expect to remap if you generate tool defs with LangChain's `convert_to_openai_tool`. Budget 30 minutes for this.
3. **Multimodal content shape is serde-tagged** (`Content` is a `oneOf` over `{"String":…}` / `{"Vec":[…]}` / `{"MultiModal":[{"Text":…}|{"Image":{"image_url":{"url":…}}}]}`). The *examples* use plain OpenAI-style `"content": "Hello!"`, so untagged/OpenAI shapes are accepted for text; **verify the image path by experiment before designing around it.** Vision input is clearly supported — which model serves it is **[unverified]** until you `GET /v2/models`.

Minimal working call (no Qualcomm SDK, MIT-safe):

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://aisuite.cirrascale.com/apis/v2",   # or the internal endpoint
    api_key=os.environ["IMAGINE_API_KEY"],
)
r = client.chat.completions.create(
    model="Llama-3.1-70B",
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    max_tokens=512, temperature=0.1, stream=False,
)
```

### 3.2 Rate limits, credits, pricing

The playground's `/models/overview` page renders, per model, quotas labelled **Requests / Tokens × Per Minute / Per Hour / Per Day**, plus an "Available / Rate Limited" status. `/models/pricing` renders `input_price` / `output_price` per model plus a `sequenceLength: 512` tier for embedding-style models. There is a credits system (`/account/credits`, `/billing/payments-history`, `"No Credits Available"` error state). **Actual numeric limits and prices are rendered at runtime from the API and could not be read without an account — [unverified].**

**Design implication:** assume the free tier is *tight* and *daily*. Never put a live cloud call on the demo's critical path without a cached fallback (§9).

---

## 4. What models are actually served

### 4.1 On the managed Imagine API — the observable set

Model IDs appearing in the live OpenAPI examples and as SDK defaults:

| Type | Model IDs |
|---|---|
| LLM | `Llama-3.1-8B` (SDK default), **`Llama-3.1-70B`** (used for the tool-calling example), `mistralai/Mistral-7B-Instruct-v0.1`, `Salesforce/xgen-7b-8k-inst`, `core42/jais-30b-chat-v1` |
| Embedding | `BAAI/bge-large-en-v1.5` (default), `BAAI/bge-small-en-v1.5` |
| Reranker | `BAAI/bge-reranker-base` (default) |
| Text-to-image | `stabilityai/sdxl-turbo` |
| Transcribe | `whisper-tiny` (default) |
| Translate | `Helsinki-NLP/opus-mt-en-es`, `-en-fr` |

Caveat: the spec is version 1.0.0 and its examples look ~2024-vintage (Llama 3.1 era). The `python-imagine-sdk` on PyPI is still **0.5.0, released 2025-07-18** — i.e. **not updated in ~12 months**, another reason to skip it. The served catalog has very likely moved on; **`GET /v2/models` is the only trustworthy list.** Plan for "a Llama-3.1-70B-class model is available" and confirm on Day 1.

**There is no TTS / `audio/speech` endpoint. At all.** This is the single most important negative finding for our use case 2.

### 4.2 What AIC100 *can* run (QEfficient validated list, for credibility in the deck)

`quic/efficient-transformers` (60+ architectures) — recent entries with dates, straight from the README:

- **07/2026** `dynamo` flag for `torch.onnx.export`-based ONNX export
- **06/2026** Gemma4 (`google/gemma-4-E2B-it`, `gemma-4-26B-A4B-it`), **Qwen3.6-35B-A3B**, Qwen3.5-0.8B, **Qwen3-VL / Qwen3-VL-MoE** (`Qwen3-VL-30B-A3B-Instruct`, `Qwen3-VL-32B-Instruct`), **GLM-4.5 MoE** (with disaggregated mode)
- **04/2026** WAN non-unified execution (`transformer_high`/`transformer_low`) + first-block-cache for WAN and FLUX
- **12/2025** disaggregated serving for gpt-oss; `facebook/wav2vec2-base-960h` (ASR); **WAN 2.2 T2V-A14B** video generation; **FLUX.1-schnell**; `openai/gpt-oss-20b`; `InternVL3_5-1B`; OLMo-2
- Earlier: Llama 4 Scout, Gemma 3, Molmo-7B, Mistral-Small-3.1-24B, Qwen2.5-VL-32B, SwiftKV, GGUF execution, FP8, AWQ/GPTQ, PEFT/LoRA finite adapters, speculative decoding (draft + TLM/multiprojection)
- The README header now carries a **"Qualcomm AI200 rack"** image and the library targets *"Qualcomm Cloud AIxxx (AI100, AI200 and so on)"*.

`quic/cloud-ai-sdk` model recipes: `models/{language_processing/{decoder,encoder}, vision/{classification,detection,segmentation}, multimodal/text_to_image, speech}`. **`models/speech` contains exactly one entry: `whisper`.** `text_to_image` has DeciDiffusion-v2-0, sdxl_deepcache, sdxl_turbo, SD-3.5-medium, SD-v1-5, SDXL-base-1.0.

Roadmap context worth one slide: Qualcomm announced **AI200 (768 GB LPDDR per card, 160 kW rack, direct liquid cooling, confidential computing) for 2026 and AI250 (near-memory computing, ">10x higher effective memory bandwidth") for 2027** on 2025-10-28.

---

## 5. Two landmines you must know about before writing a line of code

### 5.1 The Imagine SDK license is proprietary — and our repo must be open source

The submission rules require an open-source GitHub repo with an OSS license. The `python-imagine-sdk` license is `LicenseRef-Proprietary`, and the Qualcomm EULA shipped in its docs states, among other things:

- redistribution only as **binary**, never source;
- redistributable binary "may only operate in conjunction with platforms incorporating Qualcomm Technologies, Inc. chipsets";
- *"You shall not subject the Materials to any third party license terms (e.g., open source license terms)"*;
- no use of Qualcomm names/logos/trademarks.

**Action: do not vendor, bundle, or wrap the Imagine SDK in the QNet Home repo.** Talk to the endpoint with `openai`/`httpx`/`requests` (§3.1), list the API as an optional external service in the README, and keep the key in an env var / `.env.example`. This costs us nothing (the SDK adds no value over an HTTP call) and removes a genuine "commercially-ready quality" objection a Qualcomm judge might actually raise.

### 5.2 The Imagine API stores conversation history server-side

The API has `GET /v2/chat/completions` ("Chat Completion History"), `GET /v2/completions`, `GET /v2/embeddings`, `GET /v2/transcribe`, `GET /v2/images/generations` history endpoints, a `ConversationSummaryResp` schema, and `POST /v2/chat/completions/{id}` to resume a stored conversation. Cirrascale's marketing page separately claims "no storage of model inputs or outputs". Those two statements are in tension.

**Action:** (a) treat everything we send as *retained and later readable*; (b) make **stateless** calls only — never pass an `id`, never use the `/{id}` continuation endpoint for anything derived from a real home; (c) say this out loud in the README's threat model. Judges reward teams that state their trust boundaries precisely. This finding is also the strongest possible argument for the P0 role: if the cloud logs everything, then only synthetic data belongs there.

---

## 6. Hardware and latency characteristics (numbers for the deck)

| | AI 100 **Ultra** | AI 100 **Pro** | AI 100 **Standard** |
|---|---|---|---|
| INT8 | up to **870 TOPS** | up to 400 TOPS | up to 350 TOPS |
| On-die SRAM | 576 MB | 144 MB | 126 MB |
| DRAM | 128 GB LPDDR4x | 32 GB | 16 GB |
| Bandwidth | 548 GB/s | 137 GB/s | 137 GB/s |
| TDP | **150 W** | 75 W | 75 W |
| Form factor | PCIe FH¾L | PCIe HHHL | PCIe HHHL |

(The same page also lists AI 80 Ultra at 618 TOPS and AI 80 Standard at 190 TOPS.) The Cirrascale free playground is **Ultra**-based.

**Measured latency from Qualcomm's own vLLM-on-qaic benchmark docs** (TinyLlama-1.1B-Chat, 64-in/128-out, 50 prompts, concurrency 5):

- Mean **TTFT 111.49 ms** (median 114.86, P99 121.05)
- Mean **TPOT 14.18 ms**, mean ITL 14.07 ms → ~70 tok/s per stream
- Output throughput **334.14 tok/s**, total **496.10 tok/s**, 2.61 req/s

Launch command (shows the optimization vocabulary judges respond to):

```bash
python3 -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 --port 8000 \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --max-model-len 256 --max-num-seq 16 --max-seq_len-to-capture 128 \
  --device qaic --block-size 32 \
  --quantization mxfp6 --kv-cache-dtype mxint8
# ulimit -n 1048576 ; export OMP_NUM_THREADS=8
# long contexts (>=32K): --enable-chunked-prefill False
```

**Optimization techniques on AIC100** (Qualcomm's SpD/microscaling blog, Llama-2-7B and CodeGen-1-7B on AI 100 Ultra, batch 1, speculation length K=7): MXFP6 weight compression alone ≈ **2x**; speculative decoding alone **1.5–2x**; combined **≈4x** decode speedup. Draft models were 350 M (CodeGen) and 115 M (Llama-2) in FP16 against MXFP6 7B targets.

**What to expect end-to-end for our escalation call:** these are *local-server* numbers. Over the public internet to a shared free playground with a 70B model, budget **1.5–4 s** for a few-hundred-token response, occasionally much worse under rate limiting. The `python-imagine-sdk` itself sets `TIMEOUT = 30` s (client default 120 s, 3 retries on 500/502/503/504) — a hint about expected tail latency. **This is 5–20x our local hot-path budget and is precisely why the cloud must not be on the fall-detection critical path.** Measure it yourself on Day 1 and put the comparison in the deck — that table *is* evidence for the latency criterion:

| Stage | Where | Target |
|---|---|---|
| UNO Q pose inference → semantic event | Dragonwing edge | tens of ms |
| Event → local SLM decision | X Elite Hexagon NPU | < 500 ms |
| Local decision → TTS first audio | X Elite NPU | < 1 s |
| **Detection → spoken reassurance (hot path, fully local)** | | **< 3 s** |
| Optional second opinion | **AIC100 Ultra** | 1.5–4 s, off the hot path |
| Nightly summary (batch, 3 a.m.) | **AIC100 Ultra** | seconds; irrelevant |

---

## 7. Evaluating the five candidate cloud roles

### 7.1 (a) Opt-in escalation tier with privacy-preserving redaction — **ADOPT as P1**

**Verdict: adopt, but invert the framing.** The obvious version ("if it's hard, ask a big cloud model") reads as an admission that the local model isn't good enough, and it hands a skeptical judge the question *"so your privacy-first system does send my data to the cloud?"*

Make the **redaction itself the feature**:

- A hard schema boundary: the only thing that can cross it is a `RedactedIncident` dataclass — enum'd event types, confidence floats, room label, coarse durations, pseudonymous `resident_id`. No frames, no audio, no names, no wall-clock timestamps beyond time-of-day buckets. Enforce with a Pydantic model + a unit test asserting no free-text field can escape.
- **Render the exact outbound JSON in the UI** next to a byte count, and next to it "what a camera-cloud product would have sent: 12.4 MB of video." That single screen is worth more than the LLM answer.
- Triggered only when local confidence ∈ ambiguous band, **default OFF**, one toggle, and the demo shows it working with the toggle off and with the router unplugged.
- Stateless calls only (§5.2). Tool calling is available if you want the cloud to *propose* an action that the local hub still adjudicates — a nice "cloud advises, edge decides" invariant.

Cost: ~half a day. Risk: low, because the fallback is "do what we'd have done anyway."

### 7.2 (b) Nightly fleet learning / distillation / prompt-tuning — **PARTIAL: use it for prompt/policy tuning, not weights**

The platform genuinely supports LoRA SFT + compile + serve (§2 Path D), which is more than most hackathon teams will discover. But **the trained artifact appears to stay on the platform** — no export path found — so it cannot improve the X Elite's on-device SLM. And "fleet learning" with one household and four days is not a demonstrable claim; asserting it invites the question "from whose data?"

What *is* achievable and honest:
- **Automated prompt/policy optimization.** Use the 70B to rewrite the local SLM's system prompt and few-shot policy examples, scored against the P0 eval suite. Commit `prompts/v1..vN` with the eval scores per version. This is real, measurable, offline, synthetic-data-only optimization — and it directly serves the "optimization" word in the rubric.
- If someone has spare cycles: run one LoRA SFT job on a small model over synthetic `event-trace → action-plan` pairs, serve it, and show it beats the base model on the eval suite. Frame as *"roadmap, prototyped on AIC100"* — not as something running in the home.

### 7.3 (c) Personalized care summaries / family reports — **ADOPT as P2 if time allows**

Legitimate and pleasant UX, and the *timing* is the technical argument: a batch job at 3 a.m. over aggregated counts, so the hub's NPU never spends energy on prose generation. Send only aggregates (counts per category per day, trend deltas), never event narratives. Honest caveat to pre-empt: a local SLM could also write this; the cloud justification is quality + keeping the hub idle. Say that explicitly rather than overselling.

### 7.4 (d) Voice-clone / TTS model preparation at setup — **REJECT**

Three independent confirmations that this is a dead end this week:
1. The Imagine API has **no `audio/speech` / TTS endpoint** — only `POST /v2/transcribe` (ASR).
2. `quic/cloud-ai-sdk` `models/speech` contains **only `whisper`**.
3. QEfficient's audio support is **`wav2vec2-base-960h` (ASR)**; its generative media models are FLUX (image) and WAN (video), not speech synthesis.

Doing voice cloning on AIC100 means compiling an XTTS/OpenVoice/F5-class model through `qaic-compile` yourself, on Path C, on an x86 host, with the eager-mode fine-tune stack's Python-3.10/Torch-2.9.1 constraints. That is a multi-week project. Keep voice cloning on the X Elite (the team's `research/tech/_cache` already tracks `melotts_en` and `pipertts_en`) with a third-party API as the documented fallback.

### 7.5 (e) Digital-twin simulation / synthetic scenario generation / agent red-teaming — **ADOPT as P0**

This is the best-fit role and, I'd argue, the most non-obvious use of a cloud accelerator any team at this event will present.

Why it scores:
- **Privacy story is airtight by construction.** Not "we redact" — the cloud literally never receives home-derived data. It generates fiction.
- **Zero demo-day risk.** It runs before the demo. No network dependency on stage, no rate limits, no tail latency.
- **It produces exactly the artifacts the rubric asks for.** *Tests* are explicitly listed as recommended; a scored eval harness with a results table is a Technical-Implementation and Documentation win simultaneously.
- **It uses the big model for what only a big model is good at**: creative adversarial coverage and grading. That is the honest division of labor between a 70B on 870 TOPS and a 1–4B SLM on a Hexagon NPU.
- **It makes the "reusable architecture" pitch provable.** Swap the sensing skill → regenerate the scenario suite → the same eval harness scores the new scenario. That is the seed idea's core claim, made measurable.

What to build (concrete):
1. `tools/twin_generate.py` — for each scenario family (fall / near-fall / false-positive-like-a-dropped-pan / kid conflict vs. rough play / TV-time / loud sound with no person / multi-room ambiguity), ask the 70B for N event traces in our exact `SemanticEvent` JSON schema, including the *correct* expected action label and a rationale. Save to `tests/fixtures/twin/*.jsonl`. Commit them.
2. `tools/twin_grade.py` — replay fixtures through the hub's event bus (event-injection mode, which STRATEGY.md already wants as a demo backup), capture the local agent's action plan, and have the 70B grade agreement + safety (did it escalate when it should? did it wake the caregiver at 3 a.m. for a dropped pan?). Emit `docs/eval-report.md` with a confusion matrix, false-alarm rate, and mean decision latency.
3. `pytest tests/test_twin_replay.py` — asserts no regression on the labeled subset. Runs offline from committed fixtures, so CI and judges don't need a key.
4. Demo hook: a **"Simulate"** button in the hub app that injects a twin scenario live. Solves the "is AIC100 really used?" objection *and* de-risks the live fall (STRATEGY.md risk row #5) with the same code.

Adversarial framing to say out loud: *"We red-teamed our own home agent with a 70B on AI 100 Ultra. Here's the false-alarm rate before and after."* Nobody else will say that.

### 7.6 Bonus role nobody will think of: **cloud as the energy/latency baseline**

Run the *same* prompts and the *same* eval suite through (i) the local SLM on the X Elite NPU and (ii) Llama-3.1-70B on AIC100, and publish tokens/s, TTFT, joules-per-decision, and accuracy side by side. That table simultaneously (1) proves the local path is fast enough, (2) quantifies the accuracy you traded away, and (3) justifies the architecture instead of merely asserting it. It costs one script and is the single highest-density artifact for the 40-point criterion.

---

## 8. Roles to avoid — and why

| Anti-pattern | Why it hurts |
|---|---|
| Cloud LLM as the primary reasoner | Directly contradicts the privacy pitch; adds 1.5–4 s to the hot path; dies when the router is unplugged (our best demo moment). |
| Streaming frames/clips to a cloud VLM "just for hard cases" | Our differentiator is *semantic events, not video*. One frame leaving the house destroys the thesis, and §5.2 says it may be retained. |
| Cloud Whisper (`/v2/transcribe`) for the two-way conversation | Sends the resident's voice off-premises. Keep STT local (the team's cache already has whisper-tiny/base/small and zipformer). Cloud whisper-tiny is fine for grading *synthetic* audio only. |
| Cloud TTS in the parent's cloned voice | Doesn't exist on this platform (§7.4), and shipping a voice clone to a third party is exactly the consent problem we claim to solve. |
| "We fine-tuned on AIC100 and deployed to the edge" | Unsupported by the platform (no weight export). Do not claim it. |

---

## 9. 4-day implementation plan for the AIC100 slice

**Day 1 (Aug 3) — unblock and measure. ~2 h.**
- Escalate the endpoint/key question to organizers now. In parallel, self-register at https://aisuite.cirrascale.com/ and generate a key at `/account/api-keys`.
- `GET /v2/models` → paste the real model list into this file. Check `/models/overview` for the actual per-minute/hour/day quotas and `/models/pricing`.
- Run a 20-call latency probe (TTFT, total, tok/s) for the largest available model and record it. This number decides the P1 confidence band.
- Decide: `openai` client only, no Qualcomm SDK (§5.1). Add `IMAGINE_API_ENDPOINT` / `IMAGINE_API_KEY` to `.env.example`.

**Day 2 — P0 generator. ~4 h.** `tools/twin_generate.py` + committed `tests/fixtures/twin/*.jsonl`. Requires the `SemanticEvent` schema to be frozen first, so this forces a useful architectural decision early.

**Day 3 — P0 grader + P1 escalation. ~6 h.** `tools/twin_grade.py` → `docs/eval-report.md`; `pytest` regression test; the `RedactedIncident` boundary + its unit test; the redaction-diff UI panel; the "Simulate" button.

**Day 4 — P2 + polish. ~3 h.** Nightly summary job (or cut it); the local-vs-cloud comparison table (§7.6); README threat-model section; final eval numbers into the deck.

**Non-negotiable engineering rules:**
- **Cache every cloud response to disk as a fixture** (`_cache/aic100/<hash>.json`) and make the code read the cache first. The demo must run with the network unplugged. This also protects against burning the daily quota at 11 a.m. on Aug 7.
- Wrap all cloud calls in a 5 s timeout + single retry + hard local fallback. Never `await` a cloud call inside a detection handler.
- Log every cloud call to an auditable `cloud_calls.jsonl` (timestamp, endpoint, model, payload hash, byte count, latency). Show it in the UI. Auditability *is* the privacy feature, and it doubles as your latency evidence.
- Stateless calls only; never use `POST /v2/chat/completions/{id}`.

---

## 10. Open items to close on Day 1

1. Which endpoint are we entitled to (internal Imagine vs. Cirrascale playground)? → organizers.
2. Real `GET /v2/models` output — is there a ≥70B model, and is there a VLM? Is there anything newer than Llama-3.1?
3. Actual free-tier quotas and whether credits are pre-loaded for the event.
4. Does the chat endpoint accept OpenAI-standard `tools[].function.parameters`, or only `arguments`? (30-min experiment.)
5. Does image input work with standard OpenAI `image_url` content parts, or only the tagged `{"Image": …}` form?
6. **[unverified]** Whether fine-tuning artifacts can be exported off the platform. If yes — ask support — the "cloud trains a LoRA, edge runs it" story becomes available and would be a significant upgrade to P0/7.2.

---

## Sources

- Qualcomm AI Inference Suite (product/onboarding, playground list, docs links): https://www.qualcomm.com/developer/software/qualcomm-ai-inference-suite
- Cirrascale Inference Cloud playground (AI 100 Ultra, free tier, API keys, BYOM, fine-tuning): https://aisuite.cirrascale.com/
- **Live Imagine OpenAPI 3.1.0 spec** (endpoints, auth, schemas, model IDs, tool-calling examples): https://aisuite.cirrascale.com/imagine-api-docs
- Imagine SDK documentation (endpoint format `https://…/api/v2`, `IMAGINE_API_KEY`, LiteLLM/LangChain/CrewAI/AutoGen tutorials, proprietary EULA): https://aisuite.cirrascale.com/sdk/index.html · https://aisuite.cirrascale.com/sdk/tutorials/litellm.html · https://aisuite.cirrascale.com/sdk/install.html
- `python-imagine-sdk` 0.5.0 on PyPI (released 2025-07-18; `LicenseRef-Proprietary`; default model IDs; Bearer auth; TIMEOUT=30): https://pypi.org/project/python-imagine-sdk/
- Cirrascale Inference Cloud product page ("no storage of model inputs or outputs", token-based pricing): https://www.cirrascale.com/inference-cloud-qualcomm
- Cloud AI 100 product specs (Ultra 870 TOPS / 128 GB / 548 GB/s / 150 W; Pro; Standard; AI 80): https://www.qualcomm.com/products/technology/processors/cloud-artificial-intelligence/cloud-ai-100
- Qualcomm Cloud AI SDK docs (v1.21; qaic tools, Triton/vLLM/ONNX-RT, Kubernetes, aic-manager): https://quic.github.io/cloud-ai-sdk-pages/latest/
- Cloud instances (AWS DL2q, Cirrascale 1–8 accelerators, "SDKs are pre-installed on cloud instances"): https://quic.github.io/cloud-ai-sdk-pages/latest/Getting-Started/Installation/index.html
- vLLM-on-qaic OpenAI-compatible server launch (`--device qaic --quantization mxfp6 --kv-cache-dtype mxint8`): https://quic.github.io/cloud-ai-sdk-pages/latest/Getting-Started/Model-Serving/vLLM-Serving/run.html
- vLLM benchmarking numbers (TTFT 111 ms, TPOT 14.2 ms, 334 tok/s output, TinyLlama-1.1B): https://quic.github.io/cloud-ai-sdk-pages/latest/Getting-Started/Model-Serving/vLLM-Serving/benchmarking.html
- Speculative decoding + microscaling blog (MX6 ≈2x, SpD 1.5–2x, combined ≈4x; Llama-2-7B / CodeGen-1-7B on AI 100 Ultra): https://quic.github.io/cloud-ai-sdk-pages/latest/blogs/Speculative_Decode/spec_decode_ai100/index.html
- PyTorch eager-mode fine-tune constraints (x86 only, Python 3.10, Torch 2.9.1): https://quic.github.io/cloud-ai-sdk-pages/latest/Getting-Started/PyTorch-Workflow/Eager-Mode-Finetune/index.html
- `quic/efficient-transformers` README (latest news through 07/2026; Qwen3.6, Gemma4, GLM-4.5, Qwen3-VL, gpt-oss-20b, wav2vec2, FLUX, WAN 2.2; AI100/AI200): https://github.com/quic/efficient-transformers · https://raw.githubusercontent.com/quic/efficient-transformers/main/README.md
- `quic/cloud-ai-sdk` model recipes (`models/speech` = whisper only; text_to_image list): https://github.com/quic/cloud-ai-sdk/tree/main/models
- Qualcomm AI200 / AI250 announcement, 2025-10-28 (768 GB LPDDR/card, 160 kW rack, 2026/2027 availability): https://www.qualcomm.com/news/releases/2025/10/qualcomm-unveils-ai200-and-ai250-redefining-rack-scale-data-cent
- Cloud AI support forum: https://mysupport.qualcomm.com/supportforums/s/topic/0TOdK0000004BmTWAU/cloud-ai
