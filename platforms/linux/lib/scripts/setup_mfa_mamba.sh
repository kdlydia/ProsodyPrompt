#!/usr/bin/env bash
# setup_mfa_mamba.sh
#
# Installs Montreal Forced Aligner via miniforge/mamba into a dedicated env
# named `speechprint-mfa`. MFA depends on Kaldi via the `kalpy` package, and
# `montreal-forced-aligner` only reliably installs through conda-forge.
# Trying `pip install montreal-forced-aligner` into the main venv usually
# leaves kalpy/Kaldi broken, which is what bit us before.
#
# After this script finishes:
#   - mfa binary lives at $HOME/miniforge3/envs/speechprint-mfa/bin/mfa
#   - MFA_ROOT_DIR is at $HOME/.local/share/mfa (acoustic+dict caches go here)
#   - English/German/Spanish/Italian/French/Czech models are pre-downloaded
#
# Idempotent: re-running just updates the env.

set -euo pipefail

PREFIX="${MAMBA_PREFIX:-$HOME/miniforge3}"
ENV_NAME="speechprint-mfa"
LANGS_CSV="${1:-en,de,es,it,fr,cs}"

echo "=== SpeechPrint MFA setup ==="
echo "Install prefix: $PREFIX"
echo "Env name:       $ENV_NAME"
echo "Languages:      $LANGS_CSV"
echo ""

# --- 1. Make sure miniforge is installed -----------------------------------
if [ ! -x "$PREFIX/bin/conda" ]; then
    echo "Installing miniforge3 into $PREFIX …"
    tmp=$(mktemp -d)
    cd "$tmp"
    case "$(uname -m)" in
        x86_64)  ARCH=x86_64 ;;
        aarch64) ARCH=aarch64 ;;
        arm64)   ARCH=aarch64 ;;
        *)       echo "Unsupported arch: $(uname -m)"; exit 1 ;;
    esac
    curl -fsSL -o Miniforge3.sh \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${ARCH}.sh"
    bash Miniforge3.sh -b -p "$PREFIX"
    cd -
    rm -rf "$tmp"
else
    echo "✓ miniforge3 already at $PREFIX"
fi

# shellcheck disable=SC1091
source "$PREFIX/etc/profile.d/conda.sh"

conda config --add channels conda-forge 2>/dev/null || true
conda config --set channel_priority strict 2>/dev/null || true

# --- 2. Create or update the env -------------------------------------------
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "Creating env '$ENV_NAME' (this is slow; one-time)…"
    conda create -y -n "$ENV_NAME" -c conda-forge \
        montreal-forced-aligner \
        kalpy \
        "kaldi=*=cpu*"
else
    echo "Updating env '$ENV_NAME' …"
    conda install -y -n "$ENV_NAME" -c conda-forge \
        montreal-forced-aligner kalpy "kaldi=*=cpu*" \
        --update-deps || true
fi

conda activate "$ENV_NAME"

# --- 3. Smoke test ---------------------------------------------------------
echo ""
echo "=== Smoke test ==="
mfa version
python - <<'PY'
import kalpy, montreal_forced_aligner
print(f"kalpy: {kalpy.__file__}")
print(f"mfa  : {montreal_forced_aligner.__file__}")
PY

# --- 4. Pre-download language models ---------------------------------------
export MFA_ROOT_DIR="${MFA_ROOT_DIR:-$HOME/.local/share/mfa}"
mkdir -p "$MFA_ROOT_DIR"

declare -A LANG_MODEL=(
    [en]=english_mfa [de]=german_mfa [fr]=french_mfa
    [es]=spanish_mfa [it]=italian_mfa [cs]=czech_mfa
    [nl]=dutch_mfa   [pt]=portuguese_mfa [pl]=polish_mfa
)

IFS=',' read -ra LANGS <<< "$LANGS_CSV"
for code in "${LANGS[@]}"; do
    model="${LANG_MODEL[$code]:-${code}_mfa}"
    echo ""
    echo "→ Downloading MFA models for '$code' ($model)…"
    mfa model download acoustic   "$model" || echo "  ⚠ acoustic $model failed (skipping)"
    mfa model download dictionary "$model" || echo "  ⚠ dictionary $model failed (skipping)"
done

echo ""
echo "✓ MFA ready at: $PREFIX/envs/$ENV_NAME/bin/mfa"
echo "  Set MFA_ROOT_DIR=$MFA_ROOT_DIR in your shell rc to persist the model cache."
