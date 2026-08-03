# Offline Knowledge Skill Packs — How Small Is "All of First Aid", and What Else Fits the Pattern

*Research date: 2026-08-03. All corpus sizes below were **measured on this machine** (sources downloaded to `corpus_tmp/`, gitignored; text extracted with pypdf; tokens estimated at 4 chars/token). The prototype pack in `skills/emergency/` was measured after writing. Nothing here is a guess except where marked ~.*

---

## 1. TL;DR

**The entire authoritative lay-rescuer first-aid corpus is ~2.5 MB of text (~650k tokens). A distilled scenario skill is ~2.5 KB (~600 tokens). Both are rounding errors next to our ~4 GB of bundled model weights — so QNet Home ships its emergency brain offline, whole, for free.**

The hypothesis this validates: emergency-response knowledge is small because it is *engineered* to be small. AHA/IFRC/Red Cross design lay protocols to be teachable in a half-day course and recallable by a panicked bystander — 5–10 steps, unambiguous branches. The compressibility is a design goal of the domain, not luck. Corollary meta-heuristic: **anything taught to laypeople in a short course compresses to kilobytes** — which generalizes well beyond first aid (§5).

Deliverable shipped alongside this doc: `skills/emergency/` — 6 scenario skills + README, **16.4 KB total**, wired conceptually to the existing state-machine rule (machine picks the skill, LLM phrases it). Demo tie-in: the router-unplug beat now covers *knowledge*, not just detection — "no cloud, no web search, and it still knows what to do."

---

## 2. Measured corpus sizes

| Source (downloaded 2026-08-03) | Pages | PDF size | Extracted text | ~Tokens |
|---|---|---|---|---|
| IFRC International First Aid, Resuscitation, and Education Guidelines 2020 — *the* global authority | 476 | 4.23 MB | **1.37 MB** (216,901 words) | ~359k |
| AHA 2020 Guidelines Highlights for CPR and ECC | 32 | 9.69 MB | **75 KB** (10,733 words) | ~19k |
| *Where There Is No Doctor* (Hesperian, 2011 ed.) — the classic offline medical manual, copyright-released for digital distribution | 503 | 14.15 MB | **1.03 MB** (183,113 words) | ~270k |
| **Total: 1,011 pages of authoritative sources** | | 28 MB | **2.47 MB** | **~648k** |
| ready.gov disaster pages (earthquake, flood, fire, tornado, power outage) | 5 pages | — | **~7 KB each** | ~1.7–2.7k each |

