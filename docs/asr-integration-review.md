# `asr-tts-mqtt` branch — integration review

> **Resolution (2026-08-06):** integrated per this review on branch
> `voice-integration` — extraction (never merged), all five blockers fixed
> test-driven (B1 wake gate wired node-side, B2 contract conformance with our
> frozen fixtures, B3 reliability trio), everything AGPL. Live plan and phase
> tracking: `docs/voice-integration-plan.md`. Device phases (her stack
> retirement, second Ventuno, in-room gates) pending hardware access.

*2026-08-06. Three independent review passes (voice-node internals · wire-contract
compatibility · overlap/runtime-collision inventory) over commit `70700bd`,
before any integration. Verdict up front: **integrate — it's worth it — but by
extraction, never by merge**, and three small blockers must land first, two of
them hers.*

## The verdict

The branch is a **parallel mini-implementation of the whole system** grown from
the original design snapshot: its own agent, its own MQTT contract dialect, its
own broker deployment (the very stack that has been holding `:1883` on the IQ9),
its own docs. Almost all of that duplicates — in older, smaller form — what
production already runs, and a naive `git merge` produces **13 add/add conflicts
on production-critical files** (frozen contract, broker config, docs) while
silently importing a second agent and a second broker. Never merge it.

The **prize inside is real**: `apps/ventuno-q/qhome-voice-node/` — the voice
node production has never had (`qnet/node/voice.py` is still a
`NotImplementedError` stub). Her half-duplex audio core is genuinely
well-engineered — better than DESIGN §9's pseudocode assumed possible — and the
ASR is **Whisper Small compiled to QNN, executing on the Ventuno's Hexagon NPU**,
which is exactly the story this project wants to tell.

## Speech requirements scorecard (DESIGN §9, verified with file/line evidence; her 22 unit tests executed — 22 pass)

| Req | Verdict |
|---|---|
| R1 never capture while playing | ✅ satisfied — single-threaded audio loop, cancelled-generation discard, sync TTS + 500 ms guard, tested |
| R2 playback completion knowable | ✅ satisfied — `tts.speak` blocks until PCM written |
| R3 service-side VAD endpointing | ✅ satisfied — runner-side VAD (700 ms) |
| R4 bounded listen, honest silence | ✅ satisfied — 15 s session listen, `silence == (text=="")` enforced, errors ≠ silence |
| R5 all local | ⚠️ partial — inference is on-device, but idle ambient speech is published off-node and INFO-logged (see Blocker 1) |
| R6 listen cancellation | ✅ satisfied — cancel + generation tags + startup-race watchdog |

Also verified compliant as-is: responder-phrase precedence (checked before
anything is published, both paths), silence semantics, client-id scheme (no
eviction collisions with any of our services), MQTT reconnect + LWT.

## Blockers (must land before her node ever connects to our broker)

