#!/usr/bin/env bash
#
# Sets up the venv (first run) and starts the API. Safe to re-run - the venv
# and .env are only created if they're missing.
#
#   ./run.sh              # http://localhost:8000
#   PORT=9000 ./run.sh    # somewhere else
#
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
VENV=".venv"

# The app uses `X | None` type syntax, so 3.10 is a hard floor.
find_python() {
    for py in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$py" >/dev/null 2>&1 &&
            "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            echo "$py"
            return 0
        fi
    done
    return 1
}

# Sets INSTALL_CMD, since a uv-created venv has no pip of its own.
create_venv() {
    if PY=$(find_python); then
        echo "==> Creating $VENV with $($PY --version)"
        "$PY" -m venv "$VENV"
        "$VENV/bin/pip" install --quiet --upgrade pip
        INSTALL_CMD=("$VENV/bin/pip" install --quiet -r requirements.txt)
        return
    fi

    # No system Python new enough (stock macOS ships 3.9). uv can fetch one.
    echo "==> No Python 3.10+ found on PATH."
    UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
    if [ ! -x "$UV" ]; then
        echo "    uv can download a standalone Python 3.12 just for this project."
        read -r -p "    Install uv from https://astral.sh/uv? [y/N] " reply
        case "$reply" in
            [yY]*) curl -LsSf https://astral.sh/uv/install.sh | sh ;;
            *) echo "    Aborting. Install Python 3.10+ and re-run." >&2; exit 1 ;;
        esac
        UV="$HOME/.local/bin/uv"
    fi

    echo "==> Creating $VENV with uv (Python 3.12)"
    "$UV" venv --python 3.12 "$VENV"
    INSTALL_CMD=("$UV" pip install --quiet --python "$VENV/bin/python" -r requirements.txt)
}

if [ ! -d "$VENV" ]; then
    create_venv
    echo "==> Installing dependencies"
    "${INSTALL_CMD[@]}"
fi

if [ ! -f .env ]; then
    echo "==> Creating .env from .env.example"
    cp .env.example .env
fi

echo "==> API on http://localhost:$PORT  (docs at /docs, Ctrl+C to stop)"
exec "$VENV/bin/uvicorn" app.main:app --reload --port "$PORT"
