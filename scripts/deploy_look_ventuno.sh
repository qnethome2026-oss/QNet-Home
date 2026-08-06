#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-or-later
# QNet Home - deploy qnet/node/look.py to the Ventuno Q and print run lines (T6.3).
#
# Sibling of deploy_vision_ventuno.sh and assumes its one-time prep (ssh alias
# `ventuno`, ~/qnet-venv with numpy/opencv/paho/pyyaml + openai). Also assumes
# the node VLM container is up on :9001 (setup/ventuno-vlm/README.md).
# look.py imports parse_source from vision.py, and dev/inject.py needs the
# frozen fixtures - both ship too, so the board can drive itself.
#
# Usage: sh scripts/deploy_look_ventuno.sh [ssh-alias]
set -e
BOARD="${1:-ventuno}"
cd "$(dirname "$0")/.."

ssh "$BOARD" "mkdir -p ~/qnet-node/qnet/node ~/qnet-node/config ~/qnet-node/dev ~/qnet-node/contracts/fixtures"
scp qnet/__init__.py qnet/ids.py "$BOARD":qnet-node/qnet/
scp qnet/node/__init__.py qnet/node/vision.py qnet/node/look.py "$BOARD":qnet-node/qnet/node/
scp config/house.yaml config/node.yaml "$BOARD":qnet-node/config/
scp dev/spy.py dev/inject.py "$BOARD":qnet-node/dev/
scp contracts/fixtures/*.json "$BOARD":qnet-node/contracts/fixtures/

cat <<'RUN'
Deployed. On the board (broker = the IQ-9075's Mosquitto):

  ssh ventuno
  cd ~/qnet-node
  ~/qnet-venv/bin/python -m qnet.node.look --room kitchen \
      --broker 10.73.51.175 --port 11883
  # drive it from anywhere with the fixtures:
  ~/qnet-venv/bin/python dev/inject.py --broker 10.73.51.175 --port 11883 \
      look --object glasses --qid t1
  ~/qnet-venv/bin/python dev/spy.py --broker 10.73.51.175 --port 11883 -t 'qnet/kitchen/looked'
RUN
