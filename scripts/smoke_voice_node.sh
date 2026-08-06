#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <iq9-host-or-ip> <target-room>" >&2
  exit 2
fi

qhome_iq9_host="$1"
qhome_target_room="$2"
qhome_message_id="tts-smoke-$(date +%s)"
qhome_now="$(date +%s)"

mosquitto_pub \
  -h "$qhome_iq9_host" \
  -p 1883 \
  -t "qnet/$qhome_target_room/say" \
  -q 1 \
  -m "{\"id\":\"$qhome_message_id\",\"ts\":$qhome_now,\"room\":\"$qhome_target_room\",\"text\":\"QHome text to speech is working.\",\"prio\":\"comfort\"}"

echo "Published targeted TTS test $qhome_message_id to room $qhome_target_room"
