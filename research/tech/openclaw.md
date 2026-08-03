# OpenClaw Deep-Dive — Is it the right orchestrator for QNet Home?

**Researched:** 2026-08-03 · **For:** Snapdragon Multiverse hackathon (submission Aug 7, 1pm)
**Verdict up front:** **Do not put OpenClaw on the critical path.** Build a lean custom Python orchestrator; integrate OpenClaw as a ~2-hour optional "ecosystem interop" flourish. Rationale in §11.

---

## 1. What OpenClaw is, as of Aug 2026

| Fact | Value |
|---|---|
| Repo | `github.com/openclaw/openclaw` (MIT, OpenClaw Foundation) |
| Tagline | "Your own personal AI assistant. Any OS. Any Platform. The lobster way. 🦞" |
| Scale | ~385,000 stars, ~80,900 forks, ~76,244 commits on main |
| Latest core release | **v2026.7.1**, published **2026-07-13** (3,063 contributions from 532 devs) |
| npm latest | `openclaw@2026.7.1-2`, description *"Multi-channel AI gateway with extensible messaging integrations"* |
| Node engines | `>=22.22.3 <23 \|\| >=24.15.0 <25 \|\| >=25.9.0` — docs recommend **Node 26** |
| Windows companion | `openclaw-windows-node` **v0.6.12**, published **2026-06-30** |
| Issue/PR numbering | ~#118,856 as of 2026-08-03 — i.e. enormous churn |

Lineage: Clawdbot → Moltbot → OpenClaw. It is *not* a coding-agent SDK; it is a **personal-assistant gateway** whose primary product surface is "talk to your agent from WhatsApp/Telegram/Slack/iMessage."

---

## 2. Architecture

**One Gateway daemon per host** = the control plane. Everything else is a client.

- Default bind: **`127.0.0.1:18789`** (loopback). Also serves HTTP (`/__openclaw__/canvas/`, `/__openclaw__/a2ui/`) on the same port.
- **Typed WebSocket API**, JSON-Schema-validated frames.
  - First frame **must** be `connect`; non-`connect`/non-JSON → hard close.
  - Requests: `{type:"req", id, method, params}` → `{type:"res", id, ok, payload|error}`
  - Events: `{type:"event", event, payload, seq?, stateVersion?}`
  - Domain event streams: `agent`, `chat`, `presence`, `health`, `heartbeat`, `cron`
  - Events are **not replayed** — clients must refresh on gaps. Idempotency keys required for `send` and `agent`.
- Three client classes:
  1. **Control plane** — CLI, TUI, Control UI (browser), macOS app, automations. Methods: `health`, `status`, `send`, `agent`, `system-presence`.
  2. **Nodes** — `role: "node"` devices (macOS/iOS/watchOS/Android/Windows/headless Linux) that expose device commands (`canvas.*`, `camera.*`, `screen.record`, `location.get`, `system.notify`, `system.run`).
  3. **WebChat** — static UI over the same WS API.
- **Channels** owned by the Gateway: WhatsApp (Baileys — exactly one session per host), Telegram, Slack, Discord, Signal, iMessage, Google Chat, Matrix, Teams, LINE, Mattermost, Feishu (+ ~15 more as external plugins).
- Persistence: SQLite (`kysely`), sessions/transcripts serialized through per-session write lanes.

**Agent loop** (`/concepts/agent-loop`): 5 stages — *intake → context assembly → model inference → tool execution → streaming → persistence*. `req:agent` returns a `runId` immediately with `{status:"accepted"}`; progress arrives as streamed `event:agent`. Runs are **serialized per session key** (session lane). Auto-compaction emits `compaction` events and can trigger a retry. Default agent budget **48h** (configurable); provider idle watchdogs 120s cloud / 300s self-hosted.

---

## 3. SKILLS system — how to add capability

A **skill is a markdown instruction file** (`SKILL.md`) with YAML frontmatter, in a directory. Skills teach the model *when and how* to use tools; they do **not** themselves execute code.

Discovery precedence (highest wins on name collision):
1. `<workspace>/skills` → 2. `<workspace>/.agents/skills` → 3. `~/.agents/skills` → 4. `<state-dir>/skills` → 5. bundled → 6. `skills.load.extraDirs` + plugin skills

Grouped layouts up to 6 levels deep; folder path is organizational only, name comes from frontmatter.

### Example SKILL.md (verbatim shape from docs)

```markdown
---
name: data-processor
description: Process CSV and JSON files with validation and transformation
metadata:
  {
    "openclaw":
      {
        "emoji": "📊",
        "requires": { "bins": ["jq"], "env": ["PROCESSOR_API_KEY"] },
        "primaryEnv": "PROCESSOR_API_KEY",
        "install": [
          { "id": "brew", "kind": "brew", "formula": "jq", "bins": ["jq"], "label": "Install jq (brew)" }
        ]
      }
  }
---

# Data Processor Skill

When users ask to process structured data files, use the `process_file` tool...
Use `{baseDir}` to reference files within this skill's directory.
```

