#!/usr/bin/env bash
set -euo pipefail

qhome_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
qhome_venv="$qhome_root/.venv-iq9"
qhome_runtime="$qhome_root/.runtime"

mkdir -p "$qhome_runtime"

if [[ ! -x "$qhome_venv/bin/python" ]]; then
  python3 -m venv --without-pip "$qhome_venv"
fi

if ! "$qhome_venv/bin/python" -m pip --version >/dev/null 2>&1; then
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$qhome_runtime/get-pip.py"
  "$qhome_venv/bin/python" "$qhome_runtime/get-pip.py"
fi

"$qhome_venv/bin/python" -m pip install \
  --disable-pip-version-check \
  -r "$qhome_root/deploy/iq9-native/requirements.txt"

echo "IQ9 native environment is ready: $qhome_venv"
