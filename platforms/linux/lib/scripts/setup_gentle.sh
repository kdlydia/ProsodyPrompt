#!/usr/bin/env bash
# setup_gentle.sh
#
# Installs Gentle (Kaldi-based forced aligner). Two paths:
#
#   1. Docker (recommended): just verify Docker works. Image is
#      `lowerquality/gentle`. Pull it now so first use is fast.
#
#   2. Source build: clone github.com/lowerquality/gentle into
#      $SPEECHPRINT_ROOT/external/gentle and run its install.sh. This
#      builds Kaldi locally — slow (15-30 min on a laptop) and needs a
#      C++ toolchain.
#
# Pass "docker" or "source" as $1, default is auto: docker if available,
# source otherwise.

set -euo pipefail

MODE="${1:-auto}"
SP_ROOT="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
EXTERNAL_DIR="$SP_ROOT/external"
GENTLE_DIR="$EXTERNAL_DIR/gentle"

mkdir -p "$EXTERNAL_DIR"

have() { command -v "$1" >/dev/null 2>&1; }

decide_mode() {
    if [ "$MODE" != "auto" ]; then return; fi
    if have docker; then
        MODE="docker"
    else
        MODE="source"
    fi
}

install_docker() {
    if ! have docker; then
        echo "✗ Docker is not installed. Install docker first, or rerun with: $0 source"
        exit 2
    fi
    echo "Pulling lowerquality/gentle Docker image (this is ~1.5 GB and slow the first time)…"
    docker pull lowerquality/gentle
    echo ""
    echo "✓ Gentle Docker image ready."
    echo "  Start the server with: $SP_ROOT/lib/scripts/serve_gentle.sh"
}

install_source() {
    if [ -d "$GENTLE_DIR/.git" ]; then
        echo "Updating existing Gentle clone at $GENTLE_DIR …"
        git -C "$GENTLE_DIR" pull --ff-only || true
    else
        echo "Cloning Gentle into $GENTLE_DIR …"
        git clone --depth 1 https://github.com/lowerquality/gentle.git "$GENTLE_DIR"
    fi
    cd "$GENTLE_DIR"
    # Gentle's install.sh fetches Kaldi and builds it. Slow.
    if [ -x "./install.sh" ]; then
        echo "Running Gentle's install.sh (this builds Kaldi locally — 15-30 minutes)…"
        ./install.sh
    else
        echo "✗ ./install.sh missing from gentle checkout"
        exit 3
    fi
    echo ""
    echo "✓ Gentle source build complete at $GENTLE_DIR"
    echo "  Start the server with: $SP_ROOT/lib/scripts/serve_gentle.sh"
}

decide_mode
echo "Gentle install mode: $MODE"
case "$MODE" in
    docker) install_docker ;;
    source) install_source ;;
    *) echo "Unknown mode: $MODE"; exit 4 ;;
esac
