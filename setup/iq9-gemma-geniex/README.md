# IQ-9075: Gemma (E2B) via GenieX — setup log & runbook

Sets up the QNet Home "brain" LLM per `docs/DESIGN.md` §10: **Gemma 4 E2B-it (Q4_0 GGUF)** served by **GenieX** as an OpenAI-compatible endpoint on `http://127.0.0.1:18181/v1`. This is design §15 day-one check #2, including first measured numbers for QCS9075.

*Performed 2026-08-05 from the workshop Windows laptop, entirely over SSH. Every step below was actually run; outputs shown are real.*

---

## Device access

| | |
|---|---|
| Device | Qualcomm IQ-9075 EVK ("the brain") |
| IP | `10.73.51.175` (DHCP, Wi-Fi `wlp1s0` — IP may change; re-check with the workshop router if unreachable) |
| User | `ubuntu` |
| Password | shared workshop credential — ask the team; not committed here since the repo may be published (AGPL source link requirement, design §18) |
| SSH alias | `ssh iq9` (key-based, see Step 1) |

---

## Step 1 — SSH key auth (no password prompts, ever)

Done from the Windows laptop (OpenSSH 10.0p2 via Git Bash):

1. Reused the existing `~/.ssh/id_ed25519` keypair.
2. Installed the public key on the device (one-time password auth via `SSH_ASKPASS`; on Linux/macOS `ssh-copy-id ubuntu@10.73.51.175` does the same):
   ```bash
   # on the device, ~/.ssh/authorized_keys now contains the workstation pubkey
   mkdir -p ~/.ssh && chmod 700 ~/.ssh
   echo '<pubkey>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys
   ```
3. Added to the workstation's `~/.ssh/config`:
   ```
   Host iq9
     HostName 10.73.51.175
     User ubuntu
     IdentityFile ~/.ssh/id_ed25519
     ServerAliveInterval 30
     ServerAliveCountMax 4
   ```

**Verified:** `ssh -o BatchMode=yes iq9 'echo SSH_OK'` → `SSH_OK` (BatchMode = fails rather than prompt, so this proves key auth).

New teammate? Generate a key (`ssh-keygen -t ed25519`), have someone who already has access append your `.pub` to the device's `~/.ssh/authorized_keys`, add the config block above.

## Step 2 — Baseline probe (design §15 checklist)

All checks passed with large margins:

| Check | Result | Design requirement |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS (noble), kernel `6.8.0-1080-qcom` | Ubuntu ✓ |
| Arch | aarch64 | ✓ |
| SoC | `QCS9075` (soc_id 676) — confirms it's the real IQ-9075 | ✓ |
| RAM | **34 Gi total, 33 Gi available** | ~2.8 GB model + 16k KV cache ✓ (huge headroom) |
| Disk | 93 G free on `/` | ≥ 6 GB ✓ |
| CPU | 8× Cortex-A78C | — |
| NPU | `/dev/fastrpc-cdsp`, `-cdsp1`, gdsp0/1 present; `/usr/lib/rfsa/adsp` present | NPU access ✓ |
| Internet | huggingface.co and the GenieX S3 bucket both reachable | needed for pull ✓ |
| Clock | `systemd-timesyncd` active, synchronized | §5 requirement ✓ |
| Network | Wi-Fi (`wlp1s0`), 10.73.51.0/24, ~250 ms RTT from laptop | note: Wi-Fi latency is laptop↔device only; the LLM endpoint is localhost on-device |

**RAM conclusion for the team:** the design's "if the IQ-9075 is tight" fallbacks (§15) are *not needed* — 34 GB is ~10× requirement.

## Step 3 — Host dependencies (apt)

Per the official GenieX Linux-ARM64 native install docs:

```bash
sudo apt-get update
sudo apt-get install -y libatomic1 libglib2.0-0t64        # standard deps (ocl-icd-libopencl1: see note)
sudo apt-get install -y qcom-adreno1 qcom-fastrpc1 libqnn1 # Qualcomm driver libs (PPA pre-configured on the EVK image)
```

Final state (all requirements met):

