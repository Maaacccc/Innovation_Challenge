# Eldercare Multi-Agent Coordination Prototype

Production-style prototype of a multi-agent eldercare and chronic-care coordination system. The system ingests multimodal events, updates a shared patient state, generates agent proposals, and forces every proposal through a centralized `RiskReviewAgent` before any output can be delivered.

## What it demonstrates
- Multimodal normalization for physiological, behavioral, ambient, and conversational inputs.
- Specialized care-team agents that emit immutable proposal versions instead of final outputs.
- Mandatory centralized review with `APPROVE`, `REVISE`, `REROUTE`, `ESCALATE`, and `REJECT_AND_REGENERATE`.
- Rewrite/regeneration loops that create new proposal versions and re-run review.
- Consent, recipient, tone, uncertainty, and escalation governance checks.
- In-app delivery artifacts, escalation cases, human-review queue, and full audit trail.
- FastAPI backend plus a small React/Vite operations dashboard with seeded personas and JWT auth.

## Stack
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL-ready configuration, SQLite-friendly tests.
- Frontend: React 19, Vite, TypeScript, Vitest.
- AI integration: OpenAI Responses API adapter with structured outputs and a deterministic mock path for tests.

## Repo layout
```text
backend/
  app/
    agents/        # task agents, risk review, rewrite/regeneration
    services/      # state projection, governance, orchestration, rendering, metrics
    api/           # FastAPI routes
  tests/
  alembic/
frontend/
```

## Quick start
1. Start Postgres if you want the default local stack:
```bash
docker compose up -d
```
默认把容器暴露到本机 `5433`，这样不会和很多机器上已经在运行的系统 PostgreSQL `5432` 冲突。

2. Set up the backend:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload
```
3. Set up the frontend in a second terminal:
```bash
cd frontend
npm install
npm run dev
```
4. Open `http://localhost:5173`.

### One-command backend start
```bash
cd /Users/shengjiajun/Desktop/IC
bash backend/scripts/start_backend.sh
```

## Seeded users
All seeded users share the password `demo1234`.

- `patient.a@example.com`
- `patient.b@example.com`
- `patient.c@example.com`
- `caregiver.1@example.com`
- `caregiver.2@example.com`
- `reviewer.w@example.com`
- `reviewer.m@example.com`
- `admin@example.com`
- `nurse@example.com`
- `clinician@example.com`

Care-team grouping in the seeded demo:
- patient A + caregiver 1 + reviewer W
- patient B + caregiver 1 + reviewer M
- patient C + caregiver 2 + reviewer W

## Core workflow
1. `POST /api/events/ingest` normalizes an event and rebuilds the patient-state projection.
2. `POST /api/orchestrations/run` selects relevant agents and creates proposal drafts.
3. Each proposal enters the mandatory review loop.
4. The review loop either delivers an approved artifact, creates an escalation case, or opens human review after max rounds.
5. All steps are persisted in proposals, review decisions, regeneration attempts, delivery artifacts, escalations, and audit logs.

## Key endpoints
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/events/ingest`
- `GET /api/patients`
- `GET /api/patients/{id}/state`
- `POST /api/orchestrations/run`
- `GET /api/proposals/{id}`
- `GET /api/patients/{id}/proposals`
- `POST /api/reviews/{proposal_id}/run`
- `POST /api/proposals/{proposal_id}/regenerate`
- `GET /api/escalations`
- `GET /api/audit/{proposal_id}`
- `GET /api/human-review`
- `POST /api/human-review/{id}/resolve`
- `GET /api/metrics/overview`

## Sample API usage
Login:
```bash
curl -s http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"reviewer.w@example.com","password":"demo1234"}'
```

Ingest a missed-medication event:
```bash
curl -s http://localhost:8000/api/events/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "patient_id":"<PATIENT_ID>",
    "encounter_context_id":"scenario-1",
    "source":"demo-script",
    "event":{
      "event_category":"behavioral",
      "event_type":"medication_logging",
      "status":"missed",
      "recorded_at":"2026-03-17T11:00:00Z",
      "details":{"slot":"evening"}
    }
  }'
