#!/usr/bin/env bash
# Codex Lamp hook entrypoint.
# Usage: codex_lamp_hook.sh <working|idle|input|off>
#
# Keep this script quiet and fast. Codex hooks receive JSON on stdin, but this
# hook does not need to parse it because each configured event passes the state
# as argv[1]. It intentionally writes nothing to stdout and always exits 0. 

STATE="${1:-idle}"

PID_FILE="${CODEX_LAMP_PID_FILE:-/tmp/codex_lamp_daemon.pid}"
STATE_FILE="${CODEX_LAMP_STATE_FILE:-/tmp/codex_lamp_state}"
LOG_FILE="${CODEX_LAMP_LOG_FILE:-/tmp/codex_lamp_daemon.log}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DAEMON="${CODEX_LAMP_DAEMON:-$SCRIPT_DIR/codex_lamp_daemon.py}"

log() {
    printf '%s [codex-lamp] %s\n' "$(date '+%H:%M:%S')" "$*" >> "$LOG_FILE" 2>/dev/null || true
}

case "$STATE" in
    working|idle|input|off)
        ;;
    *)
        log "Unknown state '$STATE'; using idle"
        STATE="idle"
        ;;
esac

if ! printf '%s' "$STATE" > "$STATE_FILE" 2>/dev/null; then
    log "Could not write state file: $STATE_FILE"
    exit 0
fi

if [ -f "$PID_FILE" ]; then
    pid="$(cat "$PID_FILE" 2>/dev/null)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        exit 0
    fi
    rm -f "$PID_FILE" 2>/dev/null || true
fi

PYTHON=""

try_python() {
    candidate="$1"
    [ -n "$candidate" ] || return 1

    if command -v "$candidate" >/dev/null 2>&1; then
        "$candidate" -c "import bleak" >/dev/null 2>&1 || return 1
        PYTHON="$candidate"
        return 0
    fi

    if [ -x "$candidate" ]; then
        "$candidate" -c "import bleak" >/dev/null 2>&1 || return 1
        PYTHON="$candidate"
        return 0
    fi

    return 1
}

try_python "${CODEX_LAMP_PYTHON:-}" ||
    try_python "python3" ||
    try_python "/opt/homebrew/bin/python3" ||
    { [ -n "$CONDA_PREFIX" ] && try_python "$CONDA_PREFIX/bin/python3"; }

if [ -z "$PYTHON" ]; then
    log "No Python with bleak found; install with: python3 -m pip install bleak"
    exit 0
fi

if [ ! -f "$DAEMON" ]; then
    log "Daemon not found: $DAEMON"
    exit 0
fi

nohup "$PYTHON" "$DAEMON" </dev/null >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE" 2>/dev/null || true

exit 0