| Package | Version | Note |
|---|---|---|
| `libatomic1` | 14.2.0-4ubuntu2~24.04.1 | already present |
| `libglib2.0-0t64` | 2.80.0-6ubuntu3.8 | already present (24.04's name for `libglib2.0-0`) |
| `qcom-adreno1` | 1.855.3+rev2 | already present |
| `qcom-fastrpc1` | 1.0.15 | already present |
| `libqnn1` | 2.46.0 (qcom-ppa) | **installed by us** via `apt-get download` + `dpkg -i` (see gotcha #1) |
| OpenCL loader | provided by `qcom-adreno1` | do **not** install `ocl-icd-libopencl1` (see gotcha #2) |

**Gotcha #1 — the EVK image has pre-existing broken apt dependencies** (not caused by us): `qimsdk-cpp`, `python-gstreamer1.0-qcom` and `gstreamer1.0-qcom-test-framework` require `libgstreamer-qcom1.0-0 >= 1.24.13`, but the configured repos only carry `1.24.2`. This makes every plain `apt-get install` abort with "Unmet dependencies. Try 'apt --fix-broken install'". **Do not run `apt --fix-broken install`** — the newer gstreamer-qcom isn't available, so apt would "fix" it by *removing* the qimsdk/GStreamer stack (which the room nodes' vision pipeline story relies on). Workaround used for anything new: `apt-get download <pkg> && sudo dpkg -i <pkg>.deb` — installs cleanly without touching the broken set.

**Gotcha #2 — `ocl-icd-libopencl1` conflicts with `qcom-adreno1`.** The Adreno package already ships `/usr/lib/aarch64-linux-gnu/libOpenCL.so.1` (its own ICD loader) and declares a package conflict. The docs list `ocl-icd-libopencl1` for generic hosts; on this EVK the requirement is already satisfied. Skip it.

## Step 4 — GenieX CLI install

```bash
curl -fsSL https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-geniex/install.sh | sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile   # non-login SSH: use ~/.local/bin/geniex
```

Installer output confirmed: SHA256 verified, **NPU FastRPC symlinks created automatically** (`libcdsprpc.so`, `libadsprpc.so` — the step the troubleshooting docs warn about if you install manually). Binary at `~/.local/share/geniex/geniex`, launcher at `~/.local/bin/geniex`.

**Verified:**

```
GenieX CLI Version:     v0.3.18
QAIRT Runtime Version:  v2.45.0.260326
LlamaCPP Runtime Hash:  6ba5ef2
```

## Step 5 — Pull the model

The exact repo name from the design resolved on the first try:

```bash
~/.local/bin/geniex pull google/gemma-4-E2B-it-qat-q4_0-gguf
```

4.3 GB download (~2.5 min at ~33 MB/s on the workshop Wi-Fi). `geniex list` confirms: **4.0 GiB on disk, precision Q4_0**. Cache lives in `~/.cache/geniex/models/`. Note GenieX detects the model type as **vlm** (Gemma 4 E2B is multimodal; the repo ships an `mmproj` vision projector) — this matters, see the bug below.

## Step 6 — The bug we hit, and the workaround (READ THIS before touching the model cache)

**Symptom:** model loads and generates fluently, but ignores the prompt entirely — off-topic replies, `"prompt_tokens": 1` in every response, in both `geniex infer` and the server.

**Root cause:** GenieX ≤ v0.3.18 has a VLM-path tokenization bug — an uninitialized `text_len` field silently corrupts *text-only* prompts to VLM-typed models. Fixed upstream in [PR #1273](https://github.com/qualcomm/GenieX/pull/1273) (merged Aug 3 2026, **not yet in any release** as of Aug 5; latest release v0.3.18 is from Jul 31). Gemma-4 is one of the confirmed-affected models. Related context: Gemma 4 also shipped its chat template outside `tokenizer_config.json` ([transformers #45205](https://github.com/huggingface/transformers/issues/45205)), which muddied diagnosis.

**Workaround applied (until a fixed GenieX release):** force the model down the plain-LLM code path, which is unaffected. The brain only ever sends text (the VLM for "where's my stuff" runs on the *nodes*, §2/§13), so nothing is lost:

```bash
# server must be stopped first: pkill -x geniex   (note: pkill -f self-matches your ssh command — use -x)
cd ~/.cache/geniex/models/google/gemma-4-E2B-it-qat-q4_0-gguf
cp -n geniex.json geniex.json.bak
python3 - <<'EOF'
import json
m = json.load(open("geniex.json"))
m["ModelType"] = "llm"
m["MMProjFile"] = {"Name": "", "Downloaded": False, "Size": 0}
json.dump(m, open("geniex.json", "w"))
EOF
```

**Verified fixed:** same request now returns `"Hello!"` with `prompt_tokens: 23`.

⚠️ A future `geniex pull` of this model may rewrite `geniex.json` (re-marking it `vlm`) — if prompts suddenly stop landing again, re-apply the patch. When GenieX ≥ v0.3.19 ships with PR #1273, run `geniex update`, restore `geniex.json.bak`, and drop this workaround.

## Step 7 — First working inference

CLI smoke test (also how to sanity-check after any change):

```bash
~/.local/bin/geniex infer google/gemma-4-E2B-it-qat-q4_0-gguf -c hybrid -p "Say hello in one short sentence." --max-tokens 40 --think=false
```

Ran on **hybrid (NPU+CPU) compute** — the NPU path works on this board; no CPU fallback needed. Note: each CLI invocation reloads the model (~70 s); the server keeps it resident — use the server for anything repeated.

## Step 8 — Serve as a service (systemd)

`/etc/systemd/system/geniex-serve.service` (installed and enabled):

```ini
[Unit]
Description=GenieX OpenAI-compatible LLM server (Gemma 4 E2B for QNet Home)
After=network.target

[Service]
User=ubuntu
ExecStart=/home/ubuntu/.local/bin/geniex serve --skip-update
Restart=always
RestartSec=3
Environment=HOME=/home/ubuntu

[Install]
WantedBy=multi-user.target
```

Endpoint: **`http://127.0.0.1:18181/v1`** (localhost-only by design — the agent runs on this same board, §10). Swagger UI at `http://127.0.0.1:18181`. Model id as served: **`google/gemma-4-E2B-it-qat-q4_0-gguf:Q4_0`** (the bare name without `:Q4_0` also works in requests).

Operate it:

```bash
systemctl status geniex-serve          # check
sudo systemctl restart geniex-serve    # restart (endpoint back in ~8 s; model loads on first request, ~12 s)
journalctl -u geniex-serve -f          # live logs
curl -s http://127.0.0.1:18181/v1/models   # is it answering?
```

**Verified:** enabled at boot; survives `systemctl restart`; answers after restart.

## Step 9 — Tests and measured numbers

Rerunnable suite: **`tests/test_gemma_geniex.py`** (this folder) (run on the device: `~/qnet-venv/bin/python test_gemma_geniex.py`; venv setup in the file header — note `python3.12-venv` had to be installed via the gotcha-#1 dpkg workaround). Uses the same `openai` client + `base_url` the agent will use.

Results 2026-08-05, all on hybrid/NPU:

| Test | Result |
|---|---|
| `/v1/models` lists the model | ✅ |
| Chat completion, exact-instruction prompt | ✅ `HELLO QNET` |
| QNet fall-response classification ("i'm fine"→ok, "hip hurts"→escalate, silence→escalate) | ✅ 3/3 correct |
| Native OpenAI tool-calling | ❌ see finding 2 |

**Measured `[M]` numbers for QCS9075 (design §10 had `[?]`):**

| Metric | Value |
|---|---|
| Decode throughput | **~15.7–16.2 tok/s** (6 runs, ~200-token generations) |
| TTFT, model warm | **~0.18 s** |
| First request after service start (model load included) | ~12 s |
| Model RAM footprint | ~4 GB of 34 GB — no pressure |

§10 budgeted 1–3 s per agent turn: at 16 tok/s a one-sentence spoken line (~25 tokens) ≈ **1.7 s** → within budget. ✔

**Finding 1 — thinking is on by default, and the server uses non-OpenAI field names for the knobs that control it.** For non-trivial prompts the response contains Gemma 4's raw reasoning inline: `<|channel>thought ...reasoning...<channel|>ANSWER` — and short/ambiguous prompts ("hi") think the *longest*, sometimes never leaving the thought channel. The controls exist but under GenieX's own names — the full request schema is at `GET /docs/swagger.yaml` (Swagger UI: `http://127.0.0.1:18181/docs/ui/`):

| What you want | Wrong (silently ignored) | Right (verified working) |
|---|---|---|
| No thinking | `think: false` | **`enable_think: false`** → "hi" answers in 10 tokens, instantly |
| Token cap | `max_tokens` | **`max_completion_tokens`** (cap includes thinking tokens; `finish_reason: "length"`) |

Unknown fields are silently accepted, which is what made this look like a server bug at first. **`agent/llm.py` should send `enable_think: false` + `max_completion_tokens`, and still strip via last-`<channel|>` as a belt-and-braces** (with thinking off no marker appears; the strip is then a no-op). Other schema extras worth knowing: `top_k`, `min_p`, `repetition_penalty`, per-request `compute` (cpu/gpu/npu/hybrid), `enable_json`, `grammar_string`/`grammar_path` (the O1 path, server-side), and `nctx` (§10 wants 16k context — pass `nctx: 16384` per request or start serve with `--nctx`).

**Confirmed: inference runs on the Hexagon NPU.** `journalctl -u geniex-serve` shows the llama.cpp Hexagon backend loading `libggml-htp-v73.so` onto the `cdsp` FastRPC domain — the ~16 tok/s measured above is the NPU/HTP path, not CPU.

**Finding 2 — native tool-calling does not work on v0.3.18, and `tool_choice` is not enforced.** With a `tools=[say(text)]` list and a prompt demanding tool use, the model *correctly decides* to call the tool and emits Gemma 4's native syntax — but the server returns it as plain content; `tool_calls` stays null. `tool_choice: "required"` behaves identically to `"auto"` (raw evidence in the appendix). Design consequence: **don't build on SDK-native `tools=`** — the runtime's constraint mechanism (grammar) is the intended O1 path, but see Finding 3 for why that too must wait for a GenieX fix. Re-test after the next GenieX release; PR #1273's fix may also change VLM/template behavior.

**Finding 3 — structured output on the server: grammar works per-request, but v0.3.18 crashes around it (tested 2026-08-05 evening; raw evidence in the appendix).** Verified against the server, not the CLI:

| Variant | Result |
|---|---|
| `grammar` / `grammar_string` body field | **Both accepted and enforced** — with a 2-literal GBNF the answer segment came back exactly `{"action": "exit"}` (semantically correct for the prompt). Thinking still ran *before* the constrained answer; combine with `enable_think: false` for pure output. |
| …but the *next* generation | **Crashes the server** (`signal arrived during cgo execution`, exit status 2). Reproduced: two grammar requests → next vanilla request dies. systemd restarts it in ~10 s. |
| `response_format: {"type":"json_schema",…}` | **Crashes the server instantly** (native register-dump crash). Independent of grammar. |
| `response_format: {"type":"json_object"}` | Accepted (200) but **not enforced** — thought text came back, not JSON. |
| `enable_json: true` | Crashed the server in testing; occurred right after grammar requests, so independent-vs-poisoned is unconfirmed. Treat as unsafe. |

**Net for the agent (v0.3.18):** don't use `response_format`, `enable_json`, or grammar fields against the long-lived server. Until a GenieX release fixes these, the O1-style guarantee has to be **prompt + strip + validate + retry** in `agent/llm.py` (validate the stripped answer against the expected enum/JSON; retry once on mismatch — the engine's phase allowlist already refuses anything invalid). Grammar is the right mechanism and demonstrably constrains correctly — re-test it (and `json_schema`) the moment GenieX ≥ v0.3.19 ships, since [PR #1273](https://github.com/qualcomm/GenieX/pull/1273)-era fixes may land together. The chat UI's grammar/JSON controls carry ⚠ warnings for this reason.

## Alternative: Docker path (not used, documented for recovery)

There is an official containerized route — `docker pull docker.io/qualcomm/geniex:latest`, run with `--privileged -v /usr/lib:/opt/qcom-lib:ro` for NPU access — which would give a storable, reproducible image. We chose native install because (a) the device is healthy — the pre-existing apt breakage is confined to the GStreamer-qcom stack and never blocked us, (b) the v0.3.18 prompt bug lives in the GenieX binary and is identical inside the container, so Docker wouldn't have avoided it, and (c) the design runs the agent stack under systemd on the host (§5). If the device ever has to be reflashed: this document *is* the reproduction recipe — steps 3–8 take ~15 min plus the model download.

## Test chat UI

**`chat.html`** (this folder) — a single-file browser chat for poking at the model by hand (streaming, multi-turn, per-reply TTFT/tok-per-s, Gemma's thinking channel shown collapsed instead of polluting the answer). No build, no dependencies. The settings row exposes the server's real parameter set (verified against its swagger schema): **thinking on/off** (off by default — short prompts like "hi" otherwise think for ages), max tokens (`max_completion_tokens`), temperature, top_p, top_k, min_p, repetition/presence/frequency penalties, **per-request compute (npu/hybrid/gpu/cpu — good for A/B-ing silicon; first reply after a switch is slow, the model reloads)**, and — behind ⚠ warnings — JSON mode and a GBNF grammar box. The ⚠ is real: on v0.3.18 `enable_json` crashed the server in testing, and a grammar request works but makes the *next* generation crash it (Finding 3). systemd brings it back in ~10 s either way.

To use from a laptop: double-click **`start-chat.bat`** (this folder) — it opens the page and an SSH tunnel to the device (`ssh -N -L 18181:127.0.0.1:18181 iq9`; the endpoint is localhost-only on the IQ-9075, so the tunnel is what makes `127.0.0.1:18181` work from your machine). Keep the terminal window open while chatting. Requires the Step-1 SSH key setup (any teammate: add your key first).

Verified 2026-08-05: CORS is open on the server (`Access-Control-Allow-Origin: *`), streaming works through the tunnel, and the history sent on each turn carries only clean answers (thought text stripped) to keep prompts small.

## Quick-reference: what a teammate needs to know

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:18181/v1", api_key="geniex")  # key unchecked
r = client.chat.completions.create(
    model="google/gemma-4-E2B-it-qat-q4_0-gguf",
    messages=[{"role": "user", "content": "..."}],
    temperature=0.0,
    extra_body={"enable_think": False, "max_completion_tokens": 256},  # GenieX names, not OpenAI's
)
text = r.choices[0].message.content.rsplit("<channel|>", 1)[-1].strip()  # no-op when thinking off
```

- Endpoint is localhost-only on the IQ-9075 — run your code on the device (or SSH-tunnel: `ssh -L 18181:127.0.0.1:18181 iq9`).
- Don't `apt --fix-broken install`. Don't re-`geniex pull` the model without re-checking the Step-6 patch.
- Everything restarts itself (`Restart=always`); after a reboot the first request just takes ~12 s longer.
- **Requests serialize** — one model, one queue. A long thinking generation (or a teammate's test run) makes everyone else's requests look "stuck". Always send `enable_think: false` + a `max_completion_tokens` cap unless you're specifically testing thinking.
- **If the server stops answering** (e.g. a client was killed mid-generation and the log shows `dspqueue ... wait_signal_locked` errors — the NPU queue can wedge): `sudo systemctl restart geniex-serve`, wait ~10 s, done.

## Appendix — raw evidence for Findings 1–3 (server checks, 2026-08-05)

All against `POST /v1/chat/completions`, model `google/gemma-4-E2B-it-qat-q4_0-gguf:Q4_0`, `temperature: 0`. A `max_completion_tokens` cap (300–400) was added to bound runtime on the tool/thinking checks; it doesn't change field handling.

**Tool-calling** (`tools=[say(text)]`, prompt: "You MUST use the say tool… Do not answer in plain text"):

```
tool_choice=auto     → "tool_calls": null, "finish_reason": "stop", completion_tokens: 136
tool_choice=required → "tool_calls": null, "finish_reason": "stop", completion_tokens: 136
content (both): <|channel>thought …plans the call… <channel|><|tool_call>call:say{text:<|"|>Hello!<|"|>}<tool_call|>
```

**Constrained output** (prompt: reply ONLY as `{"action": "say"}` or `{"action": "exit"}`; person said "goodbye"):

```
response_format json_object  → HTTP 200, content: '<|channel>thought\nThe user is asking…' (not JSON; format ignored)
response_format json_schema  → CRASH: RemoteDisconnected; journal: native register dump (lr/sp/pc/fault), exit status 2
grammar        (GBNF, 2 literals) → HTTP 200, tail after <channel|>: '{"action": "exit"}'  ✅ parses, correct semantics
grammar_string (same GBNF)        → HTTP 200, tail after <channel|>: '{"action": "exit"}'  ✅
next vanilla request after the grammar pair → CRASH: 'signal arrived during cgo execution', exit status 2
enable_json true → CRASH: RemoteDisconnected (ran after grammar requests; independent-vs-poisoned unconfirmed)
```

**Token caps** (prompt: "Give me 30 detailed tips for learning piano"):

```
max_tokens: 20            → completion_tokens: 2048, finish_reason: "length"   (ignored; ran to server default)
max_completion_tokens: 20 → completion_tokens: 20,   finish_reason: "length"   (enforced exactly)
```

**Thinking leak** (weigh-both-sides prompt):

```
plain               → content starts '<|channel>thought\nThe user is asking for a balanced analysis…'
think: false        → content starts '<|channel>thought\nHere's a thinking process…'   (field silently ignored)
enable_think: false → content starts '## Should a Home Assistant Interrupt…'          (no markers)
```

Crash bookkeeping: three crashes total during this battery (`json_schema`, `enable_json`, post-grammar vanilla); `systemctl show geniex-serve -p NRestarts` went 0→3 and the service self-recovered each time. Vanilla requests on a fresh server never crashed all day.
