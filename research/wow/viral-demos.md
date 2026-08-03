# Viral On-Device/Edge AI Demos: Anatomy of "Wow" — and What QNet Home Should Steal

Research pass for Snapdragon Multiverse Hackathon (Aug 3–7, 2026). Compiled Aug 3, 2026.

> **Methodology note:** WebSearch quota was exhausted almost immediately this session (pre-consumed before this task started), so this report leans on (a) targeted WebFetch of specific pages — Wikipedia, GitHub, project sites — cited inline with URLs, (b) the GitHub REST search API (curl, no auth) to verify repo names/star counts/dates directly, and (c) my own trained knowledge of the 2023–2026 viral-AI-demo canon for items I could not re-fetch live (Reddit is network-blocked from this box; several TechCrunch/Verge/Qualcomm URLs 404'd or were paywalled). Every item below is tagged **[VERIFIED]** (fetched live this session, URL given) or **[RECALL]** (from training knowledge, cutoff Jan 2026 — sanity-check specific numbers before quoting them to judges). Nothing here is fabricated; RECALL items are things I'm confident happened but couldn't re-fetch a fresh source for today.

---

## 1. The anatomy of "wow" — a hook taxonomy

Before the catalog, the recurring psychological triggers that made these demos land (or fail). Everything below maps back to one or more of these:

| Hook | Mechanism | Example |
|---|---|---|
| **Latency-as-life** | Sub-second response makes a system feel *alive* rather than *queried*. Barge-in (interrupting mid-sentence) is the strongest version — only living things get interrupted. | GPT-4o voice mode, Groq token-speed demos |
| **Anthropomorphism via voice/persona** | A distinctive voice/character (Attenborough, a robot with "attitude") converts a tensor pipeline into a *character* the audience roots for. | `narrator` (Attenborough), Boston Dynamics Spot |
| **Autonomy / emergent behavior** | The system does something *nobody scripted in that exact form* — agents deciding, on their own, to change protocol. | GibberLink |
| **Spatial/embodiment surprise** | AI reaching into physical space (robot moves, a doorbell talks back, a room lights up) breaks the "it's just a chatbot" mental model. | Figure/Helix robots, roast-my-doorbell projects |
| **Transparency-as-magic ("prove it")** | Physically demonstrating a constraint holding — unplugging the network and showing it still works — is *more* impressive to technical judges than a bigger model, because it proves the architecture claim rather than asserting it. | Qualcomm on-device LLM/Stable Diffusion demos with connectivity killed |
| **Multi-agent choreography** | Two+ independent systems visibly coordinating live, with no human in the loop, reads as "this is a fabric, not a gadget." | GibberLink, phone-vs-phone voice-mode clips, CES multi-robot stage demos |
| **Vulnerability / roast / stakes** | Comedic risk (will it roast *me*?) or safety risk (will it catch the fall?) creates genuine suspense instead of a rehearsed showcase. | Doorbell-roast projects; fall-detection demos |
| **Honest failure / graceful degrade** | Paradoxically, a demo that shows a *limit* and handles it gracefully builds more trust than one that hides limits — until it fails on stage unrehearsed. | Contrast: Gemini "Hands-on" video (hid the seams, got caught) vs. Humane Pin (seams visible live, credibility died) |

---

## 2. Catalog

### A. Ambient narration lineage ("AI watches and describes my life")

**1. `narrator` — "David Attenborough narrates your life" — Charlie Holtz** **[VERIFIED]**
- Repo: `cbh123/narrator`, created **2023-11-14**, **4,426 GitHub stars**, Python. github.com/cbh123/narrator
- Built at a Replit/OpenAI hackathon: grabs a webcam frame every few seconds → GPT-4V describes the scene in Attenborough's naturalist register → ElevenLabs voice-clones Attenborough reading it aloud, near-real-time.
- Spawned an entire fork lineage doing the same trick with other voices/personas: `Doriandarko/narrator`, `paulirish/narrator`, `rsmets/ai-narrator`, and comedic variants like `import-fola/kanye-roast` ("Kanye West roasts your landing page").
- **Why it hit:** zero stakes, universal referent (everyone recognizes the Attenborough register instantly), and the *incongruity* of nature-documentary gravitas applied to someone eating cereal. Pure anthropomorphism + persona hook, near-zero latency requirement (a few seconds of lag is *part of the bit*, unlike a safety alert).
- **QNet mapping (wow: high / feasibility: high):** Do NOT clone the joke literally (mismatched to safety framing) but steal the *mechanism*: your hub already narrates room events in natural language via TTS. Give it exactly one moment in the demo where the narration voice is warm/personal (the caregiver-parent-clone voice) reading a genuinely mundane, true-to-life event with dry warmth — "Grandma just got up for water, 2:14am, gait steady, no concern" — landing the humor/warmth beat *without* breaking the privacy narrative, because the wow here is "it noticed, in words, without a camera anyone can rewind."

**2. Moondream (0.5B / 2B) — tiny vision-language model** **[VERIFIED]**
- `vikhyat/moondream`, **9.9k stars**, Apache-2.0. Two SKUs: **Moondream 2B** general-purpose, **Moondream 0.5B** explicitly positioned for edge devices. Ships a `webcam_gradio_demo.py` for live webcam captioning; hosted playground at moondream.ai/playground.
- **Why it matters for us:** this is a *sub-1B* VLM aimed squarely at the "runs on a doorbell/Arduino-class device" niche — smaller than SmolVLM's smallest video variant.
- **QNet mapping (wow: medium / feasibility: high):** a 0.5B VLM is plausibly the right size class for the QRB2210 (no NPU, 4×A53) to do a *local* one-line visual gloss ("person at door, holding package") that becomes the semantic JSON event — never the frame itself. This is the literal mechanism of "privacy by construction": show the model output text, then show the frame buffer being zeroed/never transmitted. That contrast (text out, no pixel out) is a very demonstrable, judge-legible technical claim.

**3. SmolVLM / SmolVLM2 — HuggingFace's "smallest video LM"** **[VERIFIED]**
- huggingface.co/blog/smolvlm2 — three sizes: **2.2B**, **500M**, and **256M** (described as "the smallest video model ever released"). Ships three reference apps: a fully local **iPhone app running the 500M model with zero cloud calls**, a VLC plugin for semantic video search/navigation, and a "highlight generator" that mines 1+ hour videos for key moments.
- SmolVLM also has a well-known **in-browser, WebGPU, real-time webcam demo** (community-run HF Spaces) — captioning your own webcam feed live, no server round-trip. [RECALL: I could not re-fetch the specific Space page this session (401/404), but this demo pattern is well established in the SmolVLM release cycle and widely reshared on X/HN through 2025.]
- **QNet mapping (wow: high / feasibility: medium):** the "runs the whole pipeline in-browser via WebGPU, camera never leaves the tab" framing is *exactly* the demo-grammar you want for the hub UI: show the dashboard doing on-device inference with dev tools open and Network tab empty. Even if your actual runtime is GenieX/NPU rather than WebGPU, borrowing this "open the Network tab, show zero egress" visual proof is one of the cheapest, highest-leverage wow beats available — it's a courtroom-style exhibit, not a claim.

### B. Multi-agent / multi-device coordination ("things talking to each other, not to us")

**4. GibberLink — AI agents switch to sound when they realize they're both AI** **[VERIFIED]**
- Winner, **ElevenLabs × a16z hackathon, London, Feb 2025**. Built by **Anton Pidkuiko and Boris Starkov**. Two ElevenLabs conversational agents (one "caller," one "hotel receptionist") converse in English; the moment each identifies the other as an AI, both switch to **ggwave** — Georgi Gerganov's data-over-sound protocol — and finish the transaction as machine-readable chirps. Live demo hosted at **gbrl.ai**; the ggwave web decoder can decode the chirps in real time straight off a YouTube video's audio track. Covered by Forbes, TechCrunch.
- **Why it hit:** pure autonomy hook — nobody told the agents to do this in that exact moment, it's a *policy* that fires conditionally, and the sudden shift from human-legible speech to alien beeping is genuinely uncanny (sci-fi "machines have their own language" trope, made real).
- **ggwave itself** [VERIFIED]: `ggerganov/ggwave`, **7,777 stars**, "tiny data-over-sound library." Critically for our kit: **`ggerganov/ggwave-arduino`** exists (61 stars) — an Arduino-ported mirror in the Arduino Library Manager. Also ports for Java/Android, Swift, Kotlin Multiplatform, Flutter, and even an SDR transmitter variant.
- **QNet mapping (wow: very high / feasibility: medium-high — THIS IS THE STANDOUT FIND):** GibberLink is arguably the single most stealable *mechanism* in this report for a multi-device safety fabric, because ggwave already runs on Arduino. Concrete demo beat: **kill the Wi-Fi/network live on stage.** The Arduino UNO Q node (which has no NPU and is GStreamer-native — i.e., it's the "dumb sensor" node in your fabric) detects a safety event, and instead of failing silently because the network is down, it **emits an audible/ultrasonic ggwave chirp** that the PC hub's microphone picks up and decodes into the semantic event — no Wi-Fi, no Bluetooth pairing, just sound across the room. This proves three crux claims simultaneously in about 15 seconds: (1) multi-device fabric survives infrastructure failure, (2) the channel is inherently bandwidth-limited to *symbols*, i.e. architecturally incapable of carrying video/audio payloads — privacy-by-construction, not policy — and (3) it's a genuinely novel, technically real, unrehearsed-feeling "prove it" moment judges have not seen from another team. Recommend: build this as the "if all else fails" fallback path, not primary transport, and time-box the R&D — ggwave-arduino integration risk should be spiked on day 1.

**5. Two ChatGPT Advanced Voice Mode phones talking to each other** **[RECALL]**
- Widely-reshared clips (X/TikTok, 2024) of people holding two phones face to face, each running GPT-4o's voice mode, and letting the assistants converse — sometimes escalating into singing together, arguing about who's the real AI, or looping. No canonical single source; this is a *format* that recurred many times, not one video.
- **Why it hit:** watching two instances of "the AI" interact without a human mediating triggers the same autonomy/spatial-surprise hook as GibberLink but with zero setup — anyone can replicate it in 10 seconds, which is exactly why it went wide.
- **QNet mapping (wow: medium / feasibility: high):** cheap, low-risk stage beat — have two room nodes' TTS voices "confer" out loud about a borderline event before escalating to the caregiver ("Kitchen, did you see that too?" / "Confirmed, hallway sensor agrees") — makes the agentic reasoning *audible* rather than a backend log line judges have to take on faith.

**6. Boston Dynamics Spot + ChatGPT — the robot with a scripted personality** **[RECALL]**
- Aug 2023: engineers duct-taped ChatGPT + a text-to-speech voice + a static "character" prompt onto Spot's arm-mounted head, then had it lead a "factory tour," commenting on its own surroundings and cracking jokes in-voice. Went viral on Twitter/YouTube.
- **Why it hit:** embodiment + anthropomorphism combo — the *same* underlying LLM API call reads as dramatically more alive when it comes out of a physical robot's "head" moving in the room, versus a chat window.
- **QNet mapping (wow: medium / feasibility: low for us):** we have no robot in kit, but the transferable lesson is: **route agentic speech through a fixed point in physical space** (a speaker in the room where the event happened, not a phone notification) — directionality of the voice response is doing real anthropomorphic work even without any moving parts.

**7. CES humanoid-robot stage swarms (NVIDIA Isaac/GR00T, Figure, Unitree, etc.)** **[RECALL, general pattern across CES 2024–2026]**
- Recurring CES/GTC keynote beat: multiple humanoid or quadruped robots on stage simultaneously, responding to voice, sometimes visibly stumbling or needing a human assist — famous instances of on-stage wobble/fall became their own viral (schadenfreude) clips.
- **Why it hit / why it sometimes backfired:** multi-unit *simultaneous* live operation is the hook (proves it's not one cherry-picked unit), but live hardware redundancy risk is real — a visible stumble reads as "not ready," undermining the exact claim being made.
- **Lesson for QNet:** if staging multiple nodes live (PC hub + phone + Arduino node + a second room node), **rehearse the failure path explicitly** — a node going offline should be a *scripted, narrated* resilience beat ("watch — node drops, hub falls back to cached policy") rather than something that silently breaks and reads as a bug.

### C. Real-time multimodal ("it sees the room and talks in real time")

**8. GPT-4o launch, May 13 2024** **[VERIFIED core facts + RECALL demo specifics]**
- Verified: GPT-4o added native voice-to-voice ("Advanced Voice Mode"), a real step-change from the old STT→LLM→TTS pipeline latency of prior ChatGPT voice. [en.wikipedia.org/wiki/GPT-4o]
- Demo specifics widely reported (RECALL, high confidence but not re-fetched today): live camera reasoning (pointing the phone at handwritten algebra, getting tutored in real time), live two-language interpretation, singing on request, and — the actual core wow — **being interrupted mid-sentence and gracefully changing tack**, i.e. barge-in as the headline feature, demoed live.
- **The controversy is VERIFIED and is itself a lesson:** the "Sky" voice was pulled May 20, 2024 after Scarlett Johansson said OpenAI approached her to license her voice, she declined, and Sky sounded "eerily similar" anyway; Altman's cryptic "her" tweet fanned it. Widely covered as a major self-inflicted PR wound.
- **QNet mapping (wow: very high for barge-in / hard no on the persona-cloning risk pattern):** barge-in is explicitly already in your scope — treat it as a headline demo beat, not a background feature: script a moment where a caregiver *interrupts* the hub mid-sentence and the hub yields instantly. On the ElevenLabs cloned-parent-voice feature: the Johansson episode is a direct cautionary parallel — **make consent explicit and visible in the demo** (show the opt-in flow, a real recorded consent clip) rather than just narrating "it's opt-in," because judges who remember GPT-4o's voice scandal will actively probe this.

**9. Google Bard demo error, Feb 8 2023, Paris** **[VERIFIED]**
- Live-streamed demo answered a question about the James Webb Space Telescope incorrectly; caught immediately by viewers; contributed to an **8% single-day stock decline** for Alphabet. [en.wikipedia.org/wiki/Gemini_(chatbot)]
- **Lesson:** a factual/perceptual error in a *canned, non-interactive* demo slide did more brand damage than most live-interaction stumbles, because it read as "they didn't even check their own headline example." **For QNet: pre-verify every scripted example event against the actual sensor ground truth before the judged run — don't let a slide claim something the live system can't currently reproduce.**

**10. Google "Hands-on with Gemini" video, Dec 2023, and its unraveling** **[RECALL — could not re-fetch a source this session; Wikipedia's Gemini article did not surface it, TechCrunch/Verge URLs 404'd/blocked]**
- My recollection: Google published a slick demo video implying real-time multimodal reasoning over live video/voice; it later emerged (Bloomberg and others) that the video was assembled from still frames and text prompts, not live interaction, triggering "Google faked its Gemini demo" backlash.
- **Flag: verify this before citing specific numbers on stage** — I'm confident the episode happened and the throughline (staged-video backlash) is real, but I could not re-confirm exact dates/quotes live this session.
- **Lesson (robust regardless of exact sourcing details):** the single most reputation-damaging move available to a hyped-AI demo is presenting **edited/staged footage as live capability**. For a judged hackathon demo, this argues strongly for **running everything live, in the room, on the actual kit** — including risking a visible stumble — over a pre-rendered "trust us" video reel.

**11. Project Astra (Google DeepMind), I/O 2024 → Android XR, Dec 12 2024** **[VERIFIED]**
- Prototype smartglasses demoed at I/O 2024, camera + voice fused into one Gemini Ultra-backed assistant, understanding what the wearer sees, in conversation. Google later announced **Android XR** (Dec 12 2024) with Samsung's "Moohan" headset and Astra glasses targeting a 2025 release (exact multi-device stage choreography for 2025+ not confirmed in the source I could pull).
- **QNet mapping (wow: high / feasibility: n/a for our kit but relevant framing):** Astra's pitch line — "an assistant that sees what you see and remembers what matters" — is the *consumer-productized* mirror image of what QNet Home explicitly refuses to do (never persist raw video/audio). Worth a single explicit slide/beat contrasting: "Astra-style assistants centralize seeing; QNet Home is built so no hub, cloud, or judge can ever see the room — only what happened, in words." Direct competitive contrast for judges who know the Astra/Gemini-for-Home category.

**12. Meta Ray-Ban smart glasses "Live AI"** **[RECALL — partial VERIFIED via Wikipedia, weak]**
- Wikipedia confirms Meta AI is baked into 2nd-gen Ray-Ban Meta glasses with camera input since an update. RECALL (not re-verified today): Meta's "Live AI" continuous-narration mode and live-translation-through-glasses demos at Meta Connect 2024, plus a wave of TikTok/YouTube content of blind/low-vision users using the glasses as a real-time describe-the-world aid ("Be My Eyes"-style) — this sub-genre got significant, genuinely moving viral traction because the stakes (independence for a disabled user) are real, not a party trick.
- **QNet mapping (wow: high / feasibility: high):** the accessibility framing is directly reusable and underused in AI safety pitches — cast one demo beat explicitly as "this is how a homebound elder or a kid with a medical condition gets independence *without* a camera watching them," borrowing the emotional register of the Be-My-Eyes clips rather than the generic "smart home" register.

### D. Home / security camera specific (direct competitive landscape)

**13. Ring — the cautionary contrast case, and it's getting worse, not better** **[VERIFIED, and notably recent — Aug 2025–Feb 2026]**
- **Sept 2025:** Ring launched **"Familiar Faces"** (beta) — explicitly a facial-recognition feature marketed as "reduces notifications by recognizing people you know" — despite Amazon's long-standing public claim "Ring does not use facial recognition." Internal docs previously revealed a shelved "Proactive Suspect Matching" facial-recognition plan.
- **Oct 2025:** Ring shipped **"Search Party"** — AI that scans camera footage network-wide to find lost pets — **enabled by default, opt-out**, launched with a Super Bowl ad. Critics immediately flagged it as a template for human-tracking at scale.
- **Also Oct 2025:** Ring partnered with **Flock Safety** (ALPR/license-plate-recognition camera network) — widely covered as a mass-surveillance escalation; **by Feb 2026, Ring withdrew from the partnership** amid backlash.
- Historical: Ring discontinued its formal police video-request portal (Jan 2024) after facilitating warrantless-adjacent footage requests across ~200 agencies; a 2023 FTC settlement ($5.8M) found Ring employees had improperly accessed customer video, including one employee viewing footage of 81 women.
- **This is the single best "why we exist" exhibit available to the team, and it is maximally current** (this week's news cycle, essentially). **Demo mapping (wow: very high / feasibility: trivial — it's a slide, not an engineering task):** open the judged demo with 60 seconds contrasting Ring's actual, real, ongoing 2025–2026 trajectory (opt-out facial recognition → opt-out pet-tracking AI → ALPR partnership → walked back under backlash) against QNet Home's inverse architecture (opt-in, semantic-only, on-device, no raw media ever transmitted, by construction not by policy toggle). This is not a strawman — it is literally what the market leader shipped in the last twelve months, and judges scoring "Innovation" and "Deployment" will recognize the reference immediately.

**14. Google Home / Nest "Gemini for Home" — generative descriptions of camera events** **[NOT independently re-verified this session — blog URL 404'd; RECALL]**
- Google has been rolling out natural-language event summaries for Nest cameras ("a person in a red jacket left a package on the porch") powered by cloud Gemini — the direct cloud-based analog of what your hub does locally.
- **QNet mapping (wow: medium / feasibility: n/a):** another "we do the same UX, opposite architecture" contrast point — the *feature* (plain-English event narration) is now table stakes and expected by judges; your differentiator has to be visibly the *architecture* (on-device, tiered SLM, never-leaves-the-building), not the narration feature itself, because Google already normalized the narration UX.

**15. Frigate NVR — the r/homeassistant community's favorite, entirely local** **[attempted verify, page 404'd; RECALL, high confidence]**
- Frigate is a self-hosted NVR doing local object detection (commonly on a Coral TPU or GPU) integrated tightly with Home Assistant; it's a recurring highly-upvoted topic on r/homeassistant precisely because it lets people get "smart camera" features with zero cloud dependency.
- **QNet mapping (wow: medium / feasibility: n/a, but validates market appetite):** Frigate's sustained community enthusiasm is evidence the "local-only camera AI" audience is large, engaged, and specifically motivated by privacy — useful as market-validation language in the pitch ("this audience already exists and is vocal").

**16. Roast-the-doorbell / snarky-camera projects** **[RECALL — I could not find a single canonical repo via GitHub search this session, likely because they're scattered under generic names/blog posts rather than a shared repo name; this is a real, recurring genre across YouTube/Twitter/Reddit, not one project]**
- Recurring maker-community genre (2023–2026): point a camera + GPT-4V-class model at a doorbell/driveway, generate a snarky/roasting one-liner about whoever's on camera, speak it out loud through a doorbell speaker or push it as a notification. Repeatedly resurfaces on Twitter/YouTube Shorts because the "will it roast *me*" suspense is inherently shareable.
- **QNet mapping (wow: medium-high for a stage demo, feasibility: high, but be careful with framing):** the comedic register is off-brand for "home safety," BUT the underlying mechanism — real-time, in-room, spoken commentary about who/what the system just perceived — is exactly your agentic-in-room-response crux. Recommend: use the *mechanism* (camera event → semantic description → spoken response, latency low enough to feel live) but keep tone warm/protective rather than snarky, EXCEPT possibly one intentionally light beat (e.g., the hub gently teasing a teenager sneaking a snack past curfew) to prove the system has *personality*, not just alarms — one comedic beat mid-demo resets judge attention before the safety climax.

### E. NPU / Copilot+ PC / Qualcomm-adjacent demo patterns

**17. Microsoft Recall — the industry's most-discussed on-device-AI privacy demo, and its collapse** **[VERIFIED]**
- Launched May 2024 alongside Copilot+ PCs: continuously screenshots the desktop, an **on-device** model (not cloud) makes it semantically searchable. Requires a **40 TOPS NPU**, 16GB RAM, BitLocker, Windows Hello — i.e., explicitly gated to exactly your hardware class (Snapdragon X Elite / Copilot+ PCs).
- Backlash: security researchers (the "Total Recall" tool) showed the local database was **not adequately encrypted**, meaning "on-device" alone did not equal "private" — anyone with local/malware access could exfiltrate a plaintext-ish activity log.
- Microsoft response: delayed the June 2024 ship date, made it **opt-in** (was going to be on-by-default), added **full database encryption**, added an uninstall path. Third-party privacy tools (Signal, Brave, AdGuard) added DRM-style screen-capture blocking specifically to defeat Recall.
- **This is the most important single case study in this report for your Technical/Deployment scoring.** **Lesson, very directly transferable:** "runs on an NPU, on-device" is **necessary but not sufficient** for a privacy claim — judges who know this history (very likely, given the Qualcomm/Microsoft crossover in this exact hardware class) will ask "is it encrypted at rest, is it opt-in, what happens if the hub itself is compromised?" **Concrete demo beat:** explicitly state and show that QNet Home's on-device events are (a) semantic-only at the point of capture — there is no raw-media database to leak in the first place, unlike Recall's screenshot log — and (b) show the storage/encryption story for whatever event history you do retain. Beating Recall's exact failure mode ("device compromise still leaks a media log") by design is a very sharp, judge-legible technical talking point: *"Recall's local database was the vulnerability; QNet Home has no local media database to steal — the data minimization happens before storage, not after."*

**18. Qualcomm's "pull the network cable" on-device LLM/diffusion demos** **[RECALL — pattern well-established across multiple Snapdragon Summits, could not re-fetch a specific 2025/2026 source this session; Qualcomm newsroom search didn't surface a specific match]**
- Recurring Qualcomm demo pattern since ~2023: run an LLM or Stable-Diffusion-class image model entirely on-device on a Snapdragon NPU, then **disable Wi-Fi/cellular live** to prove there's no cloud call happening, and show generation continuing unaffected.
- **This is directly, mechanically stealable and is probably the single highest wow/feasibility item you should actually build regression-tested for the judged run:** stage moment — **physically unplug the hub's ethernet / kill Wi-Fi** in front of judges, then trigger a safety event end-to-end (edge node → semantic event → SLM reasoning → TTS speech in the room). If it still works, you've proven "on-device," "privacy-by-construction," and "resilient fabric" in one ~20-second unrehearsed-feeling beat, using a demo grammar Qualcomm itself has trained conference audiences (and likely some judges) to trust as *the* proof-of-locality gesture. Pair this with beat #4 (ggwave fallback) for a one-two punch: kill network → primary path still works because it's local NPU inference → for the sensor-node link specifically, even RF-level connectivity is optional because of the acoustic fallback.

**19. Groq — speed itself as the demo** **[VERIFIED existence/positioning via Wikipedia; specific tokens/sec figures NOT re-confirmed this session, RECALL]**
- Verified: Groq rebranded its chip as an "LPU" (Language Processing Unit) and pushed hard on "fast LLMs on old silicon," launching GroqCloud Feb 2024 specifically to let developers feel the speed via API.
- RECALL: the viral artifact was screen-recordings/GIFs of a full paragraph-length LLM response appearing to render *faster than the viewer can read it*, shared widely on X circa 2024, with claimed 300–800 tokens/sec depending on model — **verify exact current numbers before citing.**
- **QNet mapping (wow: high / feasibility: depends entirely on your actual measured NPU numbers):** speed-as-spectacle is a legitimate, low-production-cost wow if your numbers are genuinely good — a simple on-screen live counter ("247ms edge-to-speech, 0.4W draw") during the safety-event demo doubles as your Technical-40 evidence and a wow beat simultaneously. This is the cheapest overlap between "judged criteria" and "audience wow" available to you — build the live latency/energy HUD regardless of anything else in this report.

### F. Legendary failures — what not to do

**20. Humane AI Pin** **[VERIFIED]**
- TED Talk reveal May 2023 → announced Nov 9 2023 → shipped April 2024 at $699. Overheating so severe that **executives reportedly chilled units with ice packs before investor demos**; the built-in projector was limited to 9 minutes of use due to thermal issues. MKBHD's review, titled "The Worst Product I've Ever Reviewed... For Now," became the defining public verdict. Returns exceeded sales by Aug 2024; company discontinued the product **Feb 2025**; devices **bricked entirely Feb 28 2025** when servers shut off.
- **Lesson:** a beautiful launch narrative (TED Talk, ambient computing vision) cannot survive *thermal/reliability failure in the reviewer's actual hands*, and cloud-server dependency means the product can be unilaterally killed — the opposite of the local-first resilience story you're telling. **For QNet: never demo on hardware you haven't stress-tested for the exact session length; have a cold spare of every device plugged in and ready.**

**21. Rabbit R1** **[VERIFIED]**
- CES 2024 reveal on the "Large Action Model" (LAM) narrative sold **130,000 units on hype alone** before a single independent review. Reviewers (MKBHD: "barely reviewable") found it was substantially **an Android app** wrapped in bespoke hardware — a framing the founder disputed but couldn't fully rebut. By Sept 2024, only **~5,000 of the first 100,000 buyers were still actively using it.**
- **Lesson:** an impressive *keynote-narrated capability* ("it can order you an Uber just by asking!") that turns out to be a thin wrapper around existing APIs, once discovered, retroactively poisons every other claim the team made. **For QNet: be precise and honest on stage about what's genuinely running on-device/on-NPU vs. what's a cloud call (e.g., AIC100 red-team rig, ElevenLabs voice cloning) — judges in a hackathon with a 40-point Technical rubric will ask, and getting caught overstating locality is the single most reputation-costly failure mode available to you, worse than a modest but honest number.**

**22. CES "perpetual demo, never ships" pattern (e.g., Samsung Ballie)** **[RECALL, general pattern, not independently re-verified this session]**
- Samsung's Ballie companion robot has been demoed at multiple CES cycles without a shipping consumer product, becoming a standing industry joke about demo-vs-product gap.
- **Lesson:** repeated re-demoing of the *same* capability without visible progression reads as stalling. Not directly applicable to a one-shot hackathon, but reinforces: **show a number that's better than a previous number** (latency, power draw) if you reference any earlier prototype milestone, rather than just re-showing the same trick.

---

## 3. Ranked: the 10 hooks most stealable for your 4-minute judged demo

Ordered by (wow × feasibility × crux-relevance) for a 4-minute slot, not by raw viral magnitude.

1. **Kill the network live, mid-demo, and keep going.** (Qualcomm on-device-proof pattern, #18) — proves privacy-by-construction and NPU locality in ~20 seconds, judge-legible, zero extra build cost beyond making sure it's actually true.
2. **Acoustic fallback via ggwave on the Arduino node.** (#4, GibberLink lineage) — with #1, this is a one-two punch: kill Wi-Fi, the sensor node still reaches the hub via sound. Novel, nobody else at this hackathon will have this, directly proves multi-device fabric resilience and architectural (not policy) privacy. Highest risk/highest distinctiveness item — spike it Day 1, have a graceful fallback demo path if the spike fails.
3. **Live latency + power HUD overlay during the safety event.** (#19, Groq-style speed-as-spectacle) — doubles as your Technical-40 evidence and an audience wow; cheapest overlap between judging rubric and spectacle.
4. **Open the Ring 2025–2026 headline slide as your cold-open.** (#13) — maximally current, real, and damning contrast; costs nothing but 60 seconds of narration; instantly frames "why this matters" for Innovation/Deployment judges without you having to argue it abstractly.
5. **Barge-in as a headline beat, not a footnote.** (#8, GPT-4o) — script an explicit "caregiver interrupts the hub mid-sentence" moment; interruptibility is the strongest available "it feels alive" signal and you already have the capability in scope.
6. **Explicit, on-screen consent flow for the cloned parent voice.** (#8, Johansson lesson) — pre-empts the single sharpest question a judge who remembers GPT-4o's Sky controversy will ask; turns a risk into a differentiator ("here's the consent receipt").
7. **Network tab / "zero egress" visual proof for on-device inference.** (#3, SmolVLM WebGPU demo grammar) — cheap, borrowed exhibit-style proof that reads as rigorous rather than asserted.
8. **One warm, personal narration moment in the cloned-parent voice.** (#1, Attenborough lineage) — landing genuine warmth (not comedy) proves the system has emotional register, not just alarms; contrast this against Ring's cold, transactional "Familiar Faces" framing.
9. **One light comedic beat, tonally controlled.** (#16, roast-doorbell genre, softened) — a single gentle, protective-not-mocking joke resets audience attention before the safety climax; use sparingly, once, mid-demo.
10. **Recall's exact failure mode, beaten explicitly.** (#17) — "on-device is necessary but not sufficient; here's what we do differently at the storage layer" — the single sharpest technical-credibility line available if a judge has any Copilot+ PC / Recall background (plausible, given the hardware kit).

---

## 4. Explicit non-recommendations

- **Do not** build anything resembling Rabbit R1's pattern of narrating a capability that's actually just an API wrapper — if AIC100 or ElevenLabs cloud calls are in the loop, say so plainly on the latency HUD (e.g., color-code "on-device NPU" vs "cloud/off-hot-path").
- **Do not** pre-record or edit any part of the judged demo footage — the Gemini "Hands-on" backlash (#10) and the Bard stock-drop (#9) both stem from claims not matching live reality; run everything live even if riskier.
- **Do not** lean on comedic "roast" framing as the primary tone for a safety product pitched to judges scoring deployment seriousness — use it as a single accent beat at most (#9 above), not the demo's spine.

---

## Sources

- [cbh123/narrator (GitHub)](https://github.com/cbh123/narrator) — verified stars/date via GitHub API
- [vikhyat/moondream (GitHub)](https://github.com/vikhyat/moondream)
- [SmolVLM2 announcement (Hugging Face blog)](https://huggingface.co/blog/smolvlm2)
- [PennyroyalTea/gibberlink (GitHub)](https://github.com/PennyroyalTea/gibberlink)
- [ggerganov/ggwave (GitHub)](https://github.com/ggerganov/ggwave)
- [ggerganov/ggwave-arduino (GitHub)](https://github.com/ggerganov/ggwave-arduino)
- [Home Assistant Voice Preview Edition](https://www.home-assistant.io/voice-pe/)
- [Humane AI Pin (Wikipedia)](https://en.wikipedia.org/wiki/Humane_AI_Pin)
- [Rabbit R1 (Wikipedia)](https://en.wikipedia.org/wiki/Rabbit_R1)
- [Windows Recall (Wikipedia)](https://en.wikipedia.org/wiki/Recall_(Windows))
- [Figure AI (Wikipedia)](https://en.wikipedia.org/wiki/Figure_AI)
- [Gemini chatbot / Bard demo incident (Wikipedia)](https://en.wikipedia.org/wiki/Gemini_(chatbot))
- [Groq (Wikipedia)](https://en.wikipedia.org/wiki/Groq)
- [Ring (company) — privacy controversies (Wikipedia)](https://en.wikipedia.org/wiki/Ring_(company))
- [Project Astra (Wikipedia)](https://en.wikipedia.org/wiki/Project_Astra)
- [GPT-4o (Wikipedia)](https://en.wikipedia.org/wiki/GPT-4o)
- [fluxions-ai/vui (GitHub)](https://github.com/fluxions-ai/vui) — local barge-in voice assistant landscape, bonus find

**Not independently verifiable this session (network/search constraints) — treat as recollection to spot-check before quoting numbers on stage:** Google "Hands-on with Gemini" staged-video controversy (Dec 2023); exact Groq tokens/sec figures; Meta Ray-Ban "Live AI" Connect 2024 specifics; Google/Nest "Gemini for Home" feature details; Frigate NVR specifics; Samsung Ballie CES history; Boston Dynamics Spot+ChatGPT demo (Aug 2023); specific Qualcomm Snapdragon Summit "pull the cable" demo dates.
