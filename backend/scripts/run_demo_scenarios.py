from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./demo_scenarios.db")

from app.core.database import Base, SessionLocal, engine
from app.models import Patient
from app.schemas import EventIngestRequest, OrchestrationRunRequest
from app.seed import seed_demo_data
from app.services.orchestration import Orchestrator
from app.services.state import ingest_event


def _scenario_event(patient_id: str, event: dict, source: str = "scenario-script"):
    return EventIngestRequest(
        patient_id=patient_id,
        encounter_context_id=source,
        source=source,
        event=event,
    )


def run() -> None:
    orchestrator = Orchestrator()
    scenarios = [
        (
            "Scenario 1",
            "a",
            [
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "behavioral",
                        "event_type": "medication_logging",
                        "status": "missed",
                        "recorded_at": datetime.utcnow() - timedelta(days=1),
                        "details": {"slot": "evening"},
                    },
                    "scenario-1a",
                ),
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "behavioral",
                        "event_type": "medication_logging",
                        "status": "missed",
                        "recorded_at": datetime.utcnow(),
                        "details": {"slot": "evening"},
                    },
                    "scenario-1b",
                ),
            ],
            ["medication_adherence"],
            1,
        ),
        (
            "Scenario 2",
            "b",
            [
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "conversational",
                        "event_type": "caregiver_observation_text",
                        "text": "Poor appetite and harder transfers today.",
                        "recorded_at": datetime.utcnow(),
                        "author_role": "caregiver",
                        "details": {},
                    },
                    "scenario-2",
                ),
            ],
            ["caregiver_support"],
            0,
        ),
        (
            "Scenario 3",
            "c",
            [
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "ambient",
                        "event_type": "fall_detected",
                        "severity": "critical",
                        "recorded_at": datetime.utcnow(),
                        "details": {"location": "bedroom"},
                    },
                    "scenario-3a",
                ),
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "ambient",
                        "event_type": "prolonged_inactivity",
                        "severity": "critical",
                        "recorded_at": datetime.utcnow(),
                        "details": {"minutes": 45},
                    },
                    "scenario-3b",
                ),
            ],
            [],
            1,
        ),
        (
            "Scenario 4",
            "a",
            [
                _scenario_event(
                    "__PATIENT__",
                    {
                        "event_category": "behavioral",
                        "event_type": "activity_drop",
                        "status": "decline",
                        "recorded_at": datetime.utcnow(),
                        "details": {"steps_change_pct": -35},
                    },
                    "scenario-4",
                ),
            ],
            ["force_risky_health_coach"],
            0,
        ),
        (
            "Scenario 5",
            "b",
            [],
            ["clinician_summary"],
            None,
        ),
    ]

    for label, patient_key, events, task_hints, trigger_index in scenarios:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_demo_data(db)
            patient_ids = {patient.first_name.lower()[0]: patient.id for patient in db.query(Patient).all()}
            patient_id = patient_ids[patient_key]
            stored_events = []
            for request in events:
                request.patient_id = patient_id
                stored_events.append(ingest_event(db, request))
            db.commit()
            result = orchestrator.run(
                db,
                OrchestrationRunRequest(
                    patient_id=patient_id,
                    trigger_event_id=stored_events[trigger_index].id if trigger_index is not None and stored_events else None,
                    task_hints=task_hints,
                ),
            )
            db.commit()
            print(label)
            for outcome in result.outcomes:
                print(
                    f"  - {outcome.proposal.title}: decision="
                    f"{outcome.latest_review.decision if outcome.latest_review else 'N/A'} "
                    f"source={outcome.proposal.source_agent} "
                    f"version={outcome.proposal.version_number} "
                    f"delivery={'yes' if outcome.delivery else 'no'} "
                    f"escalation={'yes' if outcome.escalation else 'no'}"
                )


if __name__ == "__main__":  # pragma: no cover
    run()
