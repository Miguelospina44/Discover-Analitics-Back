#!/usr/bin/env bash
# Idempotent dependency setup for the Discover Analytics full stack.
# Runs after the repository is checked out. Safe to run repeatedly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACK_DIR="$(dirname "$SCRIPT_DIR")"
FRONT_DIR="$(dirname "$BACK_DIR")/Discover-Analitics-Front"

echo "==> Installing system packages (PostgreSQL, Python build deps)"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  postgresql postgresql-contrib \
  python3-venv python3-dev build-essential libpq-dev

echo "==> Backend: Python virtualenv + dependencies"
cd "$BACK_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    created backend .env from .env.example"
fi
deactivate

if [ -d "$FRONT_DIR" ]; then
  echo "==> Frontend: npm dependencies"
  cd "$FRONT_DIR"
  npm ci
  if [ ! -f .env.local ]; then
    echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000" > .env.local
    echo "    created frontend .env.local (API on :8000)"
  fi
else
  echo "==> Frontend repo not present at $FRONT_DIR; skipping frontend setup"
fi

echo "==> install.sh complete"
