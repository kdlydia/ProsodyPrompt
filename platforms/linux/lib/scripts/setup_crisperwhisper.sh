#!/usr/bin/env bash
# setup_crisperwhisper.sh
#
# CrisperWhisper is just a HuggingFace model (nyrahealth/CrisperWhisper)
# loaded through the `transformers` pipeline. The model authors recommend
# their fork of `transformers` for the most accurate timestamps:
#   pip install git+https://github.com/nyrahealth/transformers.git@crisper_whisper
#
# So this script:
#   1. Installs torch + transformers (their fork) into the speechprint venv.
#   2. Pre-downloads the model weights so the first run isn't slow.
#
# Pass --plain to use the upstream transformers instead of the nyrahealth fork.

set -euo pipefail

SP_ROOT="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
VENV="$SP_ROOT/.venv"
USE_FORK=1
MODEL_ID="${CRISPERWHISPER_MODEL_ID:-nyrahealth/CrisperWhisper}"

for arg in "$@"; do
    case "$arg" in
        --plain) USE_FORK=0 ;;
        --model=*) MODEL_ID="${arg#--model=}" ;;
    esac
done

if [ ! -d "$VENV" ]; then
    echo "✗ SpeechPrint venv not found at $VENV"
    echo "  Run the main installer first."
    exit 2
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

PIP="$VENV/bin/pip"

echo "Installing torch + transformers …"
"$PIP" install --upgrade "torch>=2.1" || true

if [ "$USE_FORK" = "1" ]; then
    echo "Installing nyrahealth's transformers fork (recommended for crisp timestamps)…"
    "$PIP" install --upgrade \
        "git+https://github.com/nyrahealth/transformers.git@crisper_whisper" \
        || {
            echo "⚠ Fork install failed; falling back to upstream transformers"
            "$PIP" install --upgrade "transformers>=4.40"
        }
else
    "$PIP" install --upgrade "transformers>=4.40"
fi

"$PIP" install --upgrade "accelerate" "huggingface_hub" "soundfile" "librosa"

echo ""
echo "Pre-downloading model: $MODEL_ID"
python - <<PY
from huggingface_hub import snapshot_download
import os
path = snapshot_download(repo_id=os.environ.get("MODEL_ID", "$MODEL_ID"))
print(f"✓ Cached at: {path}")
PY

deactivate || true
echo ""
echo "✓ CrisperWhisper ready (model id: $MODEL_ID)"