```

Run orchestration:
```bash
curl -s http://localhost:8000/api/orchestrations/run \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "patient_id":"<PATIENT_ID>",
    "trigger_event_id":"<EVENT_ID>",
    "encounter_context_id":"scenario-1",
    "task_hints":["medication_adherence"]
  }'
```

## Demo scenarios covered
- Scenario 1: missed medication pattern.
- Scenario 2: caregiver task card with consent-aware release.
- Scenario 3: fall plus prolonged inactivity escalation.
- Scenario 4: reject-and-regenerate from risky health-coach language.
- Scenario 5: clinician summary preview and release.

## Tests
Backend:
```bash
cd backend
pytest
```

Frontend:
```bash
cd frontend
npm test
```

## Manual page testing
- Full checklist: [docs/manual_ui_test_plan.md](/Users/shengjiajun/Desktop/IC/docs/manual_ui_test_plan.md)
- Prepare representative dashboard data:
```bash
cd /Users/shengjiajun/Desktop/IC
bash backend/scripts/prepare_manual_ui_data.sh
```

## Frontend modules
- Login screen: only human roles log in. Agents stay in the backend orchestration layer and never appear as frontend identities. The seeded demo now exposes 3 patients, 2 caregivers, and 2 reviewers with scoped patient assignments.
- Patient workspace: only approved patient-facing items, a basic health overview, and an explicit caregiver-sharing control panel where the patient decides whether the caregiver can see task cards, basic overview data, broader updates, or medication-related support.
- Caregiver workspace: patient-approved basic health context, actionable caregiver task cards, and a real observation submission flow that creates new events and orchestration follow-up.
- Reviewer/admin workspace: action-required work first, a clearer decision workspace for approve/reject/escalate actions, then proposal history filtered by recipient role with explicit role responsibilities.

## OpenAI integration
- Live mode is optional and disabled by default.
- Set `OPENAI_API_KEY` and `OPENAI_ENABLE_LIVE=true` in `.env` to enable the OpenAI Responses API adapter.
- The prototype defaults to deterministic generation/review logic when live mode is off so tests remain stable.

### Live smoke test
Manual form:
```bash
cd /Users/shengjiajun/Desktop/IC/backend
source .venv/bin/activate
set -a
source ../.env
set +a
python scripts/live_openai_smoke.py
```

What each step does:
- `cd /Users/.../backend`: switch into the backend project root so relative imports and script paths resolve correctly.
- `source .venv/bin/activate`: activate the backend Python virtual environment so the installed app dependencies are on `PATH`.
- `set -a`: tell the shell to automatically export variables loaded in the next step.
- `source ../.env`: load project environment variables like `OPENAI_API_KEY`, `DATABASE_URL`, and model settings from the repo root `.env`.
- `set +a`: turn off automatic exporting so later shell variables do not leak unintentionally.
- `python scripts/live_openai_smoke.py`: run the live smoke script, which resets a local demo database and executes two OpenAI-backed orchestration scenarios.

Script form:
```bash
cd /Users/shengjiajun/Desktop/IC
bash backend/scripts/run_live_openai_smoke.sh
```

The script:
- activates the backend venv
- loads `.env`
- checks that `OPENAI_API_KEY` exists
- forces `OPENAI_ENABLE_LIVE=true`
- runs `live_openai_smoke.py`

## Notes
- Delivery is in-app only for v1.
- This is a workflow and safety prototype, not a compliance-complete clinical product.
- Seed data is synthetic and intended for demo/testing only.
- If your machine already runs a local PostgreSQL on `5432`, keep the default `.env`/`docker-compose` settings and use `5433` for this project. Only change back to `5432` if you intentionally stop the existing service.
