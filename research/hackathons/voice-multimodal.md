# Voice AI & Multimodal Hackathon Research (Aug 2024 – Aug 2026)

Research pulled for QNet Home (Snapdragon Multiverse Hackathon, Aug 3-7 2026) to sharpen positioning,
avoid overdone ideas, and find concrete technical/pitch tricks that judges have rewarded in adjacent
voice-AI / multimodal / multi-device hackathons — including **prior runs of the exact hackathon series
we are competing in**.

---

## 1. ElevenLabs x a16z Worldwide Hackathon (Feb 22-23 2025, 9 cities + online, 1,300+ participants, 300+ projects)

Judges: Mati Staniszewski (ElevenLabs CEO), Guillermo Rauch (Vercel), James Hawkins (PostHog), Anton Osika (Lovable),
a16z partners Bryan Kim & Justine Moore. Criteria: innovation, technical execution, practical use of
ElevenLabs/partner tech, demo quality.

**Global winner — GibberLink** (Boris Starkov, Anton Pidkuiko, London). Two ElevenLabs Conversational-AI
voice agents chat in English, use a tool-call to detect "the other side is also an AI," then drop out of
human speech entirely and switch to **ggwave** (Georgi Gerganov's open-source data-over-sound library,
audio-modem style, like a 1980s dial-up handshake) to exchange the rest of the payload as machine-readable
acoustic bursts — claimed **80% faster, error-proof** exchange vs. continuing in natural language. Went
viral (Forbes/TechCrunch coverage), won the global prize, GitHub: `PennyroyalTea/gibberlink`.
- *Why it won*: a single, extremely legible "wow" demo trick (you can literally hear two devices decide
  to stop talking like humans) built on an existing OSS primitive — small amount of code, huge visual/aural payoff.

**Other notable regional winners:**
- **Hugo** (1st online) — location-aware AI travel companion, voice+location fusion.
- **Pep** (2nd online, Feng Yan & Lora Xie) — multimodal **voice + vision** agent that watches a patient
  do physical-therapy exercises via camera and coaches them in real time through voice. Directly analogous
  to our pose-estimation-plus-voice-coaching pattern, but for PT rather than falls.
- **Agent SFX** (3rd online) — vision models generating game voiceover/SFX from scene graphs (fal.ai + Godot).
- **DeepSky** (Warsaw) — voice AI agent for airspace safety (Air Traffic Control-style monitoring/escalation).
- **Roadmate** (2nd, San Francisco; Anwar Mujeeb, Russell Semsem, William Xuan) — dual dashcam-style
  vision pipeline detects driver drowsiness from facial cues, an ElevenLabs voice agent has a live
  conversation to keep the driver alert and adapts based on alertness level, and **auto-texts an emergency
  contact with location if the driver doesn't respond** — essentially our "assess → converse → escalate"
  loop, but for cars. Origin story: a founder's friend crashed from drowsy driving the prior week (personal
  narrative framing helped the pitch).
- **Voice Guardian** (Seoul) — "protects your home with AI voice," home-security voice agent. Confirms
  voice-agent-for-home-security is already a known hackathon pattern — we should be explicit that QNet Home
  is not a security/intrusion system but a **care/wellbeing** system, to avoid being lumped in as derivative.
- **Espresso Labs / Vox Populi** (London) — generic voice assistant / 3D speech-interactive game — low
  differentiation, illustrates that "just another conversational voice agent" without a hardware/systems
  angle blends into the crowd.

**Later event — ElevenLabs "Project Europe" hackathon (Dec 2025):** grand prize (€10,000) went to
**qForge**, which turned voice input into a fully interactive storytelling engine — another example of
"voice → generative content" winning, but not multimodal/multi-device.

---

## 2. AssemblyAI $50k Hackathon (NYC, Dec 6 2024)