**Frontmatter fields**
- Required: `name`, `description`
- Visibility: `user-invocable` (default true → exposed as slash command), `disable-model-invocation` (hide from model prompt, keep slash command)
- Direct dispatch: `command-dispatch: tool`, `command-tool: <toolName>`, `command-arg-mode: "raw"` → **bypasses the model entirely and calls a tool** (useful for deterministic actions)
- `metadata.openclaw`: `requires.bins` / `requires.anyBins` / `requires.env` / `requires.config`, `os: ["darwin","linux","win32"]`, `install[]`, `emoji`, `homepage`

**Gating** happens in 3 stages: dependency gating (bins/env/config/os) → per-agent allowlists (`agents.defaults.skills`, `agents.list[].skills`) → config overrides (`skills.entries.<id>.enabled`).

**Token cost is documented and deterministic:** a compact XML block in the system prompt, ~97 chars per skill before field lengths ≈ **~24 tokens/skill**. `skills.limits.maxSkillsPromptChars` truncates descriptions first, then omits them.

**Snapshotting:** eligible skills are snapshotted **at session start** and reused for all turns in that session. Mid-session refresh only on `SKILL.md` watcher change or a new remote node connecting. *→ Config/skill changes need a new session. Expect confusion during a hackathon demo.*

### Skills vs Tools vs Plugins
- **Skill** = markdown instructions (prompt-level).
- **Tool** = the actual executable function the model calls.
- **Plugin** = a package that can ship tools *and* skills, register channels, model providers, agent harnesses, speech/TTS, realtime transcription, media understanding, web fetch/search, and typed lifecycle hooks.

### Plugin system (this is how you add real tools)
Manifest: `openclaw.plugin.json` + an in-process runtime module. Also accepts **Codex / Claude / Cursor plugin layouts** mapped into its inventory.

```json5
{
  plugins: {
    enabled: true,
    allow: ["voice-call"],
    deny: ["untrusted-plugin"],
    load: { paths: ["~/Projects/oss/voice-call-plugin"] },
    slots: { memory: "memory-core" },
    entries: { "voice-call": { enabled: true, config: { provider: "twilio" } } },
  },
}
```

Dev loading: `openclaw plugins install --link ./my-plugin`.
Hook APIs: `api.on(...)` (preferred typed lifecycle hooks — middleware, policy, message rewriting, prompt shaping, tool control) and `api.registerHook(...)` (coarse command/lifecycle side effects).

**Plugin inventory (147 total):** 54 bundled in the npm package + 91 official external + 2 source-only.
- Local model: `ollama`, `lmstudio`, `vllm`, `sglang`, `litellm`, and external `llama-cpp` (local GGUF text inference + memory embeddings)
- Speech/TTS: `azure-speech`, `elevenlabs`, `microsoft`, `tts-local-cli`, plus external `fish-audio`, `gradium`, `inworld`, `deepgram`, `senseaudio`
- Automation: `webhooks`, `policy`, `admin-http-rpc`, `bonjour`, `file-transfer`
- Nodes: `linux-node`, `linux-canvas`, `canvas`, `cua-computer`
- **No Home Assistant, no MQTT, no Zigbee/Matter/Z-Wave plugin exists.** ClawHub (`clawhub.ai`, the public registry; `openclaw skills search`, `openclaw plugins install clawhub:<pkg>`) surfaced nothing home-automation in the inventory either.

---

## 4. MCP support

- **MCP client: yes, first-class.** Transports: **stdio**, **SSE**, **streamable-http**. Ships `@modelcontextprotocol/sdk@1.29.0`.
- **MCP server: yes** — `openclaw mcp serve` exposes OpenClaw channel conversations to other MCP clients. Separately, the **Windows Hub can expose Windows device capabilities as a local MCP server on loopback *without a running Gateway***, drivable from Claude Desktop / Claude Code / Cursor.

```json5
{
  mcp: {
    servers: {
      docs: {
        url: "https://mcp.example.com/mcp",
        transport: "streamable-http",
        enabled: true,
        connectionTimeoutMs: 5000,
        requestTimeoutMs: 20000,
        toolFilter: { include: ["search", "read_*"] },
      },
    },
  },
}
```

For stdio, replace `url`/`transport` with `command` + `args`. MCP tools are still subject to tool-profile/tool-policy — "connecting a server does not bypass your policy." No documented tool-count cap.

> **This is the cleanest integration seam for us:** wrap our Python/GStreamer/device tools as one MCP stdio server and OpenClaw picks them all up without writing any TypeScript.

---

## 5. Model backends

