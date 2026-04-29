#!/usr/bin/env bash
set -euo pipefail

PY_BIN="${PY_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -d "$VENV_DIR" ]; then
  "$PY_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install -U pip >/dev/null
python -m pip install -r requirements.txt

exec python bot.py
