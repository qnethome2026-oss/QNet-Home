# The fall-response workflow, explained

*The narrative companion to [`DESIGN.md`](DESIGN.md) (the spec) — use case,
what runs where and why each piece was chosen, the protocol, the agent
architecture, the first-responder brief, latency numbers, and the challenges
that shaped it. Every number here is measured (`[M]`, methodology in
[`../measurements.md`](../measurements.md)) — nothing is estimated.*

## The use case

Someone living alone falls and can't reach a phone. The house notices,
**speaks to them within seconds**, and walks an escalation ladder: spoken
check-in → trusted contact over Telegram → (simulated) emergency call — with
a first-aid layer for what they say while help is coming, and a briefing for
whoever walks in. Everything runs on-device: in-home cameras only get
adopted if footage physically cannot leave the house, and that one privacy
constraint forces every model below onto local NPUs. Wearables were rejected
up front — the population that falls most is the population that won't wear
the pendant.

## The models, and why each one

| Stage | Model (full name) | Why this one |
|---|---|---|
| Fall detection | **YOLO11n** fine-tune ([`melihuzunoglu/human-fall-detection`](https://huggingface.co/melihuzunoglu/human-fall-detection)), 2.58 M params, 640×640 input, FP32 QNN context binary, Hexagon HTP v75 on each camera board | Keeps **three classes** (fallen / sitting / standing) where higher-scoring models collapse to binary fall/no-fall — and binary is useless here: sitting-on-the-floor *is* the false alarm that teaches a family to ignore the alert. Small enough for 34.8 ms/inference on the NPU, which is what makes a temporal rule affordable: single frames flicker, so the event fires only on fallen in **6-of-6 frames at ≥0.8 confidence** — calibrated live (real falls 0.85–0.94, every observed noise source ≤0.52). |
| Reasoning / dialogue | **Gemma 3n E2B** (effective-2B, Q4_0) under **GenieX** on the IQ-9075 hub, OpenAI-compatible endpoint `:18181`, ~32 k context (we use a few hundred tokens — latency, not capacity, is the budget) | Classifies in ~450 ms warm — the difference between conversation and awkward silence for someone on the floor. Its weakness shaped the architecture: measured ignoring prose instructions on three separate occasions, so it only picks from **closed option sets** or rewords engine-chosen facts. All safety and medical content lives on deterministic rails — a 2B model must never stand between a bleeding person and "press firmly on the wound." |
| "Where's my stuff" | **Qwen3-VL-4B-Instruct** (w4a16, Qualcomm GenAI container, one per room board, ~4.1 GB) | Runs **per room** so images never cross even the LAN — the privacy rule one level deeper — and rooms answer in parallel (4–7 s each). 4-bit weights let it co-reside with the detector + voice stack in the board's 14 GiB. |
| Ears | **Whisper-small** (quantized), on-board NPU per voice room | On-device audio, same reason as video. It garbles under real acoustics — so "unclear" is a first-class classification that earns "could you say that again?" instead of the model improvising a reply to nonsense. |

## The protocol

**MQTT** (Mosquitto on the hub, `11883` + `19001`/websocket for the
dashboard). Pub/sub decouples N rooms from one hub: boards drop off Wi-Fi
and reappear on new DHCP addresses constantly, and with topics nobody needs
anyone's IP. One level deeper: fall events ride **QoS 1** (broker-level
retry — "the fall message got lost" is not an acceptable failure mode),
heartbeats ride QoS 0 with retained last-wills giving liveness for free, and
the whole wire is a **frozen contract with fixture files**
([`../contracts/mqtt.md`](../contracts/mqtt.md)) — in a three-person
hackathon the wire is the only interface that must never drift, so it is the
one thing under contract test.

## The "agent" — no framework, deliberately

The agent is **our own ~1,800-line Python program**
([`../qnet/agent/engine.py`](../qnet/agent/engine.py) +
[`phases.py`](../qnet/agent/phases.py)): plain `asyncio` + `paho-mqtt`, with
Gemma behind a plain `openai` client. Three separable pieces:

1. **Serving** — GenieX exposes the model as a standard HTTP endpoint; the
   engine could swap models by changing a URL.
2. **The engine** — a **phase state machine driven by markdown skill files**
   ([`../skills/fall.md`](../skills/fall.md), [`find.md`](../skills/find.md),
   [`first-aid.md`](../skills/first-aid.md)). A skill declares phases
   (scripted opening, goal, allowed tools, named exits, timers); the engine
   speaks openings instantly (canned — zero model latency), runs tools
   itself (`notify_contacts`, `call_emergency`, `look_in_rooms`), and
   consults Gemma only at closed decision points ("pick one: ok / escalate /
   unclear") or to reword facts the engine chose. Every turn lands in a
   session journal, so any spoken sentence traces to a tool result or a
   skill line.
3. **Why not LangChain / an agent framework** — frameworks put the model in
   the driver's seat: it plans, picks tools, composes replies. That is
   backwards for this hardware and domain. A 2B quantized model can't do
   reliable free-form tool-calling, and "the LLM decided not to escalate" is
   an unacceptable failure mode. So the inversion: **rails decide, the model
   decorates** — timers, escalation, calls, and medical sentences are
   deterministic; Gemma contributes word choice and one-of-N choices, both
   validated, with canned fallbacks so `--no-llm` runs the entire flow.
   Free side effects: no dependency stack on a constrained board, auditable
   latency, and behavior changes are markdown edits a non-programmer can
   review.

## The first-responder brief

A neighbor or paramedic walks in mid-incident and says the phrase — **"I am
the first responder"** — and the room answers with a spoken timeline: when
the fall was detected, what the person said, what was done and when, elapsed
time. The pieces:

- [`../skills/responder-brief.md`](../skills/responder-brief.md) — the
  content: goal text for the one LLM wording call. It is an engine-level
  **interrupt, not a session**: pause the comfort loop → read the room's
  fall session file → one `word_line("brief")` call → speak → resume.
- The trigger phrase lives in each voice node's config
  ([`../config/voice-nodes/`](../config/voice-nodes/), `responder_phrase`) and
  is matched **node-side** in
  [`voice_controller.py`](../apps/ventuno-q/qnet-voice-node/python/voice_controller.py)
  — a plain string check, because no regex may decide a responder has
  arrived by accident.
- Every fact it reports is already on disk as the session runs — it is a
  formatter over existing data, readable live mid-escalation, with no
  "finalize the log" step. No fall file → it says so plainly and stops.

## Latency, end to end `[M]`

**Fall → first spoken word: ≈ 3–4 s.** Breakdown:

| Leg | Time | Notes |
|---|---|---|
| Camera frames → temporal rule satisfied | ~2.1 s | 6-of-6 window at the node's ~3 fps processing rate |
| Per frame inside that: preprocess / NPU / decode | 9.4 ms / ~100 ms / 0.5 ms | NPU call is `qnn-net-run` spawn + IO + 34.8 ms pure inference; batching amortises to 57 ms |
| Event → agent dispatch (MQTT, QoS 1) | milliseconds | LAN broker |
| Agent → spoken opening | instant decision | opening is canned (skill file), no model in the path; TTS renders at ~9 chars/s |

**Conversation loop (they speak → house answers): median 1.61 s, max 1.64 s**
— down from 2.37 s / 5.58 s before the benchmark round found a
session-snapshot cancellation storm (6 of 7 listens were being killed) and a
5.5 s cold-start classify (fixed with a warm-up ping; first reply now
0.48 s). Warm Gemma classify: ~450 ms.

**"Where's my keys" ask → spoken answer: ≈ 5–8 s** — both rooms' VLMs
queried in parallel (4–7 s each, first query after a container start ~30 s —
warm them before demos), plus wording and TTS.

**Escalation legs:** Telegram notify ~1 s (HTTP); contact acknowledgment
handled whenever it arrives; unanswered check-in escalates on a 30 s timer.

## Two challenges that shaped it

1. **The chip isn't in Qualcomm AI Hub's catalog** (QCS8300). Direct compile:
   no target. The conversion server's local converter: broken. What worked:
   compile for **"QCS8550 (Proxy)"** — context binaries bind to the Hexagon
   *architecture generation* (HTP v75), not the SKU, so a same-generation
   proxy loads and runs. Proven by pushing to real hardware, not the spec
   sheet. ([`../models/fall-detection/README.md`](../models/fall-detection/README.md))
2. **Spoken replies were dropped mid-response.** Instrumented first, fixed
   second. The cause was nothing acoustic: the engine republishes its
   session snapshot on every log line, and the voice node cancelled its
   active listen on every arrival. Fix: cancel only on a mode flip, plus the
   warm-up ping. The lesson that generalized: every failure got cheaper the
   moment we measured before touching.
   ([`../verify/T-voice-bench.txt`](../verify/T-voice-bench.txt))
