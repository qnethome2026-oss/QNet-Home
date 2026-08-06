# Cold start — power everything on

*Back to the [docs index](../README.md). Sister page:
[`troubleshooting.md`](troubleshooting.md) for when a step below fails.*

Everything on the boards is a service: power-cycling brings the house back with
no keystrokes — with one caveat for the voice app, called out below. IPs are
corp-DHCP and can move; the current set is in
[`devices.md`](devices.md).

## What auto-starts where

| Device | Service | How it starts | Expected after boot |
|---|---|---|---|
| IQ-9075 | Mosquitto broker (11883 tcp / 19001 ws) | systemd `mosquitto` (config `/etc/mosquitto/conf.d/qnet.conf` = [`infra/mosquitto.conf`](../../infra/mosquitto.conf)) | seconds; both listeners bound |
| IQ-9075 | Gemma 4 E2B on the NPU, `:18181` | systemd `geniex-serve` ([runbook](../../setup/iq9-gemma-geniex/README.md)) | model load takes a while (unmeasured); agent survives it — rails don't need the LLM |
| IQ-9075 | The agent | systemd `qnet-agent` (unit-encoded `After=mosquitto geniex-serve`) | journal shows `connected 127.0.0.1:11883` |
| Ventuno kitchen | Fall detection | systemd `qnet-vision` | heartbeat within ~5 s; fps settles ~2.7 [M] |
| Ventuno kitchen | Look (VLM answers) | systemd `qnet-look` + Docker VLM container (`restart=unless-stopped`) | container may take up to ~2 min to serve `/v1/models` |
| Ventuno kitchen | Frame preview `:8090` | systemd `qnet-stream` | serves once vision exports a frame |
| Ventuno kitchen | Voice node (Whisper ASR + TTS) | Arduino **App Lab app** `qnet-voice-node` — **not** systemd; whether it self-starts after a power cycle is *unverified*. Check, and if needed: `arduino-app-cli app start /home/arduino/ArduinoApps/qnet-voice-node` | app start → both whisper models registered ~10 s later [M, `verify/D3-voice-deploy.txt`]; heartbeat `kitchen-voice-01` state `listening` |
| Ventuno bedroom | Look (owns camera, `--export-every 1`) | systemd `qnet-look` (installed from `qnet-look-bedroom.service`) + Docker VLM container | heartbeat `bedroom-01` state `look-only`, fps ~27 |
| Ventuno bedroom | Frame preview `:8090` | systemd `qnet-stream` | serves look's exported frame |
| Laptop | Dashboard | launch `QNetHome.exe` (or open `dashboard/index.html`) | Settings hub `ws://<IQ9-ip>:19001/mqtt` persists in localStorage |
| Phone | Telegram | nothing to start | t.me/Qnethomebot chat open |

## Boot-order truth

Order does **not** matter across devices: every client (nodes, agent, dashboard)
reconnects to the broker on its own. The one ordering that exists is
unit-encoded on the IQ9 — `qnet-agent.service` carries
`After=mosquitto.service geniex-serve.service` / `Wants=mosquitto.service` —
so a single-board boot sequences itself. Power the three boards in any order.

## Verification sequence (run it every time, ~2 minutes)

From the laptop, in repo root:

```bash
# 1. Per-device service state
ssh iq9      'systemctl is-active mosquitto geniex-serve qnet-agent'   # 3x active
ssh ventuno  'systemctl is-active qnet-vision qnet-look qnet-stream'   # 3x active
ssh ventuno  'arduino-app-cli app list'                                # qnet-voice-node ... running
ssh ventuno2 'systemctl is-active qnet-look qnet-stream'               # 2x active

# 2. THE RIGHT-BROKER CHECK — non-negotiable after any agent restart
ssh iq9 'journalctl -u qnet-agent --no-pager | grep connected | tail -1'
# MUST say 127.0.0.1:11883 — 1883 was the teammate stack
# (verify/INCIDENT-wrong-broker.txt; the standing rules live in troubleshooting.md)

# 3. Heartbeat spy — all three nodes on one topic
.venv/Scripts/python.exe dev/spy.py --broker 10.73.51.175 --port 11883 -t 'qnet/+/status' -C 6
# expect interleaved: kitchen-01 "armed" · kitchen-voice-01 "listening" · bedroom-01 "look-only"

# 4. Camera freshness (shm export is the frame everything shares)
ssh ventuno 'stat -c "%y %s" /dev/shm/qnet_kitchen_frame.jpg; date -u'   # mtime within ~1 s
curl -sI http://10.73.51.123:8090/kitchen.jpg   # HTTP 200, tens of KB
curl -sI http://10.73.51.178:8090/bedroom.jpg   # HTTP 200

# 5. VLM containers answer
ssh ventuno  'curl -s -m 120 http://127.0.0.1:9001/v1/models'   # model listed
ssh ventuno2 'curl -s -m 120 http://127.0.0.1:9001/v1/models'
```

Then the dashboard: Settings → hub `ws://10.73.51.175:19001/mqtt`, click the
kitchen on the map → LIVE preview. The demo-specific half of pre-flight
(composer flag, phone, camera aim, timer pacing) is
[`DEMO.md §1`](../DEMO.md).

## Known cold-start wrinkles

- **First VLM call after container start can come back empty** — retry once
  before suspecting anything else ([troubleshooting](troubleshooting.md#vlm-first-call-returns-empty)).
- **Voice app persistence across reboot is unverified** (deployed 2026-08-06,
  no power cycle observed since) — hence the explicit `app list` check above.
- The IQ9 IP (`10.73.51.175`) is baked into the Ventuno unit files' `ExecStart`
  and the dashboard setting; if DHCP moved it, edit the units + daemon-reload
  (the unit headers say exactly this).