**Winner — Dealty** (Slavik Kaushan, Mario Uribe): real-time streaming STT + entity extraction to
auto-populate a real-estate deal form while a call is happening. **Runner-up — Muse**: voice-driven mental
health journaling assistant. **Special recognition — Say What**: audio-clip guessing game for interactive
learning.
- *Takeaway*: none of AssemblyAI's top projects touched elder care, family, or vision fusion — the winning
  pattern here was "transcribe + structure a real conversation into actionable data in real time," which is
  a useful sub-pattern for us (e.g., structuring the "Are you OK?" conversation transcript into a caregiver
  summary), but this contest alone doesn't validate our concept — it shows a *generic* voice-AI hackathon
  skews toward productivity tools, not home/safety.

---

## 3. UC Berkeley AI Hackathon 2024 (Cal Hacks/SkyDeck, Intel-sponsored) — DispatchAI, Grand Prize, $64k pool

**DispatchAI** (`github.com/IdkwhatImD0ing/DispatchAI`): an empathetic AI 911-dispatcher assistant.
Architecture directly relevant to QNet Home's "assess → converse → escalate" loop:
- **Hume EVI** does real-time **emotion/prosody analysis** of the caller's voice to gauge distress level,
  feeding severity/triage decisions (not just semantic content — the *tone* matters).
- A **custom fine-tuned Mistral-7B** (trained on a proprietary 911-call dataset) turns live call
  transcript + emotion + location/timestamp into a recommended action (e.g., dispatch ambulance).
- **Human-in-the-loop**: the AI recommends, a human dispatcher approves/edits — never fully autonomous
  for emergency actions.
- Stack: Twilio (call routing), Retell (voice-agent interface), Next.js/React frontend with live map
  (Leaflet), Intel Dev Cloud + IPEX for inference optimization.
- **Judges rewarded a hard, quantified number**: IPEX optimization cut inference latency from **2m53s to
  under 10s (≈80%+ reduction)**. They also open-sourced the fine-tuned model + dataset on HuggingFace.
- *Relevance*: this is close to the strongest single analog for our "fall/distress event → agent assesses
  → converses → escalates to caregiver" pipeline, and it proves judges reward (a) voice-tone/emotion as a
  triage input, not just words, and (b) a human-in-the-loop escalation gate, and (c) a big, specific,
  before/after latency number from on-device/optimized inference.

---

## 4. UC Berkeley LLM Hackathon (2023, "world's largest" at the time) — Hume-powered projects

1,200+ students, 240 projects, 57 used Hume's emotion APIs, 3 became finalists.
- **mila** (Best Use of Hume) — a device that listens to a mother's speech and uses Hume's vocal-emotion
  APIs to detect signals of **postpartum depression**, then connects her to a healthcare professional.
  Pitch framing leaned on empathy/human-connection messaging, not just tech.
- **Violet** — voice-enabled AI therapist combining facial-expression + speech-emotion analysis (GPT-4 +
  Hume) for mental-well-being counseling.
- **EdGauge** — webcam facial-expression analysis of confusion/boredom for teachers, real time.
- **Polysphere** — facial-expression-driven music recommendation/social matching.
- *Takeaway*: emotion-from-voice/face as an ambient signal for care/wellbeing is an established
  hackathon-winning pattern going back to 2023. It's a well-trodden idea, but almost nobody in these
  examples pairs vocal emotion with **vision pose events from a separate remote device** the way our
  two-node architecture would — that pairing is still a differentiator.

---

## 5. Qualcomm Snapdragon Multiverse Hackathon — THIS IS OUR HACKATHON SERIES (Princeton Sept 2025, Noida/Jalandhar, MIT CSAIL edition, Bengaluru 2026 edition)

This is the *same* Qualcomm hackathon franchise we are competing in this week (confirms format across
university sites). Key format facts from the Princeton page (closest to a rules doc we could access):
- 2-day, teams of 3-5, theme = **multi-device communication / seamless cross-platform experiences**.
- Each team gets a **Copilot+ PC (Snapdragon X Series)** as "control surface" + is encouraged to bring
  additional Snapdragon/microcontroller devices — i.e. the exact hub-and-edge-node pattern QNet Home uses.
