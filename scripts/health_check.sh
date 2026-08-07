#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - one-command health check for the whole house (cold-start gate).
# Run from the laptop with the repo checked out and its venv present:
#     bash scripts/health_check.sh
# Exits non-zero if anything a demo needs is down. Read-only: starts nothing,
# changes nothing.
set -uo pipefail

IQ9=${QNET_IQ9:-10.73.51.175}
KITCHEN=${QNET_KITCHEN:-10.73.51.123}
BEDROOM=${QNET_BEDROOM:-10.73.51.178}
PORT=${QNET_PORT:-11883}
PY=${QNET_PY:-.venv/Scripts/python.exe}
# ssh by user@IP so the env/arg IPs above are the single source of truth -
# no dependency on ~/.ssh/config aliases when an address moves.
SSH_IQ9="ubuntu@$IQ9"
SSH_KITCHEN="arduino@$KITCHEN"
SSH_BEDROOM="arduino@$BEDROOM"
fails=0
ok()   { printf '  [x] %s\n' "$1"; }
bad()  { printf '  [ ] %s  <-- FIX: %s\n' "$1" "$2"; fails=$((fails+1)); }

echo "=== QNet Home health check ==============================="

echo "--- IQ-9075 (the brain) ---"
if out=$(ssh -o ConnectTimeout=8 "$SSH_IQ9" 'systemctl is-active mosquitto geniex-serve qnet-agent | tr "\n" " "' 2>/dev/null); then
  [[ "$out" == *"active active active"* ]] && ok "mosquitto + geniex-serve + qnet-agent active" \
    || bad "IQ9 services: $out" "ssh iq9 'sudo systemctl start mosquitto geniex-serve qnet-agent'"
else bad "IQ9 unreachable over ssh" "check power/network, then ssh iq9"; fi
if line=$(ssh -o ConnectTimeout=8 "$SSH_IQ9" "journalctl -u qnet-agent --no-pager | grep connected | tail -1" 2>/dev/null); then
  [[ "$line" == *"127.0.0.1:$PORT"* ]] && ok "agent on OUR broker (:$PORT)" \
    || bad "agent connected elsewhere: $line" "board house.local.yaml needs mqtt.port $PORT (verify/INCIDENT-wrong-broker.txt)"
fi

echo "--- Ventuno kitchen (fall + look + stream + voice) ---"
if out=$(ssh -o ConnectTimeout=8 "$SSH_KITCHEN" 'systemctl is-active qnet-vision qnet-look qnet-stream | tr "\n" " "' 2>/dev/null); then
  [[ "$out" == *"active active active"* ]] && ok "vision + look + stream active" \
    || bad "kitchen services: $out" "ssh ventuno 'sudo systemctl start qnet-vision qnet-look qnet-stream'"
else bad "kitchen board unreachable" "check power/network"; fi
ssh -o ConnectTimeout=8 "$SSH_KITCHEN" 'docker ps --format "{{.Names}}" | grep -q qnet-voice-node-main' 2>/dev/null \
  && ok "voice app containers up" || bad "kitchen voice app down" "ssh ventuno 'arduino-app-cli app start user:qnet-voice-node'"
code=$(curl -s -o /dev/null -m 8 -w "%{http_code}" "http://$KITCHEN:8090/kitchen.jpg" || true)
[[ "$code" == "200" ]] && ok "kitchen camera preview serving" || bad "kitchen preview HTTP $code" "restart qnet-vision then qnet-stream"

echo "--- Ventuno bedroom (look + stream + voice) ---"
if out=$(ssh -o ConnectTimeout=8 "$SSH_BEDROOM" 'systemctl is-active qnet-look qnet-stream | tr "\n" " "' 2>/dev/null); then
  [[ "$out" == *"active active"* ]] && ok "look + stream active" \
    || bad "bedroom services: $out" "ssh ventuno2 'sudo systemctl start qnet-look qnet-stream'"
else bad "bedroom board unreachable" "check power/network"; fi
ssh -o ConnectTimeout=8 "$SSH_BEDROOM" 'curl -s -m 20 http://127.0.0.1:9001/v1/models | grep -q qwen' 2>/dev/null \
  && ok "bedroom VLM serving qwen3-vl" || bad "bedroom VLM not answering" "ssh ventuno2 'docker start genai-llm-vlm-service' (first call after start can be slow)"
ssh -o ConnectTimeout=8 "$SSH_BEDROOM" 'docker ps --format "{{.Names}}" | grep -q qnet-voice-node-main' 2>/dev/null \
  && ok "voice app containers up" || bad "bedroom voice app down" "ssh ventuno2 'arduino-app-cli app start user:qnet-voice-node'"

echo "--- the wire (what the dashboard sees) ---"
beats=$("$PY" dev/spy.py --broker "$IQ9" --port "$PORT" -t 'qnet/+/status' -C 6 2>/dev/null | grep -o '"node": *"[^"]*"' | sort -u | wc -l || echo 0)
[[ "$beats" -ge 3 ]] && ok "$beats distinct nodes heartbeating (expect 4: kitchen vision+voice, bedroom look+voice)" \
  || bad "only $beats node(s) heartbeating" "see the per-board checks above"

echo "=========================================================="
if [[ $fails -eq 0 ]]; then echo "ALL GREEN - the house is demo-ready."; else echo "$fails CHECK(S) FAILED - fix above, re-run."; fi
exit $fails
