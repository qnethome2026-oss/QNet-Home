# Ventuno Q — on-node VLM (Qwen3-VL via the Qualcomm container)

*The "eyes" behind `qnet/node/look.py`: an OpenAI-compatible VLM served on each
room node's Hexagon NPU. Brought up on the kitchen board 2026-08-05 and
replicated to the bedroom board 2026-08-06 (full transcript evidence:
`verify/T6.3.txt`, `verify/D2-bedroom-node.txt`). This runbook is the
replication recipe.*

## What runs

| Piece | Value |
|---|---|
| Container | `artifacts.codelinaro.org/iot-solutions-microservices/genai-llm-vlm-service:latest` (~830 MB, public pull) |
| Compose file | `~/docker-compose-qcs8300-ubuntu.yaml` on each board (the "qcs8300" name covers the QCS8275 boards) |
| Endpoint | `http://<board>:9001/v1` — OpenAI chat-completions with base64 image content |
| Model | `qwen3_vl_4b_instruct` (w4a16, NPU). `qwen2_5_vl_7b_instruct` also loadable — swap costs ~1–2 min |
| Models dir | `/home/arduino/models` bind-mounted to `/mnt/work/models` (the 4B model ≈ 4.1 GB) |
| Restart | `unless-stopped` — survives reboot with no keystrokes |

## Replicating to a new board

1. Copy the compose file from a working board (same path).
2. Copy ONLY the needed model subdir board-to-board (LAN direct beats re-downloading):
   `rsync -a --info=progress2 arduino@<src>:/home/arduino/models/<qwen3-subdir>/ /home/arduino/models/<qwen3-subdir>/`
   (~2 min for 4.1 GB on the workshop LAN).
3. `docker compose -f ~/docker-compose-qcs8300-ubuntu.yaml up -d` — first run pulls the image.
4. Verify: `curl -m 120 http://127.0.0.1:9001/v1/models` lists the model. First
   call after a start may be slow or return empty — retry once (model load ≈ 50 s).

## Gotchas (all observed)

- **First call after container start can return empty** — retry; `qnet/node/look.py` does this itself.
- **The NPU is shared** with fall detection (`qnn-net-run`): transient fastrpc
  errors (rc=11 / 1002) appear under contention; every consumer retries.
- Name conflicts when a board has an older parked container: rename the old one
  (e.g. `-muni-parked`), never delete someone else's container.
- Measured (kitchen board): ~3.4 s warm per 640 px image query; look→looked
  round trip median 4.1 s, worst 5.4 s → `find.look_timeout_s: 6`.
- RAM: the 4B model + container fits beside vision/look/stream (and, on the
  kitchen board, the voice app) — measured numbers in `measurements.md`.