- **Three suggested tracks**: (1) Real-time CV Assistant, (2) Conversational AI Companion, (3) RL Agent
  Arena. QNet Home spans tracks 1+2 simultaneously (vision-based edge sensing feeding a conversational
  agent hub) — a good sign our idea naturally covers more of the judged surface area than a single-track
  entry.
- Submission requirements already mirror our brief: GitHub repo + README + OSS license + a **Windows
  .EXE/.MSIX** + must run primarily on-device/edge.
- Two prize types: judged Top Award (across 4 unstated categories — almost certainly mirroring the
  "Technical / Innovation / Deployment / Presentation" rubric we were given) + peer-voted Team's Choice.

**Winning project at a Noida/Jalandhar instance of this same series: "Dragverse"** — an AI-powered
multi-device platform that takes a phone-captured 3D scan of a real environment, builds a digital twin,
trains a robot-control policy via RL inside the simulation, and deploys the trained model to a physical
robot. Prize: Snapdragon X2 Elite Copilot+ PCs + direct DevRel collaboration with Qualcomm engineering +
official blog/livestream feature.
- *Takeaway*: the pattern that won at a past instance of literally our hackathon was "phone senses the
  real world → PC does the heavy simulation/training → a third physical device acts on it" — i.e. a
  3-device pipeline with a clear physical-hardware payoff at the end. This validates that judges here reward
  **visible, physical, multi-hardware payoffs** (a robot moving) over a screen-only demo. We should make sure
  our demo has an equally undeniable physical payoff (lights flickering, speaker actually talking, a real
  person's phone actually buzzing) rather than a dashboard.
- Also worth noting for scoring calibration: Qualcomm gives the winning team **direct engineering
  collaboration + featured blog/livestream** as a prize — i.e. they're evaluating "would we want to keep
  building this," which rewards production-plausible packaging (matches the 20-pt Deployment criterion).

---

## 6. Qualcomm Edge AI Developer Hackathon — Korea instance (Feb 2026) & Bengaluru instance (June 2025)

Same Qualcomm Edge-AI hackathon franchise, different city. Five Korea award winners, all **on-device,
NPU-targeted, using named quantized open models** — this is the calibration bar for the "Technical
Implementation" 40-pt criterion at Qualcomm-run events specifically:
- **E.M.Pilot** — local email client; YOLOv8 detection + Qwen2-7B-Instruct + EasyOCR + Nomic-Embed-Text,
  Tauri/React front end, Flask/Transformers back end, runs on Snapdragon X NPU.
- **File Fairy** — semantic file search/organizer; Qwen3-4B + Nomic embeddings + LanceDB vector DB.
- **emerGen** — voice/text emergency-response assistant; Whisper-Base-En for STT, Llama-3.2-3B-Instruct
  fine-tuned, vector-DB case retrieval for disaster guidance. Directly adjacent to our emergency-escalation
  tool-call.
- **Medly** — real-time medical-speech simplifier; live captioning + Tesseract OCR + biomedical NER model
  + **Qwen2.5-7B-Instruct via Qualcomm QNN** on a Snapdragon X Elite / Hexagon NPU, with explicit hardware
  specs quoted (X1E-80-100, 16GB LPDDR5X) — judges/write-ups liked precise hardware+model naming.
- **MyStoryPal** — kids' collaborative storytelling app; Llama-3.2-3B-Instruct + Stable Diffusion 2.1 +
  CLIP, generates an illustration every few sentences, gives live grammar feedback — a **kids + generative
  content + on-device** pattern adjacent to our "kid monitoring" use case, but for creative co-writing, not
  safety.
- **Shortlisted (not winning) — "Famigo AI"**: family assistant with **voice interface + memory sharing**
  across family members. This is close to our territory (family + voice + shared context) and only made
  the shortlist, not the win — suggests a bare "family voice assistant" framing alone is not enough to win
  this style of event; it needs a sharper hook (ours: semantic-event privacy architecture + emergency
  response + parent's own cloned voice).
- Separately, there's a **real IEEE paper, "Famigo: A Privacy-Preserving Hybrid Voice Assistant for
  Multi-User Family Environments"**, using on-device voice ID + cloud RAG with a parallel private/shared
  memory architecture, ~2-3s end-to-end latency. Not a hackathon project, but prior art we should
  differentiate from if judges know it: our angle is safety/intervention events, not memory-sharing.

**Bengaluru June 2025 instance**: press coverage mentions teams building "spontaneous gameplay commentary"
and "real-time posture coaching" LLM-on-edge apps — posture coaching from vision is again adjacent to our
fall-detection pose pipeline, reinforcing that vision-based body-pose coaching is a known-good pattern for
this specific hackathon franchise, but generic "coaching" alone (without multi-device orchestration) is
not enough to stand out — the RL/sim-to-real Dragverse winner needed the multi-device angle to actually win.

---

## 7. Alibaba Cloud Singapore AI Hackathon — BabyNoCry (1st prize)

An AI baby monitor combining **sound recognition + speech/sentiment analysis + video recognition**: detects
crying, alarms, or loud noise, sends parents an instant alert with the identified sound class, a transcript
of nearby conversation, sentiment analysis, and the actual audio clip.
- *Overdone-idea flag*: baby/child audio+video monitoring with cry/sound classification is now also a
  **commercial product category**, not just a hackathon novelty — Cubo Ai, Hubble Connected AI Vision,
  Maxi-Cosi See Pro 360°, Nanit, etc. already ship "AI interprets baby cries + sends video-based alerts" as
  a retail feature. If any part of our kid-monitoring pitch sounds like "we detect crying/noise and alert
  parents," judges may perceive it as commoditized. Our differentiator must be the **semantic-event,
  no-video-leaves-the-edge privacy stance** plus the **live two-way intervention in the parent's own cloned
  voice**, not the detection step itself.

---

## 8. Voice cloning for family members — devpost/grant landscape (is "speak in a family member's voice" already done?)

Searched extensively for prior hackathon projects doing voice cloning of a parent/child or deceased
relative. Findings:

- **VoiceKeep** (HackNC 2025) — clone a speaker's voice from a short recording, generate new speech from
  text, framed for "accessibility, education, storytelling, entertainment." Built end-to-end (record →
  transcribe → clone) in under 36 hours using the **ElevenLabs API** directly (no custom voice model work).
  No prize info found; no visible consent/permission flow described on its Devpost page — this is a gap our
  entry can explicitly do better on (consent-first framing scores on both Innovation/UX and reduces
  ethical-risk optics with judges).
- **VoiceTree** — pitched as letting you "clone and preserve the voice of family members" to build a
  living archive/story-telling record — explicitly framed around the fact that people have thousands of
  photos of loved ones but almost no voice recordings.
- **Living Forever AI** (ElevenLabs Grants Program recipient, not a single hackathon but same ecosystem) —
  "interactive family legacy platform," captures **living people's voices with full explicit consent** so
  families can revisit their stories across generations; won a grant (33M voice-generation credits + 12mo
  subscription) specifically because of its consent-and-legacy framing, not just the cloning tech.
- None of the projects found do **live, synchronous, two-way remote intervention** where a parent (or
  caregiver) *actively, in real time, speaks through the home system in their own cloned voice* to a family
  member who isn't currently reachable by phone. Everything found is either (a) archival/nostalgic
  (preserve a voice for later/after death) or (b) simple clone-and-generate demo tooling. **This means "the
  system can speak in the parent's cloned voice, live, to intervene while they're in a meeting" is a
  genuinely underexplored angle in the hackathon corpus we could find** — it's a stronger, less-derivative
  hook than we'd assumed, provided we lead with consent and keep the parent "in the loop" (texting the
  system, approving the phrase, or at minimum registering ahead of time) rather than fully autonomous
  puppeteering.
- **Ethical backlash context we must actively avoid resembling**: griefbots/deadbots (HereAfter AI,
  StoryFile, DeepBrain AI "Re;memory," Amazon Alexa's "voices of deceased family members" feature) have
  drawn public criticism — most visibly Zelda Williams publicly condemning AI recreations of her father
  Robin Williams's voice/likeness as "over-processed hot dogs out of the lives of human beings" (Oct 2025).
  There's also an active wave of lawsuits (Social Media Victims Law Center / Tech Justice Law Project vs.
  OpenAI, Nov 2025) over chatbot psychological harm to minors. **For judges who are AI-industry-savvy,
  "parent's voice, with consent, while alive and available" must be pitched crisply as categorically
  different from deadbots/companion-chatbots** — living person, explicit opt-in enrollment, revocable,
  used only for a specific safety/reassurance/discipline moment, full transcript logged for the parent to
  review. State this distinction in the pitch itself; don't make judges infer it.

---

## 9. Voice AI Symposium & Hackathon (clinical, published Frontiers in Digital Health, 2025/2026)

An academic/clinical voice-AI hackathon+symposium. Six themes, most relevant to us:
- **Voice as a multimodal biomarker**: voice paired with other physiological signals (not just transcribed
  words) — same "voice carries more than semantic content" thesis DispatchAI/Hume demonstrate.
- **Consent granularity for ambient/always-listening capture**: explicit concern about "continuous voice
  capture," "secondary data use," "speaker identifiability," "power asymmetries" — directly applicable
  language for how we should describe QNet Home's privacy design (semantic-events-only, no raw audio/video
  leaving the edge node, explicit enrollment for voice cloning) in our own docs/pitch to preempt judge
  concerns about an always-on home listening system.