| # | Finding | Owner |
|---|---|---|
| B1 | **Wake gate is dead code — ungated ambient speech is published.** `wake_gate.py` is correct and imported by *nothing but its own unit test*; the idle path publishes every 10 s rolling transcript raw as `ask kind=query`. This is deliberate in her design ("IQ9 owns activation") — but her IQ9 has no LLM, our contract puts the gate node-side, and this exact behavior flooded our agent live ("60 junk sessions", garbage find sessions off room chatter — her `bedroom` room id passes our rooms filter). Fix ≈10 lines: call `extract_wake_request` in `_listen_continuously`, publish only the stripped remainder of the final (not the rolling window), stop logging transcript content. | **HERS to sign off** (reverses her documented contract + 3–4 of her tests); we can write it |
| B2 | **Her node rejects everything our agent sends.** Her `say` validator requires `id/ts/room` (we send `{text, prio}`) and rejects `prio:"routine"` → nothing would ever be spoken. Her session-snapshot parser raises on our shape → node never knows a fall session is live → never listens → never publishes `heard` → every fall escalates on pure silence. Fixes are small validator relaxations (`message_schema.py`), only `id/room/state` actually needed from sessions. | **HERS** (our contract is frozen; 5 consumers implement it) |
| B3 | **Retire her IQ9 stack before co-existence.** `iq9_native` (embedded broker :1883/:9001) + her router + her no-LLM agent triple-consume `qnet/+/ask` and would double-run fall response. Her own `deploy/iq9-native/stop.sh` is the safe, identity-checked kill. Retirement also frees the standard ports (see sequence). | **HERS, us coordinating** (it's her live demo) |
| B4 | **Ventuno RAM unmeasured.** Voice adds two App Lab containers + fp16 whisper-small (~0.7–1.2 GiB est.) on a board at ~12/14 GiB (VLM container + vision + stream). Likely fits, no margin. Measure first; fallbacks: her documented `whisper-small-quantized` (one-line rollback) or the second Ventuno board (her configs already assume two). | **US** |
| B5 | **License clash.** Her branch root `LICENSE` is MIT; her own file headers say `AGPL-3.0-only`; our repo is AGPL-3.0. Extract files under AGPL (headers already agree), never import her LICENSE file; she should fix the branch. | **HERS, trivial** |

## Glue (needed, none scary)

| Item | Owner |
|---|---|
| Node config per board: `iq9_host: 10.73.51.175` (one of her examples says `.100` — wrong), `mqtt_port: 11883` (then 1883 after switch-back), `room_id` = a key of our `rooms:` map. Pure config, zero code. | EITHER |
| Add `routine` to the node's `PRIORITY` map (accept unknown prios as lowest). | HERS |
| TTS-failure + dedupe interaction: a failed playback permanently consumes the message id, so a retried safety line dedupes into silence. Remember-on-success, or hub retries with fresh ids. | JOINT decision |
| No backoff on persistent ASR failure (4 Hz error spin + retained-status spam). | US can fix |
| `qnet/<room>/status` dialect clash (her retained LWT online/offline vs our vision heartbeat; `node_id` vs `node`; retained corpse makes the dashboard say "Camera online" for 15 s after page load). Unify or move her LWT to a subtopic. | EITHER |
| Port her voice tests + fakes into our pytest layout (drop her contract tests that assert literal LAN IPs and `listener 1883`). | US |
| >1024-char `say` is rejected, not truncated (long briefs). Truncate instead. | HERS |
| Text-length/dedupe niceties: add a ULID `id` to our `say` publishes so her dedupe/priority machinery works fully (additive, legal under both contracts). | US, trivial |

## Nice-to-have (not gating)

- Edit-distance wake tolerance ("hi home") — DESIGN §13 mentions it; her gate is exact-prefix.
- Resurrect her **broadcast/announce/replay** router logic as an agent tool (whole-home announcements — nice demo feature; the logic is clean, only its process form is obsolete).
- WebUI shows live ambient transcripts on an unauthenticated LAN page — post-gate, show only gated text.
- Publish-while-offline queueing on the node.
- `Speaker(shared=True)` — ask her if that weakens mic/speaker exclusivity.

## What to extract (and only this)

`apps/ventuno-q/qhome-voice-node/` (whole app) · `scripts/deploy_voice_node.sh` ·
`scripts/install_whisper_voice_ai_model.sh` · `contracts/arduino-speech.md` (→ our
`setup/`; it's a verified runbook incl. the whisper-medium failure post-mortem) ·
her voice tests + fakes (re-homed) · `judging/` content (see below) ·
`config/voice-nodes/*` + `qhome-config.example.json` (as the node's config format).
**Everything else stays behind** — her agent, router-as-service, embedded broker,
contract dialect, docs, README, LICENSE, deploy scripts.

## Integration sequence (nothing stops until step 2)

1. Extract + adapt in our tree (B1 gate wired, B2 validators, glue config); verify
   against our broker with her smoke script, port-fixed. Her live demo untouched.
2. **With her**: run her `stop.sh` on the IQ9 → embedded broker, router, her agent
   all stop; confirm 1883/9001 free.
3. **Switch-back to standard ports** per `infra/mosquitto.conf`'s own header:
   11883→1883, 19001→9001, board `house.local.yaml` edited in place, restart
   mosquitto + qnet-agent, journal must say `connected 127.0.0.1:1883`. (This also
   kills the wrong-broker foot-gun class — the agent's compiled default becomes
   correct.)
4. Re-point satellites: Ventuno units' `--port`, voice-node config, dashboard ws
   URL, DEMO.md pre-flight.
5. Deploy the voice node (App Lab) on the chosen board after the RAM measurement;
   decommission her leftover checkout on the IQ9 once she confirms.

## For the submission (from her `judging/` folder — salvage this regardless)

- **Repo link via the Microsoft Form by 1:00 PM Aug 7.**
- README must list team names + emails (ours does), open-source license (AGPL ✓),
  setup + run instructions (ours has them), packaged Windows .EXE/.MSIX for
  compute apps (`packaging/` ✓).
- Rubric: Technical 40 / Use-case 25 / Deployment 20 / Docs 15.