Observations:
- **PDF size is a lie** — it's 91% images and layout. The 9.69 MB AHA PDF contains 75 KB of text. Measure text, not files.
- The IFRC 2020 guidelines — literally the global reference for everything first aid — fit in ~359k tokens. That is *smaller than this project's research folder* (~1.8M tokens per PROGRESS.md).
- One ready.gov hazard page ≈ 2k tokens ≈ half a skill pack. A full disaster-prep pack (all ~30 ready.gov hazards) would be ~60k tokens / ~250 KB.
- Note: the 2025 edition of the IFRC guidelines exists ([ifrc.org](https://www.ifrc.org/document/ifrc-international-first-aid-resuscitation-and-education-guidelines-2025)); 2020 was used because its PDF is freely fetchable. For a real product, rebuild from 2025.

## 3. Measured prototype pack (`skills/emergency/`)

| Skill | Size | ~Tokens |
|---|---|---|
| fall-no-response | 2.5 KB | 644 |
| fall-responsive (the "I'm fine" + safe get-up path) | 2.3 KB | 581 |
| unresponsive-not-breathing-cpr (hands-only CPR coaching + metronome) | 2.5 KB | 631 |
| unresponsive-breathing (recovery position) | 2.2 KB | 557 |
| faint-syncope | 2.2 KB | 555 |
| choking | 2.4 KB | 614 |
| README (format spec + routing table) | 2.4 KB | 613 |
| **Pack total** | **16.4 KB** | **~4.2k** |

Every skill fits in a Qwen3-1.7B triage context with >80% of the window to spare. At 23 tok/s on the 4B, loading a whole skill costs nothing (it's prompt, not generation). **No RAG, no embeddings on the hot path** — the state machine maps event type → filename directly; retrieval infrastructure would be over-engineering at this corpus size.

## 4. Why this works — and the three real caveats

**Selection, not storage, was always the hard problem.** The bytes are trivial; picking the *right* protocol from an ambiguous situation is where the risk lives. Our existing reliability rule already solves this: the deterministic state machine picks the skill (fall + no reply → `fall-no-response.md`), the LLM only phrases it — small models are 87.9% reliable single-turn but 22% multi-turn, so the branching lives in the skill's explicit decision tree, stepped through by the machine, never free-styled.

1. **Structure beats prose.** Skills are numbered steps with explicit `[[branch]]` targets (same reason aviation uses QRH checklists). A 4B model paraphrasing one step at a time cannot reorder a protocol it never holds loosely.
2. **Localization is one config field.** Emergency numbers (911/112/999) and minor protocol variants are frontmatter (`region`, `emergency_number`), substituted at load time. Not a size problem.
3. **Versioning is provenance.** Guidelines revise on ~5-year ILCOR cycles; every skill carries `source`/`version`/`retrieved` frontmatter and the pack must be rebuildable from cited sources. LLM-distilled content requires a human review pass against the sources before demo claims (Day-4 checklist item).

Liability framing (for the deck, and it's true): the system **relays established lay-rescuer guidance and escalates to humans first** — the same content taught in a public first-aid course, never a diagnosis. Not a medical device.

## 5. The general technique — "small-corpus offline packs"

A domain qualifies when its knowledge is: **(a)** procedural/checklist-shaped, **(b)** standardized by an authority, **(c)** slow-changing, **(d)** high-stakes but low-frequency, **(e)** designed for laypeople under stress. Property (d) is the kicker for QNet specifically: **the network is most likely to be down exactly when these skills fire** (fire, storm, power outage) — offline isn't a nice-to-have for emergency knowledge, it's the requirement.

Qualifying domains, each pack plausibly < 250 KB (per the measured ready.gov and skill-pack data points):

| Domain | Authority/source | QNet relevance |
|---|---|---|
| Disaster response (earthquake/fire/flood/tornado) | FEMA/ready.gov (~2k tokens/hazard, measured) | natural "sensing skill" siblings (smoke-alarm relay is already in IDEAS.md §C) |
| Home hazards (gas leak, CO, water/electrical shutoff) | ready.gov, NFPA | pairs with CO-alarm relay skill |
| Poison-control quick reference | Poison Help / AAPCC | kid scenario adjacency |
| Infant/child emergencies + dosing | AHA pediatric BLS, AAP | kid-room nodes |
| Mental-health crisis de-escalation | 988 Lifeline protocols | vocal-emotion triage (COULD) adjacency |
| House-specific knowledge (breaker location, water shutoff, med schedule) | generated at setup wizard | **same precedent as the cloned-voice phrase bank** — pre-generate at consent/setup time |
| Ops runbooks | (the IT analogue — runbooks already ARE this pattern) | how to explain the idea to engineer judges in one sentence |

**Anti-pattern (does NOT fit):** open-ended diagnosis, fast-changing info (news, prices, recalls), long-tail Q&A, anything needing personalization beyond a config field. The moment you want retrieval-quality ranking over megabytes, you've left this technique — that's what the Ask-the-House embedding memory (IDEAS.md §A) is for, and the two compose: *packs for procedures, embeddings for the home's own history*.

## 6. Rubric tie-in

- **Innovation (25):** every eldercare competitor is alert-only; we not only speak, we *coach* — CPR metronome, recovery-position steps, safe get-up — fully offline. No prior art in the competitor scan does guidance.
- **Technical (40):** "1,011 pages of authoritative guidance = 2.5 MB text; our distilled pack = 16.4 KB; skill fits in the 1.7B triage context" is exactly the kind of measured, counter-intuitive number the judging culture rewards (like fp32-beats-int8).
- **Demo:** extends the router-unplug beat — after re-running fall detection offline, Herald *walks a bystander through the response* offline.
- **Cost:** content is already written; Guardian integration is a filename lookup in the state machine (~1–2 h, optional before freeze).

## Sources

- [IFRC International First Aid, Resuscitation, and Education Guidelines 2020 (PDF)](https://www.ifrc.org/sites/default/files/2022-02/EN_GFARC_GUIDELINES_2020.pdf) · [2025 edition](https://www.ifrc.org/document/ifrc-international-first-aid-resuscitation-and-education-guidelines-2025)
- [AHA Highlights of the 2020 Guidelines for CPR and ECC (PDF)](https://cpr.heart.org/-/media/CPR-Files/CPR-Guidelines-Files/Highlights/Hghlghts_2020_ECC_Guidelines_English.pdf)
- [Where There Is No Doctor — Hesperian](https://store.hesperian.org/products/where-there-is-no-doctor) (measured from the copyright-released 2011 mirror)
- [ready.gov](https://www.ready.gov/) hazard pages · CDC STEADI "What to do when you fall"
