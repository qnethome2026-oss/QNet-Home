#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <iq9-host-or-ip> [source-room]" >&2
  exit 2
fi

qhome_iq9_host="$1"
qhome_source_room="${2:-living-room}"
qhome_message_id="smoke-$(date +%s)"
qhome_timestamp="$(date +%s)"

mosquitto_pub \
  -h "$qhome_iq9_host" \
  -p 1883 \
  -t "qnet/$qhome_source_room/ask" \
  -q 1 \
  -m "{\"id\":\"$qhome_message_id\",\"ts\":$qhome_timestamp,\"room\":\"$qhome_source_room\",\"kind\":\"query\",\"text\":\"broadcast that the QHome MQTT path is working\"}"

echo "Published $qhome_message_id to IQ9 at $qhome_iq9_host"
