#!/usr/bin/env bash
set -euo pipefail

qhome_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
qhome_pid_file="$qhome_root/.runtime/iq9-native.pid"
qhome_log_file="$qhome_root/.runtime/iq9-native.log"

if [[ ! -f "$qhome_pid_file" ]]; then
  echo "IQ9 native runtime is not running"
  exit 1
fi

qhome_pid="$(<"$qhome_pid_file")"
if [[ ! "$qhome_pid" =~ ^[0-9]+$ ]] || ! kill -0 "$qhome_pid" 2>/dev/null; then
  echo "IQ9 native runtime is not running"
  exit 1
fi

echo "IQ9 native runtime is running with PID $qhome_pid"
tail -n 30 "$qhome_log_file"