Hosted: Anthropic, OpenAI, Google, xAI, Mistral, DeepSeek, Cohere, Meta, Groq, Together, HuggingFace, NVIDIA, Alibaba, MiniMax, Amazon Bedrock, Microsoft Foundry, GitHub Copilot, OpenRouter, LiteLLM… (~60 provider plugins). Also a **`claude-cli` backend harness** (drives the Claude Code CLI as the agent) — see open issue #103231.

Local: **Ollama, LM Studio, vLLM, SGLang, MLX, llama.cpp (external plugin), LiteLLM, `inferrs`, `ds4`,** and any OpenAI-compatible gateway.

Config for an OpenAI-compatible local endpoint (verbatim from `/gateway/local-models`):

```json5
{
  models: {
    providers: {
      lmstudio: {
        baseUrl: "http://127.0.0.1:1234/v1",
        apiKey: "lmstudio",
        api: "openai-responses",
        models: [{
          id: "my-local-model",
          reasoning: false,
          contextWindow: 196608,
          maxTokens: 8192,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
        }]
      }
    }
  }
}
```

Use `api: "openai-completions"` unless the backend truly implements `/v1/responses`. Model refs are `"provider/model-id"`. Per-provider `timeoutSeconds` for slow servers.

### ⚠️ The single most important quote in this whole report

> **"Aim for 2+ maxed-out Mac Studios or an equivalent GPU rig (~$30k+)"** for comfortable local-model agent operation. A single 24GB GPU handles "lighter tasks at higher latency."

Plus:
- *"Small or aggressively quantized models truncate context and skip provider-side safety filters."*
- *"For tool-enabled agents or agents that read untrusted content, prompt-injection risk with older/smaller models is often too high… Do not run those workloads on weak model tiers."*
- Escape hatches that exist **because local tool calling breaks**: `localModelLean: true` ("if agent turns fail despite successful direct calls") and, as a last resort, `compat.supportsTools: false` — i.e. *turn tools off entirely*.
- Recommends `contextWindow: 196608` (192k) in its own example.

**Cross-checked against our own AI Hub cache** (`research/tech/_cache/`, Snapdragon X Elite CRD, w4a16 via `geniex_qairt`):

| Model | Decode tok/s | Prefill tok/s | TTFT min |
|---|---|---|---|
| Qwen3-1.7B (ctx 4096) | **42.2** | 618 | 52 ms |
| Qwen3-4B (ctx 4096) | **21.8** | 1310 | 98 ms |
| Qwen3-VL-4B-Instruct (ctx 4096) | **20.9** | 1280 | 100 ms |

(q4_0 llama.cpp on the same part is much worse: Qwen3-4B = 7.7 tok/s NPU / 10.6 CPU at ctx 4096.)

**Implication:** OpenClaw's own guidance and our silicon are two orders of magnitude apart. At 21.8 tok/s and a 4096-token context, OpenClaw's base system prompt + skills XML block + tool JSON schemas + session history will eat most of the window and every turn will be multi-second-to-tens-of-seconds. That is a direct hit on the **40-pt latency/performance criterion** — and the latency would be in *their* code, not ours.

---

## 6. Windows / Windows-on-ARM (Snapdragon X Elite)

**Three paths, all documented:**

1. **Windows Hub** (recommended by docs) — native WinUI companion, `openclaw-windows-node`. Windows 10 20H2+/11, requires WebView2 Runtime. **Signed ARM64 installer exists**: `OpenClawCompanion-Setup-arm64.exe` (104.8 MB) and portable `OpenClawTray-0.6.12-win-arm64.zip` (139.5 MB) in v0.6.12 (2026-06-30). Installs **without administrator privileges**. Still requires a running Gateway.
2. **Native Windows CLI** — `iwr -useb https://openclaw.ai/install.ps1 | iex`. Gateway runs as a managed Windows service via Scheduled Task or Startup folder item.
3. **WSL2** — `curl -fsSL https://openclaw.ai/install.sh | bash`. Docs say: *"WSL2 remains the most Linux-compatible Gateway runtime on Windows."*

**ARM64 reality check:**
- ✅ **Node.js publishes official `win-arm64` builds** for every version OpenClaw accepts (verified against `nodejs.org/dist/index.json`: v22.22.3 → v22.23.2, all v24.x/v25.x/v26.x have `win-arm64-zip`/`win-arm64-7z`). Latest: v26.6.0 and v24.19.0, both 2026-08-03.
- ✅ Core npm deps are largely pure-JS: `express@5.2.1`, `kysely@0.29.2`, `grammy`, provider SDKs. SQLite appears to go through `node:sqlite` (built into Node 22.5+) rather than `better-sqlite3` — good news for ARM64, no native build needed.
- ⚠️ `sqlite-vec@0.1.9` is an **optionalDependency** (native) — used for memory/embedding vector search. win-arm64 prebuilds are the kind of thing that's routinely missing; being optional means it degrades rather than fails.
- ⚠️ `playwright-core@1.61.1` — the browser tool. Chromium-for-Windows-ARM64 support in Playwright is historically patchy. Don't plan on browser automation.
- ⚠️ **Talk mode is not listed for Windows.** `/nodes/talk` documents STT/TTS for macOS, iOS, Android and browsers only. The Windows *Hub* does have its own STT ("microphone transcription, opt-in") and TTS ("Windows speech synthesis, or ElevenLabs when configured" — i.e. SAPI/OneCore), so voice on Windows goes through the Hub, not through Talk mode.
- ✅ No open Windows-on-ARM issues found in the repo's issue search.

