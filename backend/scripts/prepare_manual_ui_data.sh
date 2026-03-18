#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

if [[ ! -f "${BACKEND_DIR}/.venv/bin/activate" ]]; then
  echo "Backend virtualenv not found at ${BACKEND_DIR}/.venv"
  echo "Run the backend start script first."
  exit 1
fi

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo ".env not found at ${ROOT_DIR}/.env"
  echo "Run: cd ${ROOT_DIR} && cp .env.example .env"
  exit 1
fi

cd "${BACKEND_DIR}"
source .venv/bin/activate
set -a
source ../.env
set +a

export OPENAI_ENABLE_LIVE=false

echo "Preparing manual UI data in the configured database..."
python scripts/prepare_manual_ui_data.py

