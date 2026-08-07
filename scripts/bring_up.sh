#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - one command to bring the WHOLE house up (or back up) from the
# laptop. The counterpart to health_check.sh (which verifies but starts
# nothing): this one (re)starts every service on every board, waits out the
# slow loaders, then runs the health check.
# Companion doc (stages, diagnostics explained, USB replug rules):
# scripts/bring_up.md - same name, they go together.
#
#     bash scripts/bring_up.sh                       # use the IPs below
#     bash scripts/bring_up.sh 10.0.0.5 10.0.0.6 10.0.0.7   # iq9 kitchen bedroom
#     QNET_BEDROOM= bash scripts/bring_up.sh         # skip a board (empty = skip)
#     bash scripts/bring_up.sh --dry-run             # print what would run
#
# sudo on the boards prompts for their passwords (interactive on purpose -
# no passwords live in this repo). Expect ~2 minutes end to end: the voice
# app reloads its speech models (~45 s) and the VLM's first answer after a
# start takes ~50 s.

set -uo pipefail

# ---- EDIT THESE (or override with env / arguments) -------------------------
IQ9=${QNET_IQ9:-10.73.51.175}          # the hub (user: ubuntu)
KITCHEN=${QNET_KITCHEN:-10.73.51.123}  # camera+voice room (user: arduino)
BEDROOM=${QNET_BEDROOM:-10.73.51.178}  # look+voice room (user: arduino); empty = skip
PORT=${QNET_PORT:-11883}
# ---------------------------------------------------------------------------

DRY=0
args=()
for a in "$@"; do [[ "$a" == "--dry-run" ]] && DRY=1 || args+=("$a"); done
[[ ${#args[@]} -ge 1 ]] && IQ9=${args[0]}
[[ ${#args[@]} -ge 2 ]] && KITCHEN=${args[1]}
[[ ${#args[@]} -ge 3 ]] && BEDROOM=${args[2]}

SSH="ssh -o ConnectTimeout=10 -t"      # -t: lets the board's sudo prompt you
run() {  # run <label> <target> <command...>
  local label=$1 target=$2; shift 2
  echo "--> [$label] $*"
  [[ $DRY == 1 ]] && return 0
  # shellcheck disable=SC2029
  $SSH "$target" "$*" || echo "    !! [$label] command reported failure - check above, then re-run"
}

echo "=== QNet Home bring-up: hub=$IQ9 kitchen=$KITCHEN bedroom=${BEDROOM:-<skipped>} ==="

echo ""
echo "--- 1/3 The hub (IQ-9075) ---"
run hub "ubuntu@$IQ9" "sudo systemctl restart mosquitto geniex-serve qnet-agent"
if [[ $DRY == 0 ]]; then
  sleep 4
  line=$(ssh -o ConnectTimeout=10 "ubuntu@$IQ9" "journalctl -u qnet-agent --no-pager | grep connected | tail -1" 2>/dev/null || true)
  if [[ "$line" == *"127.0.0.1:$PORT"* ]]; then
    echo "    OK: agent on 127.0.0.1:$PORT"
  else
    echo "    !! agent not on 127.0.0.1:$PORT (got: ${line:-nothing}) - fix config/house.local.yaml on the hub before continuing"
  fi
fi

echo ""
echo "--- 2/3 Kitchen room node ---"
run kitchen "arduino@$KITCHEN" "sudo systemctl restart qnet-vision qnet-look qnet-stream"
run kitchen "arduino@$KITCHEN" "docker start genai-llm-vlm-service 2>/dev/null; arduino-app-cli app restart user:qnet-voice-node"

if [[ -n "$BEDROOM" ]]; then
  echo ""
  echo "--- 3/3 Bedroom room node ---"
  run bedroom "arduino@$BEDROOM" "sudo systemctl restart qnet-look qnet-stream"
  run bedroom "arduino@$BEDROOM" "docker start genai-llm-vlm-service 2>/dev/null; arduino-app-cli app restart user:qnet-voice-node"
else
  echo ""
  echo "--- 3/3 Bedroom: skipped (no IP) ---"
fi

[[ $DRY == 1 ]] && { echo ""; echo "Dry run only - nothing was touched."; exit 0; }

echo ""
echo "Waiting 45 s for the voice apps to reload their speech models..."
sleep 45

# ---- Diagnostics for the failure modes a service restart cannot fix --------
# (each one observed live 2026-08-07; fixes in docs/operations/troubleshooting.md)
echo ""
echo "=== Diagnostics (things a restart can't fix) ==="

check_board() {  # check_board <label> <target> <frame_basename or "">
  local label=$1 target=$2 frame=$3
  # 1. A foreign App Lab app holding the mic/speaker starves OUR voice app
  #    into "failed" (one app owns the audio devices).
  foreign=$(ssh -o ConnectTimeout=8 "$target" \
    'docker ps --format "{{.Names}}" | grep -- "-voice-node-main-1" | grep -v "^qnet-voice-node"' 2>/dev/null)
  [[ -n "$foreign" ]] && echo "  !! [$label] foreign voice app running: $foreign" \
    && echo "     it owns the audio devices - park it: ssh $target 'arduino-app-cli app stop user:<that-app>'"
  # 2. No camera device nodes = the camera needs a PHYSICAL replug (kernel
  #    says 'No valid video chain found' - no software fixes that).
  if [[ -n "$frame" ]]; then
    if ! ssh -o ConnectTimeout=8 "$target" 'ls /dev/v4l/by-id/ 2>/dev/null | grep -q video-index0'; then
      echo "  !! [$label] no camera device nodes (/dev/v4l/by-id empty)"
      echo "     -> physically unplug/replug the USB camera, then: sudo systemctl restart qnet-vision (or qnet-look on an exporter room)"
    # 3. Camera present but the exported frame is stale = the vision/look
    #    process is wedged from before the camera came back - restart it.
    elif ! ssh -o ConnectTimeout=8 "$target" "find /dev/shm/$frame -newermt '-30 seconds' 2>/dev/null | grep -q ."; then
      echo "  !! [$label] camera present but /dev/shm/$frame is stale (>30 s)"
      echo "     -> the capture process is wedged: sudo systemctl restart qnet-vision (kitchen) / qnet-look (bedroom)"
    else
      echo "  ok [$label] camera live, frames fresh"
    fi
  fi
}

check_board kitchen "arduino@$KITCHEN" "qnet_kitchen_frame.jpg"
[[ -n "$BEDROOM" ]] && check_board bedroom "arduino@$BEDROOM" "qnet_bedroom_frame.jpg"

echo ""
echo "=== Verification (scripts/health_check.sh) ==="
QNET_IQ9=$IQ9 QNET_KITCHEN=$KITCHEN QNET_BEDROOM=${BEDROOM:-} QNET_PORT=$PORT \
  bash "$(dirname "$0")/health_check.sh"
status=$?
[[ $status -ne 0 ]] && echo "(A VLM 'not answering' right after bring-up can be the ~50 s first-load - wait a minute and re-run scripts/health_check.sh.)"
exit $status
