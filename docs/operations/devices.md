# Devices — what runs where

*Back to the [docs index](../README.md). Bring-up from scratch is the
[`setup/`](../../setup/README.md) runbooks; this page is the operating view of
the fleet as deployed. IPs are corp-DHCP and can move — treat them as
"current", not permanent.*

**Credentials are not in this file, deliberately.** Where they live: SSH access
is via aliases in the laptop's `~/.ssh/config` (`iq9`, `ventuno`, `ventuno2` —
key auth provisioned); board user/password tables sit in
[`models/fall-detection/README.md`](../../models/fall-detection/README.md) and
the gitignored `QUAD-Client-main\.env_boards`; the Telegram token + chat ids
live only in `config/house.local.yaml` (gitignored, board-specific — the
handling rules are in
[`troubleshooting.md`](troubleshooting.md#agent-silent--asks-vanish-without-a-journal-trace--wrong-broker)).

## IQ-9075 — the brain (`ssh iq9`, 10.73.51.175)

| What | Detail |
|---|---|
| `mosquitto` | Broker, 11883 tcp / 19001 ws (`/etc/mosquitto/conf.d/qnet.conf`; why non-standard + switch-back: [`infra/mosquitto.conf`](../../infra/mosquitto.conf) header) |
| `geniex-serve` | Gemma 4 E2B (Q4_0) on the Hexagon NPU via GenieX, OpenAI-compatible on `:18181`. Gotchas (the model-cache bug, `pkill -x geniex` not `-f`): [`setup/iq9-gemma-geniex/README.md`](../../setup/iq9-gemma-geniex/README.md) |
| `qnet-agent` | The engine + skills on rails; also the Telegram poller. Unit: [`infra/systemd/qnet-agent.service`](../../infra/systemd/qnet-agent.service). Needs `config/house.local.yaml` beside `house.yaml` (secrets + the board's `mqtt:` block) |
| Hardware | QCS9075, Hexagon HTP v73, Ubuntu 24.04 — details in the [model README](../../models/fall-detection/README.md) |

After any agent restart: the right-broker journal check
([`cold-start.md`](cold-start.md) step 2).

## Ventuno Q — kitchen node (`ssh ventuno`, 10.73.51.123)

The full-capability room: it senses falls, looks, streams, hears and speaks.

| What | Detail |
|---|---|
| `qnet-vision` | Fall detection on the Hexagon NPU (HTP v75), ~2.7 fps [M]. Owns the camera; exports `/dev/shm/qnet_kitchen_frame.jpg` for everyone else |
| `qnet-look` | VLM answers for `qnet/look` — prefers the shm frame, falls back to a direct grab when vision is down |
| `qnet-stream` | LAN-only preview `:8090/kitchen.jpg`; never opens the camera itself |
| VLM container | Qualcomm `genai-llm-vlm-service` (Docker, `restart=unless-stopped`), Qwen VLM on the NPU, `:9001` |
| `qnet-voice-node` | Arduino App Lab app (two containers): Whisper-small ASR on the NPU + Piper TTS, wake-gated. Package: [`apps/ventuno-q/qnet-voice-node/`](../../apps/ventuno-q/qnet-voice-node/); deploy evidence: `verify/D3-voice-deploy.txt` |
| Camera | HHWei UVC — use the stable `/dev/v4l/by-id/usb-HHWei...` path, never `/dev/videoN` (re-enumeration incident, [troubleshooting](troubleshooting.md#camera-offline--preview-dead--vision-active-but-frozen)) |
| Audio | Plantronics Seri headset both ways: mic `usb:2`, speaker `usb:1` (`usb:1` capture is the camera's mic — don't use it) |

## Ventuno Q — bedroom node (`ssh ventuno2`, 10.73.51.178)

Look-only by design: fall detection stays kitchen-only, so there is **no
vision** here. `look.py` owns the camera with `--export-every 1` — it writes
the shm frame `stream.py` serves and publishes the 5 s heartbeat
(state `look-only`).

| What | Detail |
|---|---|
| `qnet-look` | Installed from [`qnet-look-bedroom.service`](../../infra/systemd/qnet-look-bedroom.service) under the canonical name `qnet-look` |
| `qnet-stream` | `:8090/bedroom.jpg`, from [`qnet-stream-bedroom.service`](../../infra/systemd/qnet-stream-bedroom.service) |
| VLM container | Same Qualcomm container, Qwen3-VL-4B on `:9001` (model rsynced board-to-board — `verify/D2-bedroom-node.txt`) |
| Camera | Logitech BRIO, by-id path in the unit file |
| Parked, do not delete | Muni's containers: `genai-llm-vlm-service-muni-parked`, the stopped `qhome-voice-node-*` / `dictation-assistant` containers, `~/ArduinoApps`, and the arduino-app-cli daemon on `:8800` — all deliberately untouched |

## Laptop — Snapdragon X Elite (dev + dashboard)

| What | Detail |
|---|---|
| Dashboard | `dashboard/index.html` or the packaged `QNetHome.exe` / MSIX ([`packaging/`](../../packaging/)); hub setting `ws://10.73.51.175:19001/mqtt` |
| Dev harness | `dev/` — `spy.py` (wire tap), `inject.py` (the sanctioned simulator), `broker.py` + `sim.html` (zero-hardware mode), `replay_session.py` |
| Deploy scripts | [`scripts/`](../../scripts/) — `deploy_vision_ventuno.sh`, `deploy_look_ventuno.sh`, `deploy_voice_node.sh`, `install_whisper_voice_ai_model.sh`, `demo_fallback.sh` (the no-model G2 build). Note: the laptop has no `rsync`; `deploy_voice_node.sh` was replicated with tar-over-ssh (`verify/D3-voice-deploy.txt` §2) |
| Test suite | `.venv/Scripts/python.exe -m pytest -q` — 186 hermetic (+7 live-deselected) |
