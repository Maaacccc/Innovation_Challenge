from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./live_smoke.db")

from app.core.database import Base, SessionLocal, engine
from app.models import Patient
from app.schemas import EventIngestRequest, OrchestrationRunRequest
from app.seed import seed_demo_data
from app.services.orchestration import Orchestrator
from app.services.state import ingest_event


def _reset_db() -> dict[str, str]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        db.commit()
        return {patient.first_name.lower()[0]: patient.id for patient in db.query(Patient).all()}


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")
    if os.getenv("OPENAI_ENABLE_LIVE", "false").lower() != "true":
        raise SystemExit("Set OPENAI_ENABLE_LIVE=true to run live smoke tests.")

    orchestrator = Orchestrator()

    patient_ids = _reset_db()
    with SessionLocal() as db:
        first = ingest_event(
            db,
            EventIngestRequest(
                patient_id=patient_ids["a"],
                encounter_context_id="live-s1a",
                source="live-smoke",
                event={
                    "event_category": "behavioral",
                    "event_type": "medication_logging",
                    "status": "missed",
                    "recorded_at": datetime.utcnow() - timedelta(days=1),
                    "details": {"slot": "evening"},
                },
            ),
        )
        second = ingest_event(
            db,
            EventIngestRequest(
                patient_id=patient_ids["a"],
                encounter_context_id="live-s1b",
                source="live-smoke",
                event={
                    "event_category": "behavioral",
                    "event_type": "medication_logging",
                    "status": "missed",
                    "recorded_at": datetime.utcnow(),
                    "details": {"slot": "evening"},
                },
            ),
        )
        db.commit()
        result = orchestrator.run(
            db,
            OrchestrationRunRequest(
                patient_id=patient_ids["a"],
                trigger_event_id=second.id,
                task_hints=["medication_adherence"],
            ),
        )
        db.commit()
        print("Live smoke: scenario 1")
        for outcome in result.outcomes:
            print(f"  - {outcome.proposal.title} -> {outcome.latest_review.decision}")

    patient_ids = _reset_db()
    with SessionLocal() as db:
        event = ingest_event(
            db,
            EventIngestRequest(
                patient_id=patient_ids["a"],
                encounter_context_id="live-s4",
                source="live-smoke",
                event={
                    "event_category": "behavioral",
                    "event_type": "activity_drop",
                    "status": "decline",
                    "recorded_at": datetime.utcnow(),
                    "details": {"steps_change_pct": -35},
                },
            ),
        )
        db.commit()
        result = orchestrator.run(
            db,
            OrchestrationRunRequest(
                patient_id=patient_ids["a"],
                trigger_event_id=event.id,
                task_hints=["force_risky_health_coach"],
            ),
        )
        db.commit()
        print("Live smoke: scenario 4")
        for outcome in result.outcomes:
            print(
                f"  - {outcome.proposal.title} -> {outcome.latest_review.decision} "
                f"(source={outcome.proposal.source_agent}, version={outcome.proposal.version_number})"
            )


if __name__ == "__main__":  # pragma: no cover
    main()
