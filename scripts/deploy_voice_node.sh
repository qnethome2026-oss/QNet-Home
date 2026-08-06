#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <ventuno-host-or-ip> [remote-app-name]" >&2
  exit 2
fi

qhome_host="$1"
qhome_app_name="${2:-qhome-voice-node}"
qhome_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qhome_source="$qhome_repo_root/apps/ventuno-q/qhome-voice-node/"
qhome_remote="/home/arduino/ArduinoApps/$qhome_app_name"

rsync -az \
  --exclude qhome-config.json \
  "$qhome_source" "arduino@$qhome_host:$qhome_remote/"

echo "Deployed to $qhome_host:$qhome_remote"
echo "Create $qhome_remote/qhome-config.json from qhome-config.example.json, then run:"
echo "  arduino-app-cli app start $qhome_remote"
