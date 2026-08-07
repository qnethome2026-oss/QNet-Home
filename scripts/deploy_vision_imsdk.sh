#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - deploy the EXPERIMENTAL IM SDK fall-detection engine (T8.1).
# Installs everything but ENABLES NOTHING: the engine stays behind the flag
# (bash scripts/bring_up.sh --imsdk, or the manual systemctl swap in
# setup/ventuno-imsdk/README.md). Mainline qnet-vision is untouched.
#
# Assumes the usual board prep (setup/guides/03-room-node-ventuno.md): ssh
# access, ~/qnet-venv, model at /data/local/tmp/quad/models/best.bin, and the
# mainline node code deployed (scripts/deploy_vision_ventuno.sh - this engine
# imports qnet.node.vision).
#
# Usage: sh scripts/deploy_vision_imsdk.sh [ssh-target]   # default: ventuno
set -e
BOARD="${1:-ventuno}"
cd "$(dirname "$0")/.."

echo "--> IM SDK GStreamer plugins (board apt repos; sudo will prompt)"
ssh -t "$BOARD" "sudo apt-get install -y \
  gstreamer1.0-plugins-qcom-mlqnn gstreamer1.0-plugins-qcom-mlvconverter \
  gstreamer1.0-plugins-qcom-mlpostprocess gstreamer1.0-plugins-qcom-mlvdetection \
  gstreamer1.0-plugins-qcom-mlmetaparser gstreamer1.0-plugins-bad gstreamer1.0-libav"

echo "--> engine module + unit"
scp qnet/node/vision_imsdk.py "$BOARD":qnet-node/qnet/node/
scp infra/systemd/qnet-vision-imsdk.service "$BOARD":/tmp/
ssh -t "$BOARD" "sudo cp /tmp/qnet-vision-imsdk.service /etc/systemd/system/ && sudo systemctl daemon-reload"

echo "--> verify (element + import), engine left DISABLED"
ssh "$BOARD" "gst-inspect-1.0 qtimlvconverter >/dev/null && ~/qnet-venv/bin/python -c 'import qnet.node.vision_imsdk' && systemctl is-enabled qnet-vision-imsdk.service || true"

cat <<'DONE'
Deployed, not enabled. To run it:
  bash scripts/bring_up.sh --imsdk        # the supported switch (and back: without --imsdk)
Details + clip-based verification: setup/ventuno-imsdk/README.md
DONE
