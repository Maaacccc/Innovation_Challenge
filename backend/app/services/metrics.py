from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.enums import ReviewDecisionType
from app.models import EscalationCase, Proposal, RegenerationAttempt, ReviewDecision
from app.schemas import MetricsOverview


def get_metrics_overview(db: Session, patient_ids: list[str] | None = None) -> MetricsOverview:
    review_query = db.query(ReviewDecision).join(Proposal, Proposal.id == ReviewDecision.proposal_id)
    proposal_query = db.query(Proposal)
    regeneration_query = db.query(RegenerationAttempt).join(Proposal, Proposal.id == RegenerationAttempt.proposal_id)
    escalation_query = db.query(EscalationCase)

    if patient_ids is not None:
        if not patient_ids:
            return MetricsOverview(
                proposals_approved_directly=0,
                proposals_revised=0,
                proposals_rerouted=0,
                escalations_created=0,
                proposals_rejected_and_regenerated=0,
                average_review_rounds=0.0,
                blocked_unsafe_outputs_count=0,
                recipient_mismatch_caught_by_review=0,
                consent_violations_caught_by_review=0,
            )
        review_query = review_query.filter(Proposal.patient_id.in_(patient_ids))
        proposal_query = proposal_query.filter(Proposal.patient_id.in_(patient_ids))
        regeneration_query = regeneration_query.filter(Proposal.patient_id.in_(patient_ids))
        escalation_query = escalation_query.filter(EscalationCase.patient_id.in_(patient_ids))

    direct_approvals = review_query.filter(ReviewDecision.decision == ReviewDecisionType.APPROVE.value).count()
    revised = review_query.filter(ReviewDecision.decision == ReviewDecisionType.REVISE.value).count()
    rerouted = review_query.filter(ReviewDecision.decision == ReviewDecisionType.REROUTE.value).count()
    escalations = escalation_query.count()
    rejected = (
        review_query
        .filter(ReviewDecision.decision == ReviewDecisionType.REJECT_AND_REGENERATE.value)
        .count()
    )
    regen_count = regeneration_query.count()
    proposal_count = proposal_query.count()
    avg_rounds = round(regen_count / proposal_count, 2) if proposal_count else 0.0
    blocked_outputs = review_query.filter(ReviewDecision.block_release.is_(True)).count()
    recipient_mismatch = (
        review_query
        .filter(func.lower(ReviewDecision.review_feedback).contains("recipient"))
        .count()
    )
    consent_violations = (
        review_query
        .filter(func.lower(ReviewDecision.review_feedback).contains("consent"))
        .count()
    )
    return MetricsOverview(
        proposals_approved_directly=direct_approvals,
        proposals_revised=revised,
        proposals_rerouted=rerouted,
        escalations_created=escalations,
        proposals_rejected_and_regenerated=rejected,
        average_review_rounds=avg_rounds,
        blocked_unsafe_outputs_count=blocked_outputs,
        recipient_mismatch_caught_by_review=recipient_mismatch,
        consent_violations_caught_by_review=consent_violations,
    )
