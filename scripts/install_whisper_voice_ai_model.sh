#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 <ventuno-host-or-ip> <qnn-context-artifact-dir> [model-name]" >&2
  exit 2
fi

qnet_host="$1"
qnet_artifact_dir="${2%/}"
qnet_model_name="${3:-whisper-small}"
qnet_model_slug="${qnet_model_name//-/_}"
qnet_remote_root="/var/lib/arduino-app-cli/models/audio-analytics/asr"
qnet_remote_dir="$qnet_remote_root/${qnet_model_slug}-voice_ai-float-qualcomm_qcs8275"
qnet_tokenizer_dir="$qnet_remote_root/whisper_small_quantized-voice_ai-w8a16-qualcomm_qcs8275"
qnet_stage="/tmp/qnet-${qnet_model_slug}-voice-ai-float"

for qnet_file in encoder.bin decoder.bin metadata.json; do
  if [[ ! -f "$qnet_artifact_dir/$qnet_file" ]]; then
    echo "Missing $qnet_artifact_dir/$qnet_file" >&2
    exit 1
  fi
done

ssh "arduino@$qnet_host" "
  set -eu
  test -f '$qnet_tokenizer_dir/vocab.bin'
  if test -e '$qnet_remote_dir'; then
    echo 'Refusing to overwrite existing model directory: $qnet_remote_dir' >&2
    exit 1
  fi
  # Keep a partial staging directory so a large model transfer can be resumed
  # safely after a Wi-Fi/SSH interruption. rsync validates size and timestamp
  # before the atomic rename into the model registry.
  mkdir -p '$qnet_stage'
"

# Copy the complete artifact so official Voice AI packages retain their
# runtime-authored config.json and vocab.bin. Generic QNN exports contain only
# encoder/decoder/metadata; the Python step below fills those two files in.
rsync -a --progress "$qnet_artifact_dir/" "arduino@$qnet_host:$qnet_stage/"

ssh "arduino@$qnet_host" "QNET_STAGE='$qnet_stage' QNET_DEST='$qnet_remote_dir' QNET_SOURCE_VOCAB='$qnet_tokenizer_dir/vocab.bin' QNET_MODEL_NAME='$qnet_model_name' python3 -" <<'PY'
import json
import os
from pathlib import Path
import shutil

stage = Path(os.environ["QNET_STAGE"])
destination = Path(os.environ["QNET_DEST"])
model_name = os.environ["QNET_MODEL_NAME"]

metadata_path = stage / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
qairt_version = metadata.get("tool_versions", {}).get("qairt", "2.45.0")
qairt_parts = qairt_version.split(".")
qairt_semver = [int(part) for part in qairt_parts[:3]]
while len(qairt_semver) < 3:
    qairt_semver.append(0)
metadata["model_id"] = model_name.replace("-", "_")
metadata["model_name"] = model_name.title()
metadata["runtime"] = "voice_ai"
metadata["precision"] = "float"
metadata["chipset_attributes"] = {
    "aliases": ["qualcomm-qcs8275", "qcs8275"],
    "marketing_name": "Qualcomm QCS8275",
    "world": "IoT",
    "supports_fp16": True,
    "htp_version": 75,
    "soc_model": 82,
    "reference_device": "Dragonwing IQ-8275 EVK",
    "supports_weight_sharing": True,
    "name": "qualcomm-qcs8275",
}
metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

config_path = stage / "config.json"
if not config_path.exists():
    config = {
        "name": model_name,
        "display_name": f"{model_name.title()} (Float/Unquantized)",
        "version": "1.0.0",
        "description": f"{model_name.title()} float16 ASR compiled for Qualcomm HTP",
        "capabilities": {
            "streaming": True,
            "file_based": True,
            "real_time": True,
            "language_detection": True,
            "confidence_scores": False,
        },
        "parameters": {
            "max_file_size_mb": 25,
            "supported_formats": ["wav"],
            "sample_rates": [16000],
        },
        "model_type": "whisper",
        "assets": {
            "encoder_path": "encoder.bin",
            "vocab_path": "vocab.bin",
            "decoder_path": "decoder.bin",
        },
        "runtime": {
            "qnn_version": {
                "major": qairt_semver[0],
                "minor": qairt_semver[1],
                "patch": qairt_semver[2],
            },
            "arch": 64,
        },
    }
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

vocab_path = stage / "vocab.bin"
if not vocab_path.exists():
    shutil.copy2(os.environ["QNET_SOURCE_VOCAB"], vocab_path)

required = ["encoder.bin", "decoder.bin", "vocab.bin", "config.json", "metadata.json"]
for name in required:
    path = stage / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"invalid staged model file: {path}")

stage.rename(destination)
print(destination)
PY

echo "Installed $qnet_model_name on $qnet_host at $qnet_remote_dir"
echo "Restart the Arduino App and confirm the runner lists '$qnet_model_name' before enabling it."
