# Agentic AI / LLM Hackathon Research — Winning Patterns for QNet Home

Research date: 2026-08-03. Compiled for the Snapdragon Multiverse Hackathon (Aug 3-7, 2026) submission, team building **QNet Home**.

Scope: 2+ years of agentic-AI/LLM hackathons (Aug 2024 – Aug 2026), with special attention to multi-agent orchestration, tool-calling, physical-device/home control, local/offline agents, MCP, and — critically — **the Snapdragon Multiverse Hackathon series itself**, which turns out to have already run at several other campuses this year with the *exact same hardware kit* we have.

---

## 1. Snapdragon Multiverse Hackathon series (Qualcomm, our own hackathon brand) — MOST relevant precedent

This is not a different hackathon — it is **the same program**, run at multiple campuses (Princeton Sept 2025, MIT Jan 2026, Bangalore/Noida July 2026, and ours now). This is the single most decision-relevant data we found.

**Format facts (consistent across editions):**
- No predefined tracks in the general edition (Bangalore/our edition) — earlier campus editions (Princeton) did have 3 illustrative tracks: Real-time CV Assistant, Conversational AI Companion, RL Agent Arena — but these are just *examples*, not mandatory.
- Hardware kit is identical to ours: Copilot+ PC (Snapdragon X Series) as central hub, mobile device, Arduino UNO Q, Qualcomm AI Cloud 100, optionally BYO Snapdragon devices.
- Submission requirement: GitHub repo, README, open-source license, and a **Windows .EXE or .MSIX**, "majority should run locally" (hybrid edge/cloud okay) — matches our judging rubric's Deployment & Accessibility criterion exactly.
- Judging categories seen at Bangalore: **Overall Winner** (technical excellence, innovation, seamless execution), **Multi-Device Innovation** (explicitly: "projects using two+ devices with distributed functionality creating end-to-end workflows impossible on single devices"), and a **Popularization Award** (participant-voted, rewards best demo/presentation).

