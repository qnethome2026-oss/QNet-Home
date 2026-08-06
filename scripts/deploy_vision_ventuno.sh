#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - deploy qnet/node/vision.py to the Ventuno Q and print run lines (T4.2).
#
# Assumes the one-time board prep already done (models/fall-detection/README.md):
#   - ssh alias `ventuno` (key auth, user arduino)
#   - QNN context binary at /data/local/tmp/quad/models/best.bin, qairt-tools installed
#   - venv at ~/qnet-venv with: numpy opencv-python-headless paho-mqtt pyyaml
#
# Usage: sh scripts/deploy_vision_ventuno.sh [ssh-alias]
set -e
BOARD="${1:-ventuno}"
cd "$(dirname "$0")/.."

ssh "$BOARD" "mkdir -p ~/qnet-node/qnet/node ~/qnet-node/config ~/qnet-node/clips ~/qnet-node/dev"
scp qnet/__init__.py qnet/ids.py "$BOARD":qnet-node/qnet/
scp qnet/node/__init__.py qnet/node/vision.py "$BOARD":qnet-node/qnet/node/
scp config/house.yaml config/node.yaml "$BOARD":qnet-node/config/
scp dev/spy.py "$BOARD":qnet-node/dev/
ls clips/*.mp4 >/dev/null 2>&1 && scp clips/*.mp4 "$BOARD":qnet-node/clips/

cat <<'RUN'
Deployed. On the board (broker = the IQ-9075's Mosquitto, verify/T1.1-resolved.txt):

  ssh ventuno
  cd ~/qnet-node
  # live camera:
  ~/qnet-venv/bin/python -m qnet.node.vision --room kitchen \
      --source "v4l2src device=/dev/video0" --broker 10.73.51.175 --port 11883
  # recorded clip (same code path):
  ~/qnet-venv/bin/python -m qnet.node.vision --room kitchen \
      --source "filesrc location=clips/fall-02-cam0-rgb.mp4 ! decodebin" \
      --broker 10.73.51.175 --port 11883
  # watch the bus from anywhere:
  ~/qnet-venv/bin/python dev/spy.py --broker 10.73.51.175 --port 11883 -t 'qnet/kitchen/#'
RUN
