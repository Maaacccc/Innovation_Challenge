#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

if [[ ! -f "${BACKEND_DIR}/.venv/bin/activate" ]]; then
  echo "Backend virtualenv not found at ${BACKEND_DIR}/.venv"
  echo "Run: cd ${BACKEND_DIR} && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
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

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set in ${ROOT_DIR}/.env"
  exit 1
fi

export OPENAI_ENABLE_LIVE=true

echo "Running live OpenAI smoke test..."
python scripts/live_openai_smoke.py

