#!/usr/bin/env sh
set -eu

FULLSTACK_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$FULLSTACK_DIR/.pytest-venv"

python -m venv "$VENV_DIR"
if [ -f "$VENV_DIR/Scripts/activate" ]; then
  . "$VENV_DIR/Scripts/activate"
else
  . "$VENV_DIR/bin/activate"
fi

if [ "${TABLEPAY_SKIP_PIP_INSTALL:-0}" != "1" ]; then
  python -m pip install --upgrade pip
  python -m pip install -r "$FULLSTACK_DIR/backend/requirements.txt"
fi

export PYTHONPATH="$FULLSTACK_DIR/backend"
export FLASK_ENV=test

cd "$FULLSTACK_DIR"
printf '%s\n' "== Running unit tests =="
python -m pytest backend/unit_tests -q

printf '%s\n' "== Running API tests =="
python -m pytest backend/API_tests -q

printf '%s\n' "== Running frontend route tests =="
python -m pytest frontend/API_tests -q

printf '%s\n' "== Running frontend unit tests =="
python -m pytest frontend/unit_tests -q
