#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
#
# Gate G2 - the fallback demo, start to finish, in one command.
#
#   scripts/demo_fallback.sh                 # real time: ~50 s of incident
#   QNET_TIMER_SCALE=0.05 scripts/demo_fallback.sh   # the same incident in ~5 s
#
# Starts the dev broker and the agent (--no-llm: phases, timers and canned lines,
# no model anywhere), replays the silence scenario through dev/inject.py, and
# asserts what came back on the bus and what landed on disk. Prints PASS or FAIL,
# and kills everything it started on the way out.
#
# Nothing here is mocked: a real broker, the real agent process, the real tool
# registry. Telegram falls back to console + data/outbox/telegram.log while
# config/house.yaml still says TODO (T0.5), which is why the notification check
# accepts either channel - it asserts the message was produced, not delivered.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

SCALE="${QNET_TIMER_SCALE:-1}"
ROOM="${QNET_ROOM:-kitchen}"
PY=".venv/Scripts/python"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

WORK="data/demo"
LOGS="$WORK/logs"
SESSIONS="$WORK/sessions"
CONFIG="$WORK/house.yaml"
rm -rf "$WORK"
mkdir -p "$LOGS" "$SESSIONS"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null
  done
  sleep 0.5
  for pid in "${PIDS[@]:-}"; do
    kill -9 "$pid" 2>/dev/null
  done
}
trap cleanup EXIT INT TERM

FAILURES=0
check() { # check <name> <0|1>
  if [ "$2" -eq 0 ]; then
    echo "  [x] $1"
  else
    echo "  [ ] $1"
    FAILURES=$((FAILURES + 1))
  fi
}

echo "=== G2 fallback demo ==================================================="
echo "timer scale : $SCALE   (fall.md's 30 s/15 s ladder -> $($PY -c "print(30*$SCALE, 15*$SCALE)"))"
echo "room        : $ROOM"
echo "work dir    : $WORK"
echo

# The demo runs against its own copy of the config so a demo never writes into
# the sessions a real incident would have written.
"$PY" - "$CONFIG" "$SESSIONS" <<'PYEOF' || exit 1
import sys, yaml
config = yaml.safe_load(open("config/house.yaml", encoding="utf-8"))
config.setdefault("storage", {})["sessions_dir"] = sys.argv[2]
config.setdefault("storage", {})["skills_dir"] = "skills"
yaml.safe_dump(config, open(sys.argv[1], "w", encoding="utf-8"), allow_unicode=True)
PYEOF

wait_for_port() {
  "$PY" - "$1" <<'PYEOF'
import socket, sys, time
deadline = time.time() + 20
while time.time() < deadline:
    try:
        socket.create_connection(("127.0.0.1", int(sys.argv[1])), 1).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.2)
sys.exit(1)
PYEOF
}

echo "--- starting broker, agent and bus spy ---------------------------------"
# Refuse to run against somebody else's broker: if 1883 is already held, our own
# broker dies on bind and everything below would quietly test a foreign process.
if "$PY" -c "import socket,sys; socket.create_connection(('127.0.0.1',1883),1).close()" 2>/dev/null; then
  echo "  port 1883 is already in use - stop the other broker first (this demo starts its own)."
  exit 1
fi
"$PY" dev/broker.py >"$LOGS/broker.log" 2>&1 &
BROKER_PID=$!
PIDS+=("$BROKER_PID")
wait_for_port 1883 || { echo "broker did not come up"; sed 's/^/  /' "$LOGS/broker.log"; exit 1; }
kill -0 "$BROKER_PID" 2>/dev/null || { echo "broker exited during startup"; sed 's/^/  /' "$LOGS/broker.log"; exit 1; }

"$PY" -m qnet.agent --config "$CONFIG" --no-llm --timer-scale "$SCALE" >"$LOGS/agent.log" 2>&1 &
PIDS+=($!)
"$PY" dev/spy.py >"$LOGS/bus.log" 2>&1 &
PIDS+=($!)

