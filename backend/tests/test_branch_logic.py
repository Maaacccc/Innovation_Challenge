from __future__ import annotations

from app.enums import ProposalType, RecipientType, RiskLevel, ReviewDecisionType
from app.schemas import ProposalDraft
from app.services.governance import evaluate_governance
from app.services.orchestration import Orchestrator
from app.services.state import load_patient_state
from app.core.database import SessionLocal


def test_consent_violation_is_rerouted(patient_b_id):
    with SessionLocal() as db:
        state = load_patient_state(db, patient_b_id)
        proposal = ProposalDraft(
            source_agent="CaregiverSupportAgent",
            patient_id=patient_b_id,
            target_recipient_type=RecipientType.CAREGIVER,
            target_recipient_id=state.caregiver_relationships[0].caregiver_user_id,
            proposal_type=ProposalType.CAREGIVER_TASK_CARD,
            title="Share sensitive update",
            content="This diagnosis update should go to the caregiver.",
            structured_payload={},
            supporting_evidence=[],
            confidence_score=0.6,
            estimated_risk_level=RiskLevel.MEDIUM,
            rationale="Test draft",
            consent_scope_required="general",
            policy_tags=["test"],
        )
        review = evaluate_governance(db, proposal, state.model_dump(mode="json"))
        assert review.decision == ReviewDecisionType.REROUTE
        assert review.revised_target_recipient_type == RecipientType.INTERNAL_QUEUE


def test_max_rounds_open_human_review(monkeypatch, patient_id):
    orchestrator = Orchestrator()
    with SessionLocal() as db:
        state = load_patient_state(db, patient_id)
        initial = orchestrator._create_proposal(
            db,
            ProposalDraft(
                source_agent="HealthCoachAgent",
                patient_id=patient_id,
                target_recipient_type=RecipientType.PATIENT,
                proposal_type=ProposalType.EDUCATION,
                title="Risky coaching",
                content="This definitely means you have a worsening condition and there is no need to worry.",
                structured_payload={},
                supporting_evidence=[],
                confidence_score=0.95,
                estimated_risk_level=RiskLevel.LOW,
                rationale="Force repeated rejection",
                consent_scope_required="coaching",
                policy_tags=["test"],
            ),
            run_id=None,
        )

        def same_bad_regeneration(*args, **kwargs):
            return ProposalDraft(
                source_agent="RewriteOrRegenerationAgent",
                patient_id=patient_id,
                target_recipient_type=RecipientType.PATIENT,
                proposal_type=ProposalType.EDUCATION,
                title="Still risky",
                content="This definitely means you have a worsening condition and there is no need to worry.",
                structured_payload={},
                supporting_evidence=[],
                confidence_score=0.95,
                estimated_risk_level=RiskLevel.LOW,
                rationale="Still bad",
                consent_scope_required="coaching",
                policy_tags=["test"],
            )

        monkeypatch.setattr(orchestrator.rewriter, "regenerate", same_bad_regeneration)
        result = orchestrator._loop_review(db, initial, state)
        assert result.human_review_case is not None
        assert result.rounds == 3