**Windows node default command allowlist:** camera, location, device (info/status), notifications, computer control. `system.run`/`system.which`/`browser.proxy`/`mcp.tools.call.v1`/`screen.snapshot` unlock after operator approves pairing. Privacy-sensitive commands (`camera.snap`, `camera.clip`, `screen.record`, `sms.send`, …) require persistent opt-in via `gateway.nodes.commands.allow`.

**Bottom line:** OpenClaw *will* run on a Snapdragon X Elite Copilot+ PC. Native install is plausible; WSL2 is the safe path but adds a whole Linux VM to your deployment story. Neither is a *packaged .EXE of our application*.

---

## 7. Proactive / scheduled / event-triggered actions — **the strongest reason to consider OpenClaw**

Yes. Cleanly. Three mechanisms.

### 7a. HTTP hooks ingress (exactly what an MQTT bridge needs)

```json5
{ hooks: { enabled: true, token: "shared-secret", path: "/hooks" } }
```

```bash
# Enqueue a system event into the main session (NO model call)
curl -X POST http://127.0.0.1:18789/hooks/wake \
  -H 'Authorization: Bearer SECRET' -H 'Content-Type: application/json' \
  -d '{"text":"New email received","mode":"now"}'

# Run a full agent turn (isolated session by default)
curl -X POST http://127.0.0.1:18789/hooks/agent \
  -H 'Authorization: Bearer SECRET' -H 'Content-Type: application/json' \
  -d '{"message":"Summarize inbox","name":"Email","model":"openai/gpt-5.6-sol"}'
```

Returns after **runner admission, not completion**. Status codes: `200` admitted, `400` invalid delivery/account, `409` session conflict, `502` gateway prep failure, `503` runner admission timeout (>15s).

`hooks.mappings[]` lets you bind an inbound hook to a specific `agentId` and a `messageTemplate` (e.g. `"{{messages[0].body}}"`) — so an MQTT→HTTP bridge of ~20 lines of Python could turn `qnet/room1/fall_detected` into a targeted agent turn on a locked-down agent.

### 7b. Automations / scheduler (in-Gateway, SQLite-persisted; Gateway must stay running)

