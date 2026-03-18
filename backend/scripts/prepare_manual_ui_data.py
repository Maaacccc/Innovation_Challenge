from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./manual_ui.db")

from app.core.database import Base, SessionLocal, engine
from app.enums import ProposalType, RecipientType, RiskLevel
from app.models import EscalationCase, HumanReviewCase, Patient, Proposal
from app.schemas import EventIngestRequest, OrchestrationRunRequest, ProposalDraft
from app.seed import seed_demo_data
from app.services.orchestration import Orchestrator
from app.services.state import ingest_event, load_patient_state


def _reset_db() -> dict[str, str]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        db.commit()
        patients = {patient.first_name.lower()[0]: patient.id for patient in db.query(Patient).all()}
        if set(patients) != {"a", "b", "c"}:  # pragma: no cover - defensive
            raise RuntimeError("Expected seeded patients A, B, and C")
        return patients


def _run_event_scenario(
    db,
    orchestrator: Orchestrator,
    patient_id: str,
    events: list[dict],
    task_hints: list[str],
    encounter_prefix: str,
) -> None:
    stored_ids: list[str] = []
    for index, event in enumerate(events, start=1):
        stored = ingest_event(
            db,
            EventIngestRequest(
                patient_id=patient_id,
                encounter_context_id=f"{encounter_prefix}-{index}",
                source="manual-ui-prep",
                event=event,
            ),
        )
        stored_ids.append(stored.id)
    db.commit()
    orchestrator.run(
        db,
        OrchestrationRunRequest(
            patient_id=patient_id,
            trigger_event_id=stored_ids[-1] if stored_ids else None,
            encounter_context_id=encounter_prefix,
            task_hints=task_hints,
        ),
    )
    db.commit()


def _create_human_review_case(db, orchestrator: Orchestrator, patient_id: str) -> None:
    patient_state = load_patient_state(db, patient_id)
    initial = orchestrator._create_proposal(
        db,
        ProposalDraft(
            source_agent="HealthCoachAgent",
            patient_id=patient_id,
            encounter_context_id="manual-human-review",
            target_recipient_type=RecipientType.PATIENT,
            proposal_type=ProposalType.EDUCATION,
            title="Manual reviewer demo case",
            content="This definitely means your condition is worsening and there is no need to worry.",
            structured_payload={"purpose": "manual_ui_human_review"},
            supporting_evidence=[],
            confidence_score=0.95,
            estimated_risk_level=RiskLevel.LOW,
            rationale="Intentionally unsafe content to force human review after max rounds.",
            consent_scope_required="coaching",
            policy_tags=["manual_ui_demo"],
        ),
        run_id=None,
    )

    original_regenerate = orchestrator.rewriter.regenerate

    def same_bad_regeneration(*args, **kwargs):
        return ProposalDraft(
            source_agent="RewriteOrRegenerationAgent",
            patient_id=patient_id,
            encounter_context_id="manual-human-review",
            target_recipient_type=RecipientType.PATIENT,
            proposal_type=ProposalType.EDUCATION,
            title="Manual reviewer demo case",
            content="This definitely means your condition is worsening and there is no need to worry.",
            structured_payload={"purpose": "manual_ui_human_review"},
            supporting_evidence=[],
            confidence_score=0.95,
            estimated_risk_level=RiskLevel.LOW,
            rationale="Intentionally bad regeneration to exhaust review rounds.",
            consent_scope_required="coaching",
            policy_tags=["manual_ui_demo", "regenerated"],
        )

    orchestrator.rewriter.regenerate = same_bad_regeneration
    try:
        orchestrator._loop_review(db, initial, patient_state)
        db.commit()
    finally:
        orchestrator.rewriter.regenerate = original_regenerate


def main() -> None:
    patient_ids = _reset_db()
    orchestrator = Orchestrator()

    with SessionLocal() as db:
        _run_event_scenario(
            db,
            orchestrator,
            patient_ids["a"],
            [
                {
                    "event_category": "behavioral",
                    "event_type": "medication_logging",
                    "status": "missed",
                    "recorded_at": datetime.utcnow() - timedelta(days=1),
                    "details": {"slot": "evening"},
                },
                {
                    "event_category": "behavioral",
                    "event_type": "medication_logging",
                    "status": "missed",
                    "recorded_at": datetime.utcnow(),
                    "details": {"slot": "evening"},
                },
            ],
            ["medication_adherence"],
            "manual-s1",
        )
        print("Prepared scenario 1: missed medication reminder.")

        _run_event_scenario(
            db,
            orchestrator,
            patient_ids["b"],
            [
                {
                    "event_category": "conversational",
                    "event_type": "caregiver_observation_text",
                    "text": "Poor appetite today and transfers looked harder than usual.",
                    "recorded_at": datetime.utcnow(),
                    "author_role": "caregiver",
                    "details": {},
                }
            ],
            ["caregiver_support"],
            "manual-s2",
        )
        print("Prepared scenario 2: caregiver task card.")

        _run_event_scenario(
            db,
            orchestrator,
            patient_ids["c"],
            [
                {
                    "event_category": "conversational",
                    "event_type": "caregiver_observation_text",
                    "text": "Poor appetite overnight and needed extra cueing to get moving this morning.",
                    "recorded_at": datetime.utcnow(),
                    "author_role": "caregiver",
                    "details": {},
                }
            ],
            ["caregiver_support"],
            "manual-s2c",
        )
        print("Prepared caregiver task card for patient C.")

        _run_event_scenario(
            db,
            orchestrator,
            patient_ids["a"],
            [
                {
                    "event_category": "behavioral",
                    "event_type": "activity_drop",
                    "status": "decline",
                    "recorded_at": datetime.utcnow(),
                    "details": {"steps_change_pct": -35},
                }
            ],
            ["force_risky_health_coach"],
            "manual-s4",
        )
        print("Prepared scenario 4: reject-and-regenerate flow.")

        orchestrator.run(
            db,
            OrchestrationRunRequest(
                patient_id=patient_ids["b"],
                encounter_context_id="manual-s5",
                task_hints=["clinician_summary"],
            ),
        )
        db.commit()
        print("Prepared scenario 5: clinician summary.")

        _create_human_review_case(db, orchestrator, patient_ids["b"])
        print("Prepared manual human-review queue item.")

        _run_event_scenario(
            db,
            orchestrator,
            patient_ids["c"],
            [
                {
                    "event_category": "ambient",
                    "event_type": "fall_detected",
                    "severity": "critical",
                    "recorded_at": datetime.utcnow() - timedelta(minutes=6),
                    "details": {"location": "bedroom"},
                },
                {
                    "event_category": "ambient",
                    "event_type": "prolonged_inactivity",
                    "severity": "critical",
                    "recorded_at": datetime.utcnow(),
                    "details": {"minutes": 45},
                },
            ],
            [],
            "manual-s3",
        )
        print("Prepared scenario 3: escalation case.")

        proposal_count = db.query(Proposal).count()
        escalation_count = db.query(EscalationCase).count()
        human_review_count = db.query(HumanReviewCase).count()
        print(
            "Manual UI data ready:",
            f"patient_a={patient_ids['a']}",
            f"patient_b={patient_ids['b']}",
            f"patient_c={patient_ids['c']}",
            f"proposals={proposal_count}",
            f"escalations={escalation_count}",
            f"human_review_cases={human_review_count}",
        )


if __name__ == "__main__":  # pragma: no cover
    main()