---

## Overdone / commoditized ideas to explicitly avoid leaning on

1. **Fall detection via pose/vision alone** — a GitHub-topic-scale commodity (dozens of open repos,
   academic papers, and a "Fall Detector AI" hackathon project already exists). Detection itself will not
   impress judges; the *response/orchestration* layer must be the star.
2. **Baby/child cry or noise detection with alerting** — already a shipping retail product category
   (Cubo Ai, Hubble, Maxi-Cosi, Nanit). Don't pitch "we detect crying/loud sounds," pitch what happens next
   and how privately.
3. **Generic "voice assistant for the home / home security voice agent"** (Voice Guardian, Espresso Labs,
   plain conversational companions) — many hackathon teams build a bare conversational agent with no
   hardware/systems differentiation; without our multi-device/edge-privacy story this collapses into a
   crowded bucket.
4. **Deceased/legacy voice cloning ("griefbot")** — real ethical backlash risk (Zelda Williams, lawsuits).
   Avoid any framing that could be read this way; always anchor to *living, consenting, present* family
   members.
5. **Plain family memory-sharing voice assistants** (Famigo AI, the Famigo IEEE paper) — only reached
   "shortlist," not a win, at the one hackathon we found it in. A family-voice-assistant frame alone is not
   enough; needs the safety-event + escalation + cloned-voice-intervention layer to stand out.

