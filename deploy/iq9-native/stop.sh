#!/usr/bin/env bash
set -euo pipefail

qhome_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
qhome_pid_file="$qhome_root/.runtime/iq9-native.pid"

if [[ ! -f "$qhome_pid_file" ]]; then
  echo "IQ9 native runtime is not running"
  exit 0
fi

qhome_pid="$(<"$qhome_pid_file")"
if [[ ! "$qhome_pid" =~ ^[0-9]+$ ]]; then
  echo "Refusing to use invalid PID file: $qhome_pid_file" >&2
  exit 1
fi

qhome_command="$(ps -p "$qhome_pid" -o command= 2>/dev/null || true)"
if [[ "$qhome_command" != *"services.iq9_native.main"* ]]; then
  echo "PID $qhome_pid is not the QHome IQ9 runtime; refusing to stop it." >&2
  exit 1
fi

kill "$qhome_pid"
rm "$qhome_pid_file"
echo "IQ9 native runtime stopped"