Schedule types: `at` (one-shot ISO 8601 or relative `20m`), `every` (`10m`/`1h`/`1d`), `cron` (5- or 6-field, `--tz <IANA>`), **`on-exit`** (fire when a watched command exits), **`stream`** (fire from batched lines of a supervised long-lived command — *interesting: you could pipe a GStreamer/sensor process's stdout into this*).

Payloads (exactly one per job): `--system-event` (queued, no model call), `--message` (model-backed agent turn), `--command`/`--command-argv` (shell on Gateway host), `--script` (headless code-mode; needs `cron.triggers.enabled: true`).

Session styles: `main` | `isolated` | `current` | `session:<id>`. Delivery: `announce` (fallback-deliver to chat), `webhook` (POST finished event), `none`.

```bash
openclaw automations create "2027-02-01T16:00:00Z" \
  --name "Reminder" --session main \
  --system-event "Check the automations docs" --wake now --delete-after-run

openclaw automations add --name "PR CI watcher" --every 30s \
  --trigger-script ./watch-pr-ci.js --message "Respond to CI status change" --session isolated
```

Trigger scripts return `{ fire, message?, state? }`; **30s minimum interval, 30s evaluation timeout**. Outbound webhook URLs are SSRF-restricted (`cron.webhookSsrfPolicy.allowedHostnames`) — loopback/private targets blocked by default. Cron DOM+DOW uses **OR** semantics (croner). `--model` overrides are strict: disallowed model = validation failure, not silent fallback. Kill switch: `cron.enabled: false` or `OPENCLAW_SKIP_CRON=1`.

### 7c. Internal hooks (in-Gateway event handlers, TS/JS)

Hookable events: `command:new|reset|stop|command`, `session:auto-reset`, `session:compact:before|after`, `session:patch`, `agent:bootstrap`, `gateway:startup|shutdown|pre-restart`, `message:received|transcribed|preprocessed|sent`.

```json
{ "hooks": { "internal": { "enabled": true,
  "entries": { "session-memory": { "enabled": true }, "command-logger": { "enabled": false } } } } }
```

Handlers are async TS/JS and *can* spawn child processes (docs show `execFile` calling `openclaw system event`), but "keep handlers fast."

### 7d. CLI injection
`openclaw agent` triggers a run from the shell. Also `message send|broadcast|poll|react`, `nodes invoke|notify|push`, `nodes canvas|camera|screen`, `devices approve`, `infer tts convert|voices|personas|set-provider`, `cron *`, `tasks list|show|cancel`, `gateway start|stop|restart|status|health|diagnostics export`, `webhooks gmail setup`. Global flags: `--profile <name>`, `--dev`, `--json`.

---

## 8. TTS / voice

**14 speech providers.** Auto-TTS converts outbound replies to audio: native voice notes on Feishu/Matrix/Telegram/WhatsApp (Opus 48 kHz/64 kbps), MP3 attachments (44.1 kHz/128 kbps) elsewhere, PCM or `ulaw_8000` for Talk/telephony.

```json5
{
  tts: {
    auto: "always",           // off | always | inbound | tagged
    provider: "elevenlabs",
    providers: { elevenlabs: { apiKey: "${ELEVENLABS_API_KEY}", model: "eleven_multilingual_v2" } },
  },
}
```

- **Providers that need no API key: `microsoft` (Windows speech synthesis) and `tts-local-cli`.** ✅ This is our offline path on the Copilot+ PC — and `tts-local-cli` is the hook for wiring in Piper/MeloTTS from AI Hub (we already have `pipertts_en.yaml` and `melotts_en.yaml` cached).
- **Voice cloning:** ElevenLabs (cloud) and **MLX local TTS with voice cloning — macOS only** (`openclaw-mlx-tts`). *There is no documented local voice-cloning path on Windows.* For the parent's-cloned-voice feature this is a real gap: OpenClaw's answer would be ElevenLabs, which contradicts our privacy-first pitch.
- **Personas:** stable spoken identities applied deterministically across providers, with fallback policies `preserve-persona` | `provider-defaults` | `fail`. Managed via `openclaw infer tts personas` / `/tts persona <id>`.
- **Model-driven directives** (nice for emotional reassurance in a fall scenario):
  ```
  [[tts:speakerVoiceId=abc123 model=eleven_v3 speed=1.1]]
  [[tts:text]](laughs) Expressive content here.[[/tts:text]]
  ```
  Keys: `provider`, `speakerVoiceId`, `model`, `speed`, `seed`, `emotion`, language codes.
- Slash commands: `/tts on|off|status`, `/tts audio <text>`, `/tts persona`, `/tts provider`, `/tts latest`. Per-user overrides in `~/.openclaw/settings/tts.json`.
- **Talk mode** (`/nodes/talk`): continuous listen→transcribe→model→speak loop. STT = Apple Speech (macOS/iOS), Android device speech service, browser providers. `silenceTimeoutMs` 700 ms (macOS/Android) / 900 ms (iOS). `interruptOnSpeech: true` by default (barge-in: playback stops, interruption timestamp noted for the next prompt). Realtime options: OpenAI GPT-4 Realtime, Google Live, client-owned WebRTC (bypasses Gateway) or Gateway-owned relay. **Windows is not listed.** Wake words are separate and Gateway-owned (`/nodes/voicewake`).

---

## 9. Security / permission model

Explicit trust assumption: *"one trusted operator boundary per gateway (single-user, personal-assistant model)."* And bluntly: *"OpenClaw is not a hostile multi-tenant security boundary."* Multi-user → one isolated Gateway per tenant.

- **Gateway auth:** `token` (recommended), `password` (env var), or `trusted-proxy` (identity from proxy headers). Applies universally regardless of locality. `sessionKey` is *routing*, not authorization.
- **Device pairing:** every `connect` carries a signed device identity and must sign a `connect.challenge` nonce (signature v3 binds platform + deviceFamily). New devices → pairing request → `openclaw devices approve <requestId>` (pending expires after 5 min). Loopback auto-approves for local UX; LAN/tailnet requires explicit approval. `sshVerify` gives key-verified node enrollment over operator SSH. Auto-approve off by default, needs CIDR allowlist.
- **DM policies:** `pairing` (default — expiring codes, ignored until approved) | `allowlist` | `open` (needs explicit `"*"`) | `disabled`. Use `session.dmScope: "per-channel-peer"` to stop cross-user context bleed.
- **Tool policy:** profiles (`messaging`, `minimal`, custom), explicit allow/deny, interactive approval workflows, `tools.toolsBySender`. Exec approvals bind to exact command/cwd/target-file; **heredocs always require approval** in allowlist mode.
- **Sandboxing:** whole-Gateway-in-Docker, or host Gateway + Docker/Podman tool sandbox. Per-agent `sandbox.mode` + `workspaceAccess: none | ro | rw`. `tools.elevated` escapes the sandbox — keep `allowFrom` tight.
- **Prompt injection:** acknowledged as *"not solved by system prompt guardrails alone."* External content wrapped in `<<<EXTERNAL_UNTRUSTED_CONTENT ...>>>`; self-hosted chat-template tokens (`<|im_start|>` etc.) stripped to block role-forging.
- `openclaw security audit [--fix]` checks inbound policy, tool blast radius, exec approval drift, network exposure, browser exposure, plugin allowlists. Threat model mapped to **MITRE ATLAS** (`/security/THREAT-MODEL-ATLAS`).
- Hardened baseline:
  ```json5
  { gateway: { mode: "local", bind: "loopback", auth: { mode: "token", token: "long-random-token" } },
    session: { dmScope: "per-channel-peer" },
    tools: { profile: "messaging",
             deny: ["group:automation","group:runtime","group:fs","sessions_spawn"],
             exec: { security: "deny" } } }
  ```

**Demo-relevant:** the security model is genuinely good and would be *quotable* in a privacy-first pitch. It also means non-trivial setup friction (pairing approvals, tokens) on a judge's machine — a **Deployment (20 pts)** liability.

---

## 10. Resource footprint

Not documented anywhere — no stated RAM/CPU/disk figures. Observable proxies:
- Persistent Node process (Gateway) + optional Hub tray app + optional local model server.
- Windows Hub installers: **104.8 MB (arm64)** / 119.7 MB (x64); portable tray zips 139.5–148.5 MB.
- The `openclaw` npm tree pulls `playwright-core`, `@anthropic-ai/sdk`, `openai`, `@google/genai`, `@mistralai/mistralai`, `@modelcontextprotocol/sdk`, `express`, `kysely`, `grammy`, `typescript` — expect a several-hundred-MB `node_modules` before any model weights.
- systemd unit on Linux applies OOM bias so children die before the Gateway. Nothing equivalent documented for the Windows Scheduled Task.

For a submission that must ship as **one .EXE/.MSIX that judges install and run**, this is the crux: OpenClaw + a Node 26 runtime + our code + model weights is a very large, very unfamiliar bundle to assemble in four days.

---

## 11. Honest evaluation & recommendation

### What OpenClaw genuinely gives us
1. **`POST /hooks/agent` + `/hooks/wake`** — the exact "external event triggers an agent turn" primitive our architecture needs, already built, tokenized and mapped to locked-down agents. Best single feature for us.
2. **MCP client** — our Python tools (GStreamer control, light flicker, caregiver notify, escalate) become available with zero TS.
3. **Automations `stream`/`on-exit` triggers** — a sensor process's stdout can drive agent turns.
4. **TTS with no-API-key providers** (`microsoft`, `tts-local-cli`) + personas + emotion directives.
5. **`linux-node`** — the Arduino UNO Q (Debian arm64) could pair as a headless node (`openclaw node run --host <gw> --port 18789`) exposing `system.notify`, `system.run` (approval-gated), `computer.act`. A nice "heterogeneous devices in one fabric" visual.
6. Credible **security narrative** we can cite.

### What disqualifies it from the critical path
1. **Their own local-model guidance is ~$30k of GPU.** We have a Snapdragon X Elite. Qwen3-4B w4a16 on its NPU is **21.8 tok/s / TTFT 98 ms**; OpenClaw's example config asks for a 192k context window. Their documented mitigations for local models are `localModelLean: true` and *disabling tools entirely*. A cloud-model demo would gut the privacy-first pitch and needs conference Wi-Fi to work at 1pm on Aug 7.
2. **Latency you don't own = points you can't claim.** Technical Implementation is 40 pts on *resource utilization, optimization, latency, energy efficiency*. Judges want *our* NPU offload and *our* measured numbers. Wrapping the interesting part in a 76k-commit Node framework makes it hard to instrument and hard to attribute.
3. **Deployment (20 pts) is a packaged .EXE/.MSIX of *our* application.** Bundling Node 26 + a ~300 MB node_modules + gateway service registration + device pairing approvals + WebView2 + model weights into an installer that works first-try on a judge's Copilot+ PC — in four days, on Windows-on-ARM — is the highest-risk line item in the whole project. A PyInstaller/MSIX bundle around a ~1000-LOC Python service is a fraction of the risk.
4. **Windows-on-ARM is a documented second-class citizen.** Docs steer to WSL2 as "most Linux-compatible"; Talk mode omits Windows; `sqlite-vec` prebuilds and Playwright-ARM64 are unknowns. Debugging any one of these could burn a full build day.
5. **No local voice cloning on Windows.** MLX voice cloning is macOS-only. Our headline "speak in the parent's cloned voice" feature would be forced onto ElevenLabs cloud — directly contradicting the pitch.
6. **Config surface is enormous** (`openclaw.json`: gateway, models, agents, tools, skills, plugins, hooks, cron, tts, session, sandbox…) and skills are **snapshotted at session start**, a classic live-demo footgun.
7. **No home-automation primitives at all** — no Home Assistant, MQTT, Matter or Zigbee plugin exists. We'd be writing that bridge anyway. (Third-party Home Assistant MCP servers exist and could be mounted via `mcp.servers`, but that's another moving part.)
8. **Innovation optics.** "We configured OpenClaw" reads as integration; "we built a semantic-event agent fabric across four Snapdragon devices with NPU-resident models" reads as engineering. 25 pts of Use-Case & Innovation rewards the latter.

