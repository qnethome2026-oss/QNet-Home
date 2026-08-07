#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - one command to bring the WHOLE house up (or back up) from the
# laptop. The counterpart to health_check.sh (which verifies but starts
# nothing): this one (re)starts every service on every board, waits out the
# slow loaders, then runs the health check.
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

echo ""
echo "=== Verification (scripts/health_check.sh) ==="
QNET_IQ9=$IQ9 QNET_KITCHEN=$KITCHEN QNET_BEDROOM=${BEDROOM:-} QNET_PORT=$PORT \
  bash "$(dirname "$0")/health_check.sh"
status=$?
[[ $status -ne 0 ]] && echo "(A VLM 'not answering' right after bring-up can be the ~50 s first-load - wait a minute and re-run scripts/health_check.sh.)"
exit $status