# Both clients are connected once the agent has said so in its own log.
for _ in $(seq 1 100); do
  grep -q "connected 127.0.0.1:1883" "$LOGS/agent.log" && break
  sleep 0.2
done
grep -q "connected 127.0.0.1:1883" "$LOGS/agent.log" || { echo "agent did not connect"; cat "$LOGS/agent.log"; exit 1; }
sleep 0.5
echo "ok"
echo

echo "--- the incident: a fall, then silence ---------------------------------"
"$PY" dev/inject.py fall --room "$ROOM" | sed 's/^/  inject > /'

# The person says nothing at all; the node keeps reporting listen timeouts.
LADDER=$("$PY" -c "print(45*$SCALE + 3)")
END=$("$PY" -c "import time; print(time.time() + $LADDER)")
while [ "$("$PY" -c "import time; print(1 if time.time() < $END else 0)")" = "1" ]; do
  "$PY" dev/inject.py heard --room "$ROOM" --silence >/dev/null
  sleep "$($PY -c "print(max(0.3, 10*$SCALE))")"
done
sleep 1
echo "  (silence held for ${LADDER}s of wall clock)"
echo

echo "--- what the bus and the disk say --------------------------------------"
SESSION_FILE=$(ls -1 "$SESSIONS"/${ROOM}__fall-response__*.jsonl 2>/dev/null | tail -1)
if [ -z "$SESSION_FILE" ]; then
  echo "  no session file in $SESSIONS - the agent never opened a session"
  FAILURES=$((FAILURES + 1))
else
  echo "  session file: $SESSION_FILE"
  sed 's/^/    /' "$SESSION_FILE"
fi
echo

# 1. the room was spoken to, starting with the canned opening
grep -q "qnet/$ROOM/say" "$LOGS/bus.log"; check "say seen on qnet/$ROOM/say" $?
grep -q "I saw you fall" "$LOGS/bus.log"; check "the canned opening was spoken first" $?

# 2. the caregiver notification fired (engine on_enter, never the model)
grep -q '"tool": "notify_contacts"' "$SESSION_FILE" 2>/dev/null; check "notify_contacts fired (session log)" $?
{ grep -q "notify_contacts:console" "$LOGS/agent.log" || test -s data/outbox/telegram.log; }
check "notification rendered (console marker or data/outbox/telegram.log)" $?

# 3. the emergency call fired, and is unmistakably simulated (DESIGN §14)
grep -q '"tool": "call_emergency"' "$SESSION_FILE" 2>/dev/null; check "call_emergency fired" $?
{ grep -qi "SIMULATED" "$SESSION_FILE" 2>/dev/null || ls data/outbox/emergency_*.json >/dev/null 2>&1; }
check "SIMULATED emergency payload rendered" $?

# 4. the session file is the whole timeline, in order
grep -q '"event": "detected"' "$SESSION_FILE" 2>/dev/null; check "session file: detected line" $?
grep -q '"from": "check", "to": "escalate"' "$SESSION_FILE" 2>/dev/null; check "session file: check -> escalate" $?
grep -q '"from": "escalate", "to": "call_help"' "$SESSION_FILE" 2>/dev/null; check "session file: escalate -> call_help" $?
grep -q "I'm calling emergency services now" "$SESSION_FILE" 2>/dev/null; check "session file: call_help opening spoken" $?
"$PY" -c "import json,sys; [json.loads(l) for l in open(sys.argv[1], encoding='utf-8') if l.strip()]" "$SESSION_FILE" 2>/dev/null
check "session file: every line is valid JSON" $?

# 5. the same stream went out live for the dashboard
grep -q "qnet/session/" "$LOGS/bus.log"; check "session document published to qnet/session/<id>" $?

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "=== PASS ==============================================================="
  exit 0
fi
echo "=== FAIL ($FAILURES check(s)) =========================================="
echo "logs: $LOGS/agent.log  $LOGS/bus.log  $LOGS/broker.log"
exit 1