### Would Claude Agent SDK be better?
`@anthropic-ai/claude-agent-sdk@0.3.220` (Node ≥18, peers: zod ≥4, `@anthropic-ai/sdk` ≥0.93, `@modelcontextprotocol/sdk` ≥1.29, bundles `claudeCodeVersion: 2.1.220`). Excellent tool-calling, MCP-native, minimal ceremony.

**But** it requires the Claude Code CLI + cloud Claude API. That is (a) not on-device, (b) not privacy-first, (c) network-dependent at judging time. **Use it for build-time velocity (we already are) and optionally as an explicit "cloud escalation tier" — not as the runtime orchestrator.**

### ✅ Recommendation

**Plan A — build a lean custom orchestrator (recommended).**
Python service on the Copilot+ PC, ~600–1000 LOC:
- **Event bus:** MQTT (`aiomqtt` + Mosquitto, or an embedded broker) — Arduino UNO Q nodes publish semantic JSON events only. This *is* the architecture story; own it.
- **Policy + agent loop:** local SLM with strict tool-calling. Use **Qwen3-1.7B w4a16 (42.2 tok/s, 52 ms TTFT)** for the fast triage/routing turn and **Qwen3-4B or Qwen3-VL-4B w4a16 (~21 tok/s, ~1300 tok/s prefill)** for the reasoning/conversation turn. Keep the system prompt under ~800 tokens and the tool schema to 5–8 tools — the opposite of OpenClaw's prompt budget.
- **Voice:** Whisper-small/base (cached) for STT, Piper or MeloTTS (cached) for TTS — all NPU/on-device, all in `research/tech/_cache` already.
- **Tools:** caregiver notify, live-connect, light flicker, escalate, speak-as-persona.
- **Instrument everything:** per-stage timestamps (event→decision→speech), tokens/s, NPU vs CPU vs GPU comparison, power. That table is worth more of the 40 pts than any framework choice.
- **Package:** PyInstaller one-folder → MSIX (or Inno Setup .EXE). Single artifact, no Node, no WSL.

