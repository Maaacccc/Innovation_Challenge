#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd "${BACKEND_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not on PATH"
  exit 1
fi

echo "Starting local Postgres container..."
docker compose up -d postgres

cd "${BACKEND_DIR}"

if [[ ! -d ".venv" ]]; then
  echo "Creating backend virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import fastapi, sqlalchemy, alembic" >/dev/null 2>&1; then
  echo "Installing backend dependencies..."
  pip install -r requirements.txt
fi

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo ".env not found at ${ROOT_DIR}/.env"
  echo "Run: cd ${ROOT_DIR} && cp .env.example .env"
  exit 1
fi

set -a
source "${ROOT_DIR}/.env"
set +a

echo "Running database migrations..."
alembic upgrade head

echo "Starting backend on http://localhost:${BACKEND_PORT:-8000}"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port "${BACKEND_PORT:-8000}"

