#!/usr/bin/env zsh
# SpeechPrint - macOS CLI wrapper
# Sets up environment, then forwards to the Python pipeline

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

BREW_CMD=""
for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -f "$brew_path" ] && [ -x "$brew_path" ]; then
        BREW_CMD="$brew_path"
        break
    fi
done

if [ -z "${SPEECHPRINT_ROOT:-}" ]; then
    if [ -n "$BREW_CMD" ] && "$BREW_CMD" --prefix speechprint &>/dev/null; then
        SPEECHPRINT_ROOT="$("$BREW_CMD" --prefix speechprint)"
    elif [ -d "$HOME/SpeechPrint" ]; then
        SPEECHPRINT_ROOT="$HOME/SpeechPrint"
    else
        echo "[SpeechPrint ERROR] SPEECHPRINT_ROOT not set and no installation found."
        echo "Set SPEECHPRINT_ROOT environment variable, or run the SpeechPrint installer."
        exit 1
    fi
fi
export SPEECHPRINT_ROOT
export MFA_ROOT_DIR="${MFA_ROOT_DIR:-$SPEECHPRINT_ROOT/mfa}"
export WHISPERX_MODEL="${WHISPERX_MODEL:-large-v3}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -d "$SCRIPT_DIR/templates" ]; then
    TEMPLATES_DIR="$SCRIPT_DIR/templates"
elif [ -d "$HOME/.local/share/speechprint/templates" ]; then
    TEMPLATES_DIR="$HOME/.local/share/speechprint/templates"
elif [ -d "/Library/SpeechPrint/templates" ]; then
    TEMPLATES_DIR="/Library/SpeechPrint/templates"
else
    echo "[SpeechPrint ERROR] Templates not found. Please reinstall SpeechPrint." >&2
    exit 1
fi
export SPEECHPRINT_TEMPLATE_DIR="$TEMPLATES_DIR"

# Activate the venv if it exists
if [ -f "$SPEECHPRINT_ROOT/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$SPEECHPRINT_ROOT/.venv/bin/activate"
fi

# ============================================================================
# UTILITIES
# ============================================================================

usage() {
    cat <<EOF
SpeechPrint - Linguistic Annotation Toolchain

Usage:
  speechprint new <corpus-name> [destination-dir] [options]
  speechprint annotate <wav> --language <code>
  speechprint linguist <wav>
  speechprint ensemble
  speechprint corpus <dir> --language <code>
  speechprint --help

Options for 'new':
  --language <code>  Default corpus language (en, de, it, es, fr, cs)
  --no-vscode        Skip VS Code configuration
  --auto-ensemble    Run ensemble aggregation after each annotate

Environment Variables:
  SPEECHPRINT_ROOT   Override SpeechPrint installation location
  MFA_ROOT_DIR       Montreal Forced Aligner cache (default: \$SPEECHPRINT_ROOT/mfa)
  WHISPERX_MODEL     Default WhisperX model (default: large-v3)
EOF
    exit 0
}

error() {
    echo "[SpeechPrint ERROR] $*" >&2
    exit 1
}

# ============================================================================
# DISPATCH
# ============================================================================

[ "$#" -eq 0 ] && usage
[ "$1" = "--help" ] || [ "$1" = "-h" ] && usage

case "$1" in
    new)
        shift
        # create_corpus.sh is bundled next to this script on macOS
        if [ -f "$SCRIPT_DIR/create_corpus.sh" ]; then
            exec bash "$SCRIPT_DIR/create_corpus.sh" new "$@"
        elif [ -f "/Library/SpeechPrint/scripts/create_corpus.sh" ]; then
            exec bash "/Library/SpeechPrint/scripts/create_corpus.sh" new "$@"
        else
            error "create_corpus.sh not found"
        fi
        ;;
    annotate|linguist|ensemble|transcribe|align|prosody|export|corpus|gui|nmf-corpus|nmf-demo)
        # Hand off to the Python pipeline
        exec python3 -m speechprint_pkg.cli "$@"
        ;;
    --version)
        echo "speechprint 0.3.0"
        ;;
    --config)
        echo "SPEECHPRINT_ROOT: $SPEECHPRINT_ROOT"
        echo "MFA_ROOT_DIR:     $MFA_ROOT_DIR"
        echo "WHISPERX_MODEL:   $WHISPERX_MODEL"
        echo "TEMPLATES_DIR:    $TEMPLATES_DIR"
        ;;
    *)
        error "Unknown command: $1. Run 'speechprint --help'"
        ;;
esac
