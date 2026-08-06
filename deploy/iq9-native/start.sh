#!/usr/bin/env bash
set -euo pipefail

qhome_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
qhome_python="$qhome_root/.venv-iq9/bin/python"
qhome_runtime="$qhome_root/.runtime"
qhome_pid_file="$qhome_runtime/iq9-native.pid"
qhome_log_file="$qhome_runtime/iq9-native.log"

mkdir -p "$qhome_runtime"

if [[ ! -x "$qhome_python" ]]; then
  echo "Run deploy/iq9-native/setup.sh first." >&2
  exit 1
fi

if [[ -f "$qhome_pid_file" ]]; then
  qhome_old_pid="$(<"$qhome_pid_file")"
  if [[ "$qhome_old_pid" =~ ^[0-9]+$ ]] && kill -0 "$qhome_old_pid" 2>/dev/null; then
    echo "IQ9 native runtime is already running with PID $qhome_old_pid"
    exit 0
  fi
fi

cd "$qhome_root"
nohup "$qhome_python" -m services.iq9_native.main >"$qhome_log_file" 2>&1 &
qhome_pid="$!"
echo "$qhome_pid" >"$qhome_pid_file"

sleep 2
if ! kill -0 "$qhome_pid" 2>/dev/null; then
  echo "IQ9 native runtime failed to start:" >&2
  tail -n 100 "$qhome_log_file" >&2
  exit 1
fi

echo "IQ9 native runtime started with PID $qhome_pid"
echo "Log: $qhome_log_file"
