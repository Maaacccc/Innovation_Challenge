# Prototype Demo Runbook

## Goal

Use the current application as a **functional proof-of-concept** for the innovation challenge.

This runbook gives you a simple, repeatable demo flow.

## Prototype statement

**Prototype title:** Eldercare Multi-Agent Coordination Dashboard

**Prototype type:** Functional proof-of-concept

**Core claim:** The system can ingest care events, coordinate specialized agent outputs, and block or reshape unsafe outputs through mandatory review before delivery.

## What to prepare before the demo

1. Start PostgreSQL with Docker.
2. Start the backend.
3. Prepare demo data.
4. Start the frontend.
5. Keep the slide deck ready as backup.

## Setup commands

### Terminal 1: database

```bash
cd /Users/MacsMacbook/Downloads/DBA5102/Innovation_Challenge
docker compose up -d
```

### Terminal 2: backend

```bash
cd /Users/MacsMacbook/Downloads/DBA5102/Innovation_Challenge/backend
source .venv/bin/activate
set -a
source ../.env
set +a
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 3: prepare demo data

```bash
cd /Users/MacsMacbook/Downloads/DBA5102/Innovation_Challenge
bash backend/scripts/prepare_manual_ui_data.sh
```

### Terminal 4: frontend

```bash
export PATH="/usr/local/opt/node@20/bin:$PATH"
cd /Users/MacsMacbook/Downloads/DBA5102/Innovation_Challenge/frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Demo accounts

All demo users use password `demo1234`.

Recommended accounts:

- `reviewer.w@example.com`
- `caregiver.1@example.com`
- `patient.a@example.com`

## Recommended live demo flow

### Part 1: Explain the problem

Say:

“Eldercare coordination is difficult because events come from many sources, and different stakeholders need different actions and visibility.”

### Part 2: Show reviewer view

Log in as `reviewer.w@example.com`.

Show:

- action-required work
- proposal history
- escalation cases
- human-review queue
- safety metrics

Say:

“Every proposal goes through review before it can be delivered. The system is designed to govern outputs, not just generate them.”

### Part 3: Show caregiver or patient view

Log out and log in as `caregiver.1@example.com` or `patient.a@example.com`.

Show:

- role-specific interface
- caregiver task cards or patient-safe outputs
- limited, scoped visibility
- patient-controlled caregiver sharing options if using patient view

Say:

“Different users see different versions of the same coordination workflow. This is important for privacy and usability.”

### Part 4: Highlight one scenario

Use one of these:

- missed medication
- caregiver observation
- escalation event

Say:

“This scenario shows that the system can transform an event into an auditable, reviewed output instead of sending raw AI content directly.”

### Part 5: Close with the prototype claim

Say:

“This prototype proves that multi-agent coordination in eldercare can be useful while remaining role-aware, reviewable, and safety constrained.”

## Best 3 scenarios to mention

### 1. Missed medication

Value:

- clear user problem
- easy to understand
- easy to show in the dashboard

### 2. Caregiver task card

Value:

- shows different recipient roles
- shows practical task generation
- shows privacy-aware sharing

### 3. Escalation or human review

Value:

- shows governance
- shows why the project is not just another chatbot
- makes the system feel more responsible and healthcare-appropriate

## If the live demo breaks

Fallback plan:

1. Use the slide deck: [project_intro_deck.pptx](/Users/MacsMacbook/Downloads/DBA5102/Innovation_Challenge/docs/project_intro_deck.pptx)
2. Use screenshots from the running app
3. Explain the workflow with the prepared scenarios

## What to say if someone asks “what exactly is the prototype?”

Use this answer:

“The prototype is a functional web application that demonstrates the end-to-end workflow: event ingestion, agent orchestration, safety review, and role-based delivery.”

## What not to claim

Avoid saying the prototype is:

- a clinically validated care system
- production-ready healthcare software
- a compliance-complete product

Safer wording:

“This is a workflow and safety prototype designed to validate the coordination concept.”
