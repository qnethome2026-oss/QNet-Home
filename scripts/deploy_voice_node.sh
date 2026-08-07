#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - a privacy-first, multi-device home safety system.
# Copyright (C) 2026 QNet Home contributors. This is free software under the
# GNU Affero General Public License v3 or later, with ABSOLUTELY NO WARRANTY.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <ventuno-host-or-ip> [remote-app-name]" >&2
  exit 2
fi

qnet_host="$1"
qnet_app_name="${2:-qnet-voice-node}"
qnet_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qnet_source="$qnet_repo_root/apps/ventuno-q/qnet-voice-node/"
qnet_remote="/home/arduino/ArduinoApps/$qnet_app_name"

rsync -az \
  --exclude qnet-config.json \
  "$qnet_source" "arduino@$qnet_host:$qnet_remote/"

echo "Deployed to $qnet_host:$qnet_remote"
echo "Create $qnet_remote/qnet-config.json from qnet-config.example.json, then run:"
echo "  arduino-app-cli app start $qnet_remote"