---

## Top ideas for QNet Home from this domain (ranked)

1. **Fuse vocal emotion/prosody with semantic vision events, and say so explicitly.** DispatchAI (Hume EVI)
   and the mila/Violet Hume projects prove judges reward using *how* something is said (distress, calm,
   panic) as a triage signal, not just *what* was said or seen. Add a lightweight on-device prosody/emotion
   classifier to the two-way "Are you OK?" conversation so escalation severity is driven by vision event +
   voice tone + conversational content together — a concrete extra modality of "fusion" for the 40-pt
   Technical criterion.
2. **Lead the pitch with the "live, consenting, present parent" distinction, not just "voice cloning."**
   No hackathon project we found does synchronous remote intervention in a living parent's cloned voice;
   frame it explicitly against deadbot/griefbot backlash (Zelda Williams, OpenAI-minor-harm lawsuits) and
   clinical-hackathon consent language (granular, revocable, logged) to convert an ethics risk into a
   scored strength on Innovation/UX and de-risk judge pushback.
3. **Copy DispatchAI's "human-in-the-loop + one big quantified latency number" pattern.** Report a hard
   before/after number for NPU-offloaded inference on the Copilot+ PC (e.g., time-to-first-spoken-response,
   or edge-event-to-agent-decision latency, CPU vs Hexagon NPU) — this exact rhetorical move (a startling
   percentage reduction, credited to on-device acceleration) won UC Berkeley's grand prize.
