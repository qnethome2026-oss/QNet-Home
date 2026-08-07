# Cold start — power on to demo-ready

*Back to the [docs index](../README.md). When a step fails:
[`troubleshooting.md`](troubleshooting.md). Per-device reference:
[`devices.md`](devices.md).*

**The short version: plug everything in, wait ~3 minutes, run one command.**

```
bash scripts/health_check.sh
```

It checks every service, container, camera and heartbeat across all three
boards and prints `ALL GREEN - the house is demo-ready`, or exactly which
check failed and the command that fixes it. It starts nothing and changes
nothing, so it is safe to run at any time — including mid-demo.

Not green? `bash scripts/bring_up.sh <hub-ip> <kitchen-ip> <bedroom-ip>`
(re)starts every service on every board in the right order, waits out the
slow model loads, and re-runs the check. Both scripts take the three IPs as
env vars/arguments — nothing depends on `~/.ssh/config` aliases.

## What comes back by itself (audited 2026-08-06 — every row verified on-device)

| Device | Piece | How it returns |
|---|---|---|
| IQ-9075 | Mosquitto broker, 11883 tcp / 19001 ws | systemd `mosquitto`, enabled (config = [`infra/mosquitto.conf`](../../infra/mosquitto.conf)) |
| IQ-9075 | Gemma 4 E2B on the NPU, `:18181` | systemd `geniex-serve`, enabled ([runbook](../../setup/iq9-gemma-geniex/README.md)) |
| IQ-9075 | The agent | systemd `qnet-agent`, enabled, ordered after the broker |
| Ventuno kitchen | Fall detection | systemd `qnet-vision`, enabled |
| Ventuno kitchen | Look (VLM answers) | systemd `qnet-look`, enabled |
| Ventuno kitchen | Camera preview `:8090` | systemd `qnet-stream`, enabled |
| Ventuno kitchen | Qwen3-VL container | Docker `restart: unless-stopped` |
| Ventuno kitchen | Voice (App Lab app) | systemd `qnet-voice-app`, enabled — *see the audit note* |
| Ventuno bedroom | Look + camera preview | systemd `qnet-look`, `qnet-stream`, enabled |
| Ventuno bedroom | Qwen3-VL container | Docker `restart: unless-stopped` — *see the audit note* |
| Ventuno bedroom | Voice (App Lab app) | systemd `qnet-voice-app`, enabled — *see the audit note* |
| Laptop | Dashboard | open `dashboard/index.html` or the packaged app; hub URL is the built-in default |
| Phones | Telegram | nothing to start |

> **Three gaps the audit found and closed.** They are the kind that only show
> up after a real power cycle, which is why this table is now verified rather
> than assumed:
> 1. the App Lab voice app runs containers with `restart: no`, and the App CLI
>    daemon does **not** restore running apps at boot → added
>    [`qnet-voice-app.service`](../../infra/systemd/qnet-voice-app.service) on
>    both Ventunos (waits 20 s for the daemon, then `app start`);
> 2. the **bedroom** VLM container had no restart policy → set to
>    `unless-stopped` (the kitchen's already had it);
> 3. everything else was genuinely enabled — now proven.

**Boot order does not matter.** Every MQTT client reconnects on its own, so a
node coming up before the broker is fine. The one real dependency — agent after
broker — is encoded in the unit. Rough timings: board services ~30 s, a VLM
container's first model load ~50 s, the voice app's containers + Whisper ~45 s.

## Verifying by hand (what the script automates)

```
ssh iq9      'systemctl is-active mosquitto geniex-serve qnet-agent'    # 3x active
ssh iq9      "journalctl -u qnet-agent --no-pager | grep connected | tail -1"
             # MUST say 127.0.0.1:11883 - anything else, see troubleshooting.md
ssh ventuno  'systemctl is-active qnet-vision qnet-look qnet-stream'    # 3x active
ssh ventuno2 'systemctl is-active qnet-look qnet-stream'                # 2x active
ssh ventuno  'docker ps --format "{{.Names}}"'   # voice main + runner, VLM
ssh ventuno2 'docker ps --format "{{.Names}}"'   # same
curl -o /dev/null -w '%{http_code}\n' http://10.73.51.123:8090/kitchen.jpg   # 200
curl -o /dev/null -w '%{http_code}\n' http://10.73.51.178:8090/bedroom.jpg   # 200
.venv/Scripts/python.exe dev/spy.py --broker 10.73.51.175 --port 11883 -t 'qnet/+/status' -C 6
             # expect 4 nodes: kitchen-01, kitchen-voice-01, bedroom-01, bedroom-voice-01
```

## Then the demo pre-flight

Dashboard hub `ws://10.73.51.175:19001/mqtt` (built-in default), voice-sim
composer on if you want the typed fallback, camera previews pre-filled. Full
run of show: [`../DEMO.md`](../DEMO.md).

## If an IP moved (corp DHCP)

Addresses live in: the Ventuno unit files (`--broker`), each board's
`~/ArduinoApps/qnet-voice-node/qnet-config.json` (`iq9_host`), the IQ9's
`~/qnet-home/config/house.local.yaml` (`mqtt.host` — **edit in place**, never
copy the laptop's), the dashboard's Settings hub URL, and
`scripts/health_check.sh`'s defaults (or export `QNET_IQ9`, `QNET_KITCHEN`,
`QNET_BEDROOM`).