**Two-tier escalation is a bonus story that also uses the AIC100 in the kit:** local SLM handles ~95% of events; on genuine ambiguity, escalate to a larger model served OpenAI-compatibly on **Cloud AI 100** — and report the measured escalation rate and latency delta. This makes the AIC100 load-bearing instead of decorative.

**Plan B — de-risk the agent loop (fallback if small-model tool calling is flaky).**
Do not fight it. Replace free-form function calling with **constrained decoding** (llama.cpp GBNF grammar / `outlines`) so the SLM emits a fixed JSON action schema; or split responsibilities — deterministic rule/state-machine policy engine decides *what* to do, LLM only generates *what to say*. This is more reliable, lower-latency, and completely defensible on stage. Budget: half a day to swap in.

**Plan C — OpenClaw as optional interop, not dependency (~2 hours, do this on Day 3–4 if ahead).**
Ship `qnet-home` as an **MCP stdio server** plus a small `SKILL.md`, and document: *"QNet Home also plugs into OpenClaw — add `mcp.servers.qnet` and point `POST /hooks/agent` at our event bridge."* Optionally pair the Arduino UNO Q as an `openclaw node` for one slide. Zero risk to the deliverable, real ecosystem credit in the README and presentation. Skip entirely if behind schedule.

**Plan D — only if the team overrules the above.** OpenClaw on native Windows ARM64 (not WSL2, to keep the install story sane), LM Studio or `llama.cpp` serving an OpenAI-compatible endpoint, `hooks.enabled` with a token, `hooks.mappings` binding our MQTT bridge to a sandboxed agent with `tools.profile: "messaging"`, TTS provider `microsoft`, and MCP for our device tools. **Spike this in a 3-hour timebox on Day 1 and kill it if the Gateway isn't answering `/hooks/agent` with a local model by hour 3.**

### Day-1 go/no-go checklist if anyone spikes OpenClaw
1. `node -v` from an official win-arm64 build ≥ 22.22.3 → `iwr -useb https://openclaw.ai/install.ps1 | iex`
2. `openclaw doctor` and `openclaw gateway status` clean (watch for `sqlite-vec` / Playwright warnings)
3. `curl http://127.0.0.1:1234/v1/models` against a local server, then wire `models.providers.*.baseUrl` with `api: "openai-completions"`
4. `POST /hooks/agent` returns `200` (not `503`) with the local model — **this is the kill criterion**
5. `/tts provider microsoft` then `/tts audio "Are you OK?"` actually produces audio on the PC
6. Measure end-to-end event→speech latency. If > 5 s, stop and go to Plan A.

