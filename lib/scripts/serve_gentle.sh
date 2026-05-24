#!/usr/bin/env bash
# serve_gentle.sh
#
# Starts Gentle's HTTP server on localhost:8765. The Python aligner module
# (speechprint_pkg/aligners.py) talks to it over HTTP, so this needs to be
# running before you click Run with Gentle selected.
#
# Auto-detects whether Gentle is installed as Docker or from source, and
# uses whichever works. Runs in the foreground so you see logs; Ctrl+C to
# stop. To run in the background, add `&` or use systemd.

set -euo pipefail

PORT="${GENTLE_PORT:-8765}"
SP_ROOT="${SPEECHPRINT_ROOT:-$HOME/SpeechPrint}"
GENTLE_DIR="$SP_ROOT/external/gentle"

have() { command -v "$1" >/dev/null 2>&1; }

# 1. If we have a source build, use that — it's faster (no container)
if [ -f "$GENTLE_DIR/serve.py" ]; then
    echo "Starting Gentle (source) on http://localhost:$PORT …"
    cd "$GENTLE_DIR"
    exec python3 serve.py --port "$PORT"
fi

# 2. Otherwise, try Docker
if have docker; then
    # Check whether a container is already running on the same port
    existing=$(docker ps --filter "publish=$PORT" --format '{{.ID}}' | head -n1 || true)
    if [ -n "$existing" ]; then
        echo "Gentle Docker container already running: $existing"
        echo "Endpoint: http://localhost:$PORT"
        exit 0
    fi
    echo "Starting Gentle (Docker) on http://localhost:$PORT …"
    exec docker run --rm -p "$PORT:8765" lowerquality/gentle
fi

echo "✗ Neither a source build at $GENTLE_DIR nor Docker is available." >&2
echo "  Run: $SP_ROOT/lib/scripts/setup_gentle.sh" >&2
exit 1