**Winner: "Dragverse" — Snapdragon Multiverse Hackathon, Noida edition (~July 2026)**
Team "Ghost Map," led by Deepesh Kakkar (Thapar University). [Tribune India](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- What it did: phone captures a 3D scan of a real room → builds a digital twin → trains a robot-control policy via **reinforcement learning inside the simulated twin** → deploys the trained policy onto a **physical robot**.
- Why it won: explicitly praised for "multi-device architecture strength" spanning phone → PC/cloud simulation → physical robot — a workflow literally impossible on one device. It used the full device chain (mobile capture, PC/cloud compute, physical actuator) rather than treating "multi-device" as an afterthought.
- Takeaway for us: judges in *this exact hackathon franchise* reward pipelines where each device does something the others structurally cannot, chained into one coherent workflow, and story the "impossible on a single device" framing directly in the pitch.

**Idea for QNet Home:** Explicitly narrate, in the demo, "this event could only be detected here, decided here, and acted on there" — i.e. make the cross-device necessity visible and undeniable, not just implied.

---

## 2. Qualcomm "Windows on Snapdragon AI Hackathon" (Devpost, wos-ai.devpost.com)

[Winners announcement](https://wos-ai.devpost.com/updates/34096-and-the-winners-are)

- **1st: AudioNova** ([Devpost](https://devpost.com/software/audionova)) — local-first TTS + voice cloning + voice-changing app. Whisper (quantized/pruned via Qualcomm AI Hub) for ASR, Vall-E-X for voice cloning/TTS, FastAPI backend, React/Windows front end. Measured and reported: **2x transcription speedup** and **35% power reduction** on Snapdragon X via Qualcomm AI Hub optimization (quantization, DSP/GPU offload, custom matmul kernels). One-click installer.
- **2nd: Multilingual Translator** — real-time on-device EN/JA/KO/ZH translation, no internet dependency.
- **3rd: Civil Dialog** — moderated discourse tool.
- Judged on: technological implementation, design, potential impact, idea quality, and **best use of Qualcomm AI Hub models** — i.e., citing concrete AI Hub optimization + a measured number is a proven winning move on Snapdragon hardware specifically.

**Idea for QNet Home:** We should reproduce AudioNova's playbook precisely — quantize our on-device TTS/ASR/VLM via Qualcomm AI Hub and **report a measured before/after number** (latency ms, tokens/sec, watts) in the pitch deck. This is a direct, provable win pattern on this exact judging panel's home turf.

## 3. Qualcomm x Meta ExecuTorch Hackathon (June 2026, SF)

- Challenge: ship a responsive on-device AI app using ExecuTorch on Snapdragon (mobile), showcasing latency/privacy/offline/energy benefits.
- **EchoWalk** (accessibility navigation aid): runs **4 AI models entirely on the Snapdragon NPU** — a "semantic safety radar" for obstacle warning via spatial audio, plus a tap-to-describe VLM path that narrates the room. Multiple models chained, all local, framed around accessibility/independence for blind/low-vision users.
- Takeaway: stacking several small on-device models into one coherent sensing→reasoning→spoken-output loop, and giving it an accessibility/dignity framing (not just "cool demo"), reads well to Qualcomm-adjacent judges.

## 4. Qualcomm Edge AI Developer Hackathon — Korea (Feb 2026)

[Qualcomm blog](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea)

Five featured projects, all fully on-NPU, all privacy-first:
- **E.M.Pilot** — on-device private email agent (YOLOv8, Qwen2-7B-Instruct, EasyOCR, Nomic-Embed) doing classification/summarization/replies locally.
- **File Fairy** — semantic local file search/organizer, no cloud, ONNX embeddings.
- **emerGen** — offline emergency-response assistant: vector-DB-grounded guidance + Whisper-Base-En for audio input, Llama-3.2-3B fine-tuned, works with zero connectivity.
- **Medly** — real-time medical-jargon simplifier for patients: STT + biomedical NER + Qwen2.5-7B, entirely on Hexagon NPU, "all AI computations processed directly on the device's NPU."
- **MyStoryPal** — kids' English-learning storybook co-creation: Llama-3.2-3B + Stable Diffusion 2.1 + CLIP, all on-device.
- Common thread across ALL winners: explicit "100% on-NPU / no cloud dependency" claims as the headline differentiator, and a named list of specific quantized open models running locally (never just "an LLM").

**Idea for QNet Home:** Name our exact on-device model stack (SLM/VLM name + quantization + which NPU/DSP block it runs on) in the pitch — vague "local AI" claims underperform vs. teams that show the model bill of materials.

## 5. Microsoft AI Agents Hackathon 2025 (18,000 registrants, 570 submissions)

[Winners page](https://microsoft.github.io/AI_Agents_Hackathon/winners/)

- Best Overall: **RiskWise** (supply-chain risk agent, Semantic Kernel + Azure AI Agent Service).
- Best C#: **Apollo** — deep-research assistant with named specialized sub-agents (Athena=research, Hermes=analysis) — a clean **planner + named specialist sub-agents** pattern that's easy for judges to grok in 3 minutes.
- **ModelProof "Sentinel"** — safety-focused chatbot running **two LLMs in parallel to cross-verify each other's outputs** for hallucination/bias/toxicity auditing — a lightweight guardrail pattern using a second model as a checker rather than hand-written rules.
- Explicitly noted: **no IoT/home-automation/physical-device entries won** in this cohort — pure software/RAG/copilot agents dominated. This is the "generic agent" crowd we want to avoid resembling.

**Idea for QNet Home:** Borrow the "named specialist sub-agents" narrative clarity (e.g., "Sentry" = event triage, "Voice" = conversation/TTS, "Guardian" = escalation policy) rather than one monolithic agent — judges reward legible role decomposition in a 3-minute demo.

## 6. Global Agent Hackathon, May 2025 (Agno framework, 60+ submissions)

[Winners](https://www.agno.com/blog/global-agent-hackathon-winners)

- Grand prize: **Likeminds** (agentic semantic social network) and **Superwizard AI** (NL→browser-automation Chrome extension).
- Notable: **Windows-Use** — an agent that controls Windows apps/workflows directly (OS-level tool-calling), a precedent for "agent drives your Copilot+ PC" as a legitimate, judge-approved category.
- Pattern noted: heavy emphasis on browser/workflow automation and content curation; **zero physical-device or IoT winners** — again confirms most agent hackathons stay purely digital, so a genuinely physical multi-device story stands out by contrast.

## 7. Meta LlamaCon Hackathon (2025/2026) and Llama Impact Hackathon India

- LlamaCon 3rd place: **Llama CCTV Operator** — zero-fine-tune surveillance event detection from video using Llama 4 multimodal, flags "custom video events in simple language," sampling every 5 frames. **This is essentially our vision-pipeline concept, minus the privacy angle** (it streams/analyzes raw video, not semantic-only events) — validates the demand for this capability while showing the differentiation opportunity: they process frames with a cloud/edge VLM directly; we deliberately never send video off the sensing node, only semantic events. That privacy contrast is a strong, explicit pitch line.
- LlamaCon "Best Llama API Usage": **Geo-ML**, praised for exploiting a **1M-token context window** and multimodal text+image — a reminder that "we used a genuinely large context / multimodal capability, not just a chat wrapper" is a specific technical-merit hook judges cite.
- Llama Impact Hackathon India, "AI on Edge" theme: **Circuit Bot / Auto Bot** — edge speech-recognition + Llama interpreting voice commands to control BLE appliances **fully offline**, prized specifically for "localized, low-latency control" with no internet dependency. Near-identical thesis to QNet Home's Arduino edge nodes — validates the edge-voice-control pattern as a proven crowd-pleaser, but it's single-device; we go further with cross-device semantic events + multi-turn conversation + escalation tooling.
- Other India-hackathon winners (CurePharma AI, CivicFix) leaned on **WhatsApp as the always-available UI layer** for accessibility in constrained contexts — a reminder that judges reward "meets the user where they already are" delivery even when the AI core is sophisticated.

## 8. Forum Ventures x Anthropic Agentic AI Hackathon (Sept 2025, NYC)

[Devpost rules](https://forum-x-anthropic-hackathon.devpost.com/)

Judging axes: **Technical Innovation** (creative combination of tech/novel approaches), **Organization & Conventions** (code clarity/docs), **Use of AI** (depth of integration — explicitly named: APIs, prompt engineering, **MCP servers**, RAG pipelines), **UI/UX** (seamlessness). Winning team (per community write-ups) built **Zenith**, a customer-discovery platform, "entirely with agentic workflows" using Claude Code as the build tool itself, not just the shipped product — a meta-pattern (using an agent to build the agent) that impressed judges on velocity.

**Idea for QNet Home:** If our team uses an agent (Claude Code/OpenClaw) to co-build the demo itself under time pressure, that's worth a one-line mention — "we dogfooded our own agentic tooling to hit a 4-day build," reinforcing the "agentic multi-device orchestration" thesis at the meta level too.

## 9. Google Gemini API Developer Competition (2024, results carried into subsequent Gemini hackathons)

[ai.google.dev/competition](https://ai.google.dev/competition)

- **Vite Vere** (Most Impactful & People's Choice) — assists people with cognitive disabilities toward independence via personalized everyday guidance.
- **Gaze Link** (Best Android) — eye-tracking communication for ALS patients.
- **ViddyScribe** — instant audio descriptions for video accessibility.
- Strong, repeated pattern: **accessibility/independence-for-vulnerable-users framing wins both technical and "impact" categories simultaneously** — directly validates our elder-care and kid-safety framing as a genre that consistently places well, provided the tech is real (not just a UI wrapper).

## 10. Kong Agentic AI Hackathon 2025

[Winners](https://konghq.com/blog/news/winners-of-kong-agentic-ai-hackathon)

- 2nd place **AgenticAI-MCP-Client**: centralizes MCP connections inside an API gateway, converting NL → structured queries, explicitly praised for "reducing operational overhead and **attack surface**" — one of the few explicit security/guardrail mentions found across all hackathons surveyed.
- 3rd place **Kong Auto Rollback AI Agent**: autonomous monitor + auto-rollback of misconfigurations — an "agent with a kill-switch/undo" pattern.
- Note: across nearly every hackathon surveyed, **explicit safety/guardrail engineering was rarely highlighted as a standalone winning factor** — it's assumed table-stakes, not a differentiator by itself. What *did* win: agents with a visible, demoable **undo/rollback or escalation action**, which we should copy (our "emergency escalation" and "caregiver notification" tool calls are exactly this pattern — make the escalation/de-escalation *visibly reversible/gated* in the demo).

## 11. Mistral Worldwide Hackathon (London edition, 2025/2026)

Winning team built **"Mistralverse"**: a self-governing "agent civilization" where autonomous agents held land, money, and opinions, and democratically elected their own mayor. Pure novelty/spectacle play — judges rewarded audacity and a clean live-demo narrative over practical utility. Useful *counter-example*: it shows judges will reward a wild, legible demo concept even with limited "real-world usefulness" — reinforces that presentation/demo craft (our Presentation & Docs 15 pts, and the "Popularization" vote in the Qualcomm rubric) matters as much as raw utility.

## 12. Cerebral Valley x Anthropic "Claude Opus Build Day" hackathons (recurring 2025-2026)

300+ participants, 6 finalists, 3 winners format, in-person judging by Anthropic staff (Boris Cherny, Cat Wu). Winners like **Tekton** (a 3D reconstruction of Tang Dynasty architecture) show these events reward a **tight, visually stunning, single novel artifact** demoed live rather than a broad feature set — reinforces "cut scope, polish one wow-moment" advice for our 4-day build.

---

## Overdone / saturated ideas to avoid resembling

- **Generic RAG/chatbot/copilot agents** (customer support bots, doc-QA, "chat with your data") dominate volume at nearly every general agent hackathon (Microsoft, Agno, Kong) and rarely win top prizes anymore — too much sameness, judges are fatigued by them.
- **Browser/workflow automation agents** ("agent clicks buttons for you") — heavily represented in the Agno Global Agent Hackathon; a crowded lane.
- **Fall detection / elder-monitoring via pose estimation** is a known, frequently-pitched concept in hackathons and vendor demo reels generally (confirmed indirectly: multiple "dementia/aging" agent entries exist, e.g. Microsoft's "Nuroxa" dementia-risk assistant) — the *sensing* part is not novel by itself. Winners in this space differentiate via **delivery mechanism** (WhatsApp-native, voice-first, familiar-voice) or by chaining sensing into a genuinely multi-device *response* loop, not by the detector itself. Our pitch must foreground the **cross-device orchestration + familiar-voice response + privacy-by-construction (semantic events only, no video leaves the node)**, not "we detect falls," since that alone is unremarkable.
- **Single-device "local LLM app" demos** (an offline chatbot with no other device in the loop) are common and, per this hackathon's own Bangalore rubric, explicitly scored lower under "Multi-Device Innovation" — that criterion exists precisely because too many teams submit single-device apps.
- **Voice cloning as a party trick** — separately, we found real news-cycle concern about *malicious* child/family voice cloning (virtual-kidnapping scams, now achievable from 3-6 seconds of audio, e.g. via consumer tools). This means our parent-voice-cloning feature will read to some judges as topically risky unless we proactively show **explicit consent capture, on-device-only storage of the voice model, and a visible provenance/watermark or verification cue** distinguishing our system's speech from a spoof. Silence on this point is a real risk; addressing it head-on is a differentiator (safety-consciousness is judged 40% of the technical score too).

---

## Top ideas for QNet Home — ranked

1. **Report Qualcomm AI Hub optimization numbers, not just "runs on NPU."** Copy AudioNova's winning move exactly: quantize/prune the on-device SLM/VLM/TTS/ASR via Qualcomm AI Hub and put a concrete before/after number (e.g., "2x faster transcription, 35% less power" is the exact bar AudioNova set winning 1st place) on a slide. This is the single most provable lever for the 40-pt Technical Implementation score on this specific judging panel.
2. **Make the "impossible on one device" workflow explicit and narrated**, exactly like the Dragverse winner (phone scan → cloud/PC RL training → physical robot). For us: "Arduino node detects (edge) → PC/SLM reasons + decides (hub) → speaker/lights/phone act (endpoints) → cloud escalation only if needed" — say this chain out loud in the demo and pitch as literally impossible on any single device in the kit. This maps directly onto Qualcomm's own "Multi-Device Innovation" judging category seen at the Bangalore sibling event.
3. **Name your model stack and roles like specialist sub-agents** (Sentry/Voice/Guardian, or similar), mirroring the Apollo (Athena/Hermes) pattern that won Best C# Agent at Microsoft's hackathon — legible role decomposition reads better in a 3-minute judged demo than one monolithic "AI."
4. **Differentiate explicitly from Llama CCTV Operator / generic fall-detection**: our pitch's strongest unique line is "we never send video anywhere — only semantic events cross the wire," in direct contrast to cloud/edge VLM surveillance projects like LlamaCon's CCTV Operator. State this contrast out loud; don't assume judges infer it.
5. **Address voice-cloning risk proactively, don't let judges ask first.** Given real 2025-2026 news coverage of malicious child/parent voice-clone scams (from as little as 3-6 seconds of audio), explicitly demo: consent capture flow, on-device-only voice model storage, and some verification cue that distinguishes system speech from a real call — turns a potential liability into a technical/safety talking point.
6. **Give the "escalation" tool call a visible undo/gate**, mirroring the pattern in Kong's winning "Auto Rollback" and "MCP-Client attack-surface reduction" projects — e.g., show the caregiver-notify or emergency-escalation action requiring a brief confirmation window / being cancelable by the resident's voice ("I'm fine, cancel") before it fires. Demoable reversibility reads as maturity, not slowness.
7. **Steal the accessibility/independence framing that wins BOTH technical and impact categories simultaneously** (Vite Vere, Gaze Link, ViddyScribe, EchoWalk) — frame elder fall-response as "preserving independence/dignity, not surveillance," which is proven to resonate with judges across Google's and Meta's competitions.
8. **Cut scope hard and polish one wow-moment for the live demo**, per Cerebral Valley Build Day and Mistral's "Mistralverse" pattern — judges in these formats reward one vivid, legible, live-fireable scenario (e.g., a real fall-to-response loop with a real Arduino node, real light flicker, real two-way voice) over a feature checklist.
9. **Note the Popularization/participant-vote award pattern** (seen at the Bangalore sibling event and echoed by Mistral's audacious "agent civilization" win) — invest real effort in the live-demo spectacle itself (parent's cloned voice talking through a smart speaker live on stage is a strong, cinematic beat) since audience-voted prizes reward memorability independent of technical depth.
10. **Consider naming the concrete open model stack (e.g., a specific Llama/Qwen SLM size + quantization + which Snapdragon block it runs on)** rather than saying "local AI" — every Korea-hackathon winner did this and it reads as substantially more credible/technical than vague claims.

---

## Sources

- [Snapdragon Multiverse Hackathon | Princeton](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon | Bangalore](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)
- [Snapdragon Multiverse Hackathon | MIT CSAIL](https://www.csail.mit.edu/event/snapdragon-multiverse-hackathon)
- [Team led by city youth emerges winner at Qualcomm hackathon — The Tribune (Dragverse)](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [Windows on Snapdragon AI Hackathon — winners announcement](https://wos-ai.devpost.com/updates/34096-and-the-winners-are)
- [AudioNova project page — Devpost](https://devpost.com/software/audionova)
- [Qualcomm x Meta ExecuTorch Hackathon recap — lablab.ai](https://lablab.ai/ai-hackathons/qualcomm-x-meta-executorch-hackathon)
- [On-device AI hackathon in Korea: winners and highlights — Qualcomm Developer Blog](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea)
- [AI Agents Hackathon 2025 — Winners page (Microsoft)](https://microsoft.github.io/AI_Agents_Hackathon/winners/)
- [AI Agents Hackathon 2025 – Category Winners Showcase — Microsoft Community Hub](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/ai-agents-hackathon-2025-%E2%80%93-category-winners-showcase/4415088)
- [Global agent hackathon winners — Agno blog](https://www.agno.com/blog/global-agent-hackathon-winners)
- [Meet the winners of our first-ever LlamaCon Hackathon — Meta AI blog](https://ai.meta.com/blog/llamacon-hackathon/)
- [Highlights from the first-ever Llama hackathon in India — Meta AI blog](https://ai.meta.com/blog/llama-hackathon-india/)
- [Forum Ventures x Anthropic Agentic AI Hackathon — Devpost rules](https://forum-x-anthropic-hackathon.devpost.com/)
- [The Claude Code setup that won a hackathon — AI @ Sulat.com](https://ai.sulat.com/the-claude-code-setup-that-won-a-hackathon-a75a161cd41c)
- [Meet the winners of our Claude Opus 4.8 Build Day hackathon — Claude/Anthropic blog](https://claude.com/blog/meet-the-winners-of-our-claude-opus-4-8-build-day-hackathon)
- [Gemini API Developer Competition winners — ai.google.dev](https://ai.google.dev/competition)
- [Announcing the Winners of the Gemini API Developer Competition — Google Developers Blog](https://developers.googleblog.com/en/announcing-the-winners-of-the-gemini-api-developer-competition/)
- [Announcing the winners of Kong Agentic AI Hackathon 2025 — Kong blog](https://konghq.com/blog/news/winners-of-kong-agentic-ai-hackathon)
- [Cerebral Valley on X — Opus 4.6 global hackathon stats](https://x.com/cerebral_valley/status/2026066211482857844)
- [Winners of the @MistralAI hackathon — X/etnshow thread (Mistralverse)](https://x.com/etnshow/status/2029200653285818791)
- [AI Voice Cloning of Children: The New Child Safety Crisis — HiWave blog](https://hiwavemakers.com/blog/ai-voice-cloning-child-safety-parents/)
- [Agents & MCP Hackathon — Hugging Face org page](https://huggingface.co/Agents-MCP-Hackathon)
- [MCP - AI Agents Hackathon — Devpost](https://mcp-ai-agents-hackathon.devpost.com/)
- [Qualcomm India Opens Registrations for Snapdragon Multiverse Hackathon — press release](https://m.thewire.in/article/ptiprnews/qualcomm-india-opens-registrations-for-snapdragon-multiverse-hackathon-to-build-multi-device-ai-solutions)