---

## Sources

- [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw) — README, stars/forks/commits, MIT license
- [OpenClaw v2026.7.1 release](https://api.github.com/repos/openclaw/openclaw/releases/latest) — tag, 2026-07-13, highlights
- [npm: openclaw@2026.7.1-2](https://registry.npmjs.org/openclaw/latest) — engines, dependencies, optionalDependencies
- [docs.openclaw.ai](https://docs.openclaw.ai/) — documentation hub
- [docs.openclaw.ai/llms.txt](https://docs.openclaw.ai/llms.txt) — full page index
- [Architecture](https://docs.openclaw.ai/concepts/architecture) — Gateway, WS protocol, pairing, port 18789
- [Agent loop](https://docs.openclaw.ai/concepts/agent-loop) — turn stages, session lanes, compaction, timeouts
- [Skills](https://docs.openclaw.ai/tools/skills) — SKILL.md format, precedence, gating, token budget
- [Plugins](https://docs.openclaw.ai/tools/plugin) — manifest, `api.on`, `plugins install --link`
- [Plugin inventory](https://docs.openclaw.ai/plugins/plugin-inventory) — 54 bundled / 91 external / 2 source-only
- [MCP](https://docs.openclaw.ai/tools/mcp) — client + `openclaw mcp serve`, transports, `mcp.servers` config
- [Model providers](https://docs.openclaw.ai/providers) — provider list
- [Local models](https://docs.openclaw.ai/gateway/local-models) — LM Studio/vLLM/LiteLLM config, "~$30k+" hardware guidance, `localModelLean`, `compat.supportsTools`
- [Install](https://docs.openclaw.ai/install) — Node 22.22.3+/24.15+/25.9+, installer scripts, `openclaw doctor`
- [Getting started](https://docs.openclaw.ai/start/getting-started) — onboarding wizard
- [Platforms](https://docs.openclaw.ai/platforms) — support matrix
- [Windows](https://docs.openclaw.ai/platforms/windows) — Hub vs PowerShell vs WSL2, local MCP server mode
- [Linux](https://docs.openclaw.ai/platforms/linux) — `linux-node` plugin, headless node, systemd
- [Nodes](https://docs.openclaw.ai/nodes) — pairing, per-platform command allowlists, `openclaw nodes *` CLI
- [Talk mode](https://docs.openclaw.ai/nodes/talk) — STT/TTS engines, barge-in, silence timeouts (no Windows)
- [Voice wake](https://docs.openclaw.ai/nodes/voicewake)
- [TTS](https://docs.openclaw.ai/tools/tts) — 14 providers, `tts.auto`, personas, `[[tts:...]]` directives, keyless `microsoft`/local-CLI
- [Automations: cron, webhooks, Gmail PubSub](https://docs.openclaw.ai/automation/cron-jobs) — `/hooks/wake`, `/hooks/agent`, schedule/payload/session/delivery matrix
- [Hooks](https://docs.openclaw.ai/automation/hooks) — internal lifecycle events
- [CLI reference](https://docs.openclaw.ai/cli) — command surface
- [ClawHub](https://docs.openclaw.ai/clawhub) — registry, `skills search` / `plugins install clawhub:`
- [Security](https://docs.openclaw.ai/gateway/security) — trust model, DM policies, sandbox, prompt injection, `security audit`
- [Threat model (MITRE ATLAS)](https://docs.openclaw.ai/security/THREAT-MODEL-ATLAS)
- [github.com/openclaw/openclaw-windows-node](https://github.com/openclaw/openclaw-windows-node) + [v0.6.12 release](https://api.github.com/repos/openclaw/openclaw-windows-node/releases/latest) — signed arm64 installer, 2026-06-30, command families, SAPI TTS
- [npm: @anthropic-ai/claude-agent-sdk@0.3.220](https://registry.npmjs.org/@anthropic-ai/claude-agent-sdk/latest) — Node ≥18, peers, bundles Claude Code 2.1.220
- [nodejs.org/dist/index.json](https://nodejs.org/dist/index.json) — official `win-arm64` builds for v22.22.3+, v24.x, v25.x, v26.x
- Local AI Hub metrics: `research/tech/_cache/llm_qwen3_1_7b.yaml`, `llm_qwen3_4b.yaml`, `llm_qwen3_vl_4b_instruct.yaml`, `pipertts_en.yaml`, `melotts_en.yaml` — Snapdragon X Elite CRD w4a16/q4_0 tok/s, prefill, TTFT