4. **Give the demo an undeniable physical payoff, following the "Dragverse" pattern that won a past
   Snapdragon Multiverse Hackathon.** That event's actual past winner ended with a *real robot moving*, not
   a dashboard. Make sure our demo climax is physical and visible: lights actually flicker, the room speaker
   actually talks, a phone actually buzzes with a caregiver alert — avoid a screen-only finale.
5. **Explicitly map our system onto this hackathon's own listed tracks** (Real-time CV Assistant +
   Conversational AI Companion, per the Princeton rules) in the pitch deck's first slide — we're not a
   single-track entry, we cover both, plus multi-device orchestration, which past organizers have said is
   the actual theme ("how systems work together").
6. **Steal GibberLink's demo trick for a secondary "wow" beat, not the core architecture.** Consider a
   quick, audible ggwave-style acoustic handshake demo between the two Arduino UNO Q edge nodes (or edge
   node → PC) as a low-bandwidth/offline-fallback channel — a 10-second "listen to the devices talk to each
   other" moment is cheap to build and highly memorable, mirroring what made GibberLink go viral.
7. **Use precise on-device model/hardware naming in every slide, matching the Qualcomm-hackathon
   calibration bar** (Korea instance): name the exact quantized model + runtime (e.g., "Llama/Qwen via
   Qualcomm QNN on Hexagon NPU," "Whisper-base for on-device STT") rather than saying "a local LLM" —
   Qualcomm-run hackathons visibly reward specificity here.
8. **Don't pitch child-monitoring as "we detect crying/loud sounds/danger"** — that's commodity (BabyNoCry,
   Cubo Ai, Hubble, Nanit already ship it). Pitch the *event-to-privacy-preserving-response* pipeline and
   the parent's-voice intervention as the novel layer.
9. **Consider structuring the caregiver-facing side like Dealty/AssemblyAI's pattern**: turn the live
   "Are you OK?" conversation into a structured, timestamped incident summary (transcript + emotion +
   vision-event tags) delivered to the caregiver — reuses a proven "real-time STT → structured record"
   hackathon-winning pattern for our notification/logging tool-call.
10. **Track record: this exact Qualcomm hackathon has multiple prior instances (Princeton, Noida/Jalandhar,
    Bengaluru) with an official rules PDF hosted by MIT CSAIL** (`cap.csail.mit.edu`) — worth having a
    teammate skim that PDF directly for the literal scoring rubric text if time allows, since our fetch
    only got the public event page, not the full rules document.

---

## Sources

- [ElevenLabs Worldwide Hackathon — Devpost](https://elevenlabs-worldwide-hackathon.devpost.com/)
- [Announcing the winners of the ElevenLabs Worldwide Hackathon](https://elevenlabs.io/blog/announcing-the-winners-of-the-elevenlabs-worldwide-hackathon)
- [Gibberlink: Two AI voice assistants have a conversation — ElevenLabs blog](https://elevenlabs.io/blog/what-happens-when-two-ai-voice-assistants-have-a-conversation)
- [GibberLink GitHub (PennyroyalTea)](https://github.com/PennyroyalTea/gibberlink)
- [Gibberlink — Wikipedia](https://en.wikipedia.org/wiki/Gibberlink)
- [We Should All Do What ElevenLabs Did With Its VoiceAI Hackathon — ShiftMag](https://shiftmag.dev/we-should-all-do-what-elevenlabs-did-with-its-voiceai-hackathon-7326/)
- [RoadMate — Devpost](https://devpost.com/software/roadmate-t28eqk)
- [What I learned attending my first ever hackathon — PostHog](https://posthog.com/blog/elevenlabs-hackathon)
- [Living Forever AI awarded ElevenLabs grant — Barchart](https://www.barchart.com/story/news/783627/living-forever-ai-awarded-elevenlabs-grant-accelerating-voice-powered-legacy-platform-for-thousands-of-families)
- [VoiceKeep — Devpost](https://devpost.com/software/voicekeep)
- [Top Speech AI projects and winners at 2024 AssemblyAI Hackathon](https://www.assemblyai.com/blog/top-speech-ai-projects-and-winners-at-2024-assemblyai-hackathon)
- [DispatchAI — GitHub (IdkwhatImD0ing)](https://github.com/IdkwhatImD0ing/DispatchAI)
- [UC Berkeley AI Hackathon 2024: 36 Hours of Hacking for Good — Medium](https://carolinewinnett.medium.com/uc-berkeley-ai-hackathon-2024-36-hours-of-hacking-for-good-c18068cd842d)
- [Innovation with Impact: UC Berkeley AI Hackathon 2024 — Intersog](https://intersog.com/blog/strategy/uc-berkeley-ai-hackathon-2024/)
- [Hume Powers Projects at UC Berkeley LLM Hackathon — Hume AI blog](https://www.hume.ai/blog/hume-powers-projects-at-uc-berkeley-llm-hackathon)
- [Snapdragon Multiverse Hackathon — Princeton (Qualcomm)](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-princeton)
- [Snapdragon Multiverse Hackathon — Bangalore (Qualcomm)](https://www.qualcomm.com/developer/events/snapdragon-multiverse-hackathon-bangalore)
- [Snapdragon Multiverse Hackathon — MIT CSAIL](https://www.csail.mit.edu/event/snapdragon-multiverse-hackathon)
- [Official Rules PDF — Snapdragon Multiverse Hackathon at MIT (CSAIL)](https://cap.csail.mit.edu/sites/default/files/resource-pdfs/official-rules-snapdragon-multiverse-hackathon_mit.pdf)
- [Team led by city youth emerges winner at Qualcomm hackathon — Tribune India (Dragverse)](https://www.tribuneindia.com/news/jalandhar/team-led-by-city-youth-emerges-winner-at-qualcomm-hackathon/)
- [On-device AI hackathon in Korea: winners and highlights — Qualcomm developer blog](https://www.qualcomm.com/developer/blog/2026/02/on-device-ai-developers-korea)
- [Qualcomm India Launches Global Edge AI Developer Hackathon Series — PR Newswire](https://www.prnewswire.com/in/news-releases/qualcomm-india-launches-global-edge-ai-developer-hackathon-series-302466732.html)
- [Famigo: A Privacy-Preserving Hybrid Voice Assistant for Multi-User Family Environments — IEEE Xplore](https://ieeexplore.ieee.org/document/11385934/)
- [BabyNoCry: An Innovative AI Baby Monitor — Alibaba Cloud Community](https://www.alibabacloud.com/blog/babynocry-an-innovative-ai-baby-monitor_600946)
- [Digital Doppelgangers: Ethical and Societal Implications of Pre-Mortem AI Clones — arXiv](https://arxiv.org/html/2502.21248v1)
- [Griefbots, Deadbots, Postmortem Avatars — Philosophy & Technology, Springer](https://link.springer.com/article/10.1007/s13347-024-00744-w)
- [Zelda Williams condemns AI puppeteering of Robin Williams — coverage via financialcontent.com](https://markets.financialcontent.com/ms.intelvalue/article/tokenring-2025-10-7-zelda-williams-condemns-ai-puppeteering-of-robin-williams-igniting-fierce-ethical-debate-on-digital-immortality)
- [Translating AI research into reality: summary of the 2025 Voice AI Symposium and Hackathon — Frontiers in Digital Health](https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2026.1754426/full)
