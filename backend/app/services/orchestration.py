from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import TaskContext
from app.agents.rewrite import RewriteOrRegenerationAgent
from app.agents.risk import RiskReviewAgent
from app.agents.task_agents import (
    CareCoordinatorAgent,
    CaregiverSupportAgent,
    ClinicianCopilotAgent,
    DigitalNurseAgent,
    HealthCoachAgent,
    MedicationAdherenceAgent,
)
from app.ai.provider import get_llm_provider
from app.core.config import get_settings
from app.enums import (
    DeliveryChannel,
    HumanReviewStatus,
    ProposalStatus,
    RecipientType,
    ReviewDecisionType,
)
from app.models import (
    DeliveryArtifact,
    EscalationCase,
    HumanReviewCase,
    NormalizedEvent,
    OrchestrationRun,
    Proposal,
    RegenerationAttempt,
    ReviewDecision,
)
from app.schemas import (
    OrchestrationResult,
    OrchestrationRunRequest,
    OrchestrationRunView,
    PatientStateView,
    ProposalDraft,
    ProposalOutcome,
    ProposalView,
    ReviewDecisionView,
)
from app.services.audit import record_audit
from app.services.rendering import render_delivery_artifact
from app.services.state import load_patient_state, rebuild_patient_state


settings = get_settings()


@dataclass
class ReviewLoopResult:
    proposal: Proposal
    latest_review: ReviewDecision | None = None
    delivery: DeliveryArtifact | None = None
    escalation: EscalationCase | None = None
    human_review_case: HumanReviewCase | None = None
    rounds: int = 0


class Orchestrator:
    def __init__(self) -> None:
        provider = get_llm_provider()
        self.coordinator = CareCoordinatorAgent(provider)
        self.nurse = DigitalNurseAgent(provider)
        self.medication = MedicationAdherenceAgent(provider)
        self.coach = HealthCoachAgent(provider)
        self.caregiver = CaregiverSupportAgent(provider)
        self.clinician = ClinicianCopilotAgent(provider)
        self.reviewer = RiskReviewAgent(provider)
        self.rewriter = RewriteOrRegenerationAgent(provider)

    def _select_agents(self, state: PatientStateView, trigger_event: NormalizedEvent | None, task_hints: list[str]):
        agents = []
        event_type = trigger_event.event_type if trigger_event else None
        if event_type in {"medication_logging", "reminder_response"} or "medication_adherence" in task_hints:
            agents.append(self.medication)
        if event_type in {"fall_detected", "prolonged_inactivity", "patient_symptom_text"}:
            agents.append(self.nurse)
        if event_type in {"caregiver_observation_text", "reduced_room_exit_frequency"} or "caregiver_support" in task_hints:
            agents.append(self.caregiver)
        if event_type in {"activity_drop", "sleep_duration", "step_count"} or "health_coach" in task_hints or "force_risky_health_coach" in task_hints:
            agents.append(self.coach)
        if "clinician_summary" in task_hints:
            agents.append(self.clinician)
        if state.current_risk_status != "low" or "care_coordinator" in task_hints:
            agents.append(self.coordinator)
        if not agents:
            agents.append(self.coordinator)
        return agents

    def _create_proposal(
        self,
        db: Session,
        draft: ProposalDraft,
        run_id: str | None,
        parent_proposal_id: str | None = None,
        version_number: int = 1,
    ) -> Proposal:
        proposal = Proposal(
            parent_proposal_id=parent_proposal_id,
            version_number=version_number,
            source_agent=draft.source_agent,
            patient_id=draft.patient_id,
            encounter_context_id=draft.encounter_context_id,
            orchestration_run_id=run_id,
            target_recipient_type=draft.target_recipient_type.value,
            target_recipient_id=draft.target_recipient_id,
            proposal_type=draft.proposal_type.value,
            title=draft.title,
            content=draft.content,
            structured_payload=draft.structured_payload,
            supporting_evidence=draft.supporting_evidence,
            confidence_score=draft.confidence_score,
            estimated_risk_level=draft.estimated_risk_level.value,
            rationale=draft.rationale,
            consent_scope_required=draft.consent_scope_required,
            policy_tags=draft.policy_tags,
            needs_human_review=draft.needs_human_review,
            status=ProposalStatus.DRAFT.value,
        )
        db.add(proposal)
        db.flush()
        record_audit(
            db,
            action="proposal_created",
            actor_type=draft.source_agent,
            detail={"proposal_type": proposal.proposal_type, "version": proposal.version_number},
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            orchestration_run_id=run_id,
        )
        return proposal

    def _create_review(self, db: Session, proposal: Proposal, review_draft) -> ReviewDecision:
        review = ReviewDecision(
            proposal_id=proposal.id,
            decision=review_draft.decision.value,
            severity=review_draft.severity.value,
            issues_found=review_draft.issues_found,
            review_feedback=review_draft.review_feedback,
            structured_feedback=review_draft.structured_feedback,
            required_changes=review_draft.required_changes,
            revised_target_recipient_type=review_draft.revised_target_recipient_type.value
            if review_draft.revised_target_recipient_type
            else None,
            revised_policy_tags=review_draft.revised_policy_tags,
            escalation_reason=review_draft.escalation_reason,
            require_second_review=review_draft.require_second_review,
            block_release=review_draft.block_release,
        )
        db.add(review)
        db.flush()
        record_audit(
            db,
            action="proposal_reviewed",
            actor_type="RiskReviewAgent",
            detail={"decision": review.decision, "severity": review.severity},
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            review_id=review.id,
            orchestration_run_id=proposal.orchestration_run_id,
        )
        return review

    def _deliver(self, db: Session, proposal: Proposal) -> DeliveryArtifact:
        rendered = render_delivery_artifact(proposal)
        delivery = DeliveryArtifact(
            proposal_id=proposal.id,
            recipient_type=proposal.target_recipient_type,
            recipient_id=proposal.target_recipient_id,
            channel=DeliveryChannel.IN_APP.value,
            rendered_title=rendered["rendered_title"],
            rendered_content=rendered["rendered_content"],
            artifact_payload=rendered["artifact_payload"],
        )
        db.add(delivery)
        proposal.status = ProposalStatus.DELIVERED.value
        db.flush()
        record_audit(
            db,
            action="proposal_delivered",
            actor_type="delivery_service",
            detail={"channel": delivery.channel, "recipient_type": delivery.recipient_type},
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            orchestration_run_id=proposal.orchestration_run_id,
        )
        return delivery

    def _escalate(self, db: Session, proposal: Proposal, review: ReviewDecision) -> EscalationCase:
        escalation = EscalationCase(
            proposal_id=proposal.id,
            patient_id=proposal.patient_id,
            reason=review.escalation_reason or review.review_feedback,
            severity=review.severity,
            route_to="nurse_queue" if proposal.target_recipient_type != RecipientType.CLINICIAN.value else "clinician_queue",
            artifact_payload={
                "proposal_title": proposal.title,
                "issues_found": review.issues_found,
                "supporting_evidence": proposal.supporting_evidence,
            },
        )
        db.add(escalation)
        proposal.status = ProposalStatus.ESCALATED.value
        db.flush()
        record_audit(
            db,
            action="escalation_created",
            actor_type="RiskReviewAgent",
            detail={"reason": escalation.reason, "severity": escalation.severity},
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            orchestration_run_id=proposal.orchestration_run_id,
        )
        return escalation

    def _open_human_review(self, db: Session, proposal: Proposal, review: ReviewDecision | None, reason: str) -> HumanReviewCase:
        case = HumanReviewCase(
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            status=HumanReviewStatus.OPEN.value,
            reason=reason,
        )
        db.add(case)
        proposal.needs_human_review = True
        db.flush()
        record_audit(
            db,
            action="human_review_opened",
            actor_type="system",
            detail={"reason": reason, "review_id": review.id if review else None},
            patient_id=proposal.patient_id,
            proposal_id=proposal.id,
            review_id=review.id if review else None,
            orchestration_run_id=proposal.orchestration_run_id,
        )
        return case

    def _loop_review(self, db: Session, proposal: Proposal, patient_state: PatientStateView) -> ReviewLoopResult:
        current = proposal
        rounds = 0
        latest_review = None
        while rounds < settings.max_review_rounds:
            rounds += 1
            current.status = ProposalStatus.UNDER_REVIEW.value
            db.flush()
            proposal_view = ProposalView.model_validate(current)
            review_draft = self.reviewer.review_proposal(db, proposal_view, patient_state.model_dump(mode="json"))
            review = self._create_review(db, current, review_draft)
            latest_review = review
            decision = review.decision

            if decision == ReviewDecisionType.APPROVE.value:
                current.status = ProposalStatus.APPROVED.value
                db.flush()
                delivery = self._deliver(db, current)
                return ReviewLoopResult(
                    proposal=current,
                    latest_review=review,
                    delivery=delivery,
                    rounds=rounds,
                )

            if decision == ReviewDecisionType.ESCALATE.value:
                escalation = self._escalate(db, current, review)
                return ReviewLoopResult(
                    proposal=current,
                    latest_review=review,
                    escalation=escalation,
                    rounds=rounds,
                )

            current.status = (
                ProposalStatus.REROUTED.value
                if decision == ReviewDecisionType.REROUTE.value
                else ProposalStatus.REVISED.value
                if decision == ReviewDecisionType.REVISE.value
                else ProposalStatus.REJECTED.value
            )
            db.flush()

            regenerated_draft = self.rewriter.regenerate(
                ProposalView.model_validate(current),
                ReviewDecisionView.model_validate(review),
                patient_state.model_dump(mode="json"),
            )
            next_proposal = self._create_proposal(
                db,
                regenerated_draft,
                current.orchestration_run_id,
                parent_proposal_id=current.id,
                version_number=current.version_number + 1,
            )
            attempt = RegenerationAttempt(
                prior_proposal_id=current.id,
                proposal_id=next_proposal.id,
                review_decision_id=review.id,
                strategy="reroute" if decision == ReviewDecisionType.REROUTE.value else "rewrite",
                feedback_snapshot=review.structured_feedback,
            )
            db.add(attempt)
            db.flush()
            record_audit(
                db,
                action="proposal_regenerated",
                actor_type="RewriteOrRegenerationAgent",
                detail={"from": current.id, "to": next_proposal.id, "decision": decision},
                patient_id=current.patient_id,
                proposal_id=next_proposal.id,
                review_id=review.id,
                orchestration_run_id=current.orchestration_run_id,
            )
            current = next_proposal

        case = self._open_human_review(
            db,
            current,
            latest_review,
            "Maximum review/regeneration rounds reached without a releasable output.",
        )
        return ReviewLoopResult(
            proposal=current,
            latest_review=latest_review,
            human_review_case=case,
            rounds=rounds,
        )

    def run(self, db: Session, request: OrchestrationRunRequest) -> OrchestrationResult:
        patient_state = load_patient_state(db, request.patient_id)
        trigger_event = db.get(NormalizedEvent, request.trigger_event_id) if request.trigger_event_id else None
        run = OrchestrationRun(
            patient_id=request.patient_id,
            trigger_event_id=request.trigger_event_id,
            status="running",
            summary={},
        )
        db.add(run)
        db.flush()
        record_audit(
            db,
            action="orchestration_started",
            actor_type="orchestrator",
            detail={"task_hints": request.task_hints, "trigger_event_id": request.trigger_event_id},
            patient_id=request.patient_id,
            orchestration_run_id=run.id,
        )
        task_context = TaskContext(
            patient_state=patient_state,
            trigger_event={
                "event_type": trigger_event.event_type,
                "event_category": trigger_event.event_category,
            }
            if trigger_event
            else None,
            task_hints=request.task_hints,
            encounter_context_id=request.encounter_context_id or (trigger_event.encounter_context_id if trigger_event else None),
            now=datetime.utcnow(),
        )
        agents = self._select_agents(patient_state, trigger_event, request.task_hints)
        outcomes: list[ProposalOutcome] = []
        counters = Counter()

        for agent in agents:
            draft = agent.generate_proposal(patient_state, task_context)
            if not draft:
                continue
            proposal = self._create_proposal(db, draft, run.id)
            loop_result = self._loop_review(db, proposal, patient_state)
            outcomes.append(
                ProposalOutcome(
                    proposal=ProposalView.model_validate(loop_result.proposal),
                    latest_review=ReviewDecisionView.model_validate(loop_result.latest_review)
                    if loop_result.latest_review
                    else None,
                    delivery=loop_result.delivery,
                    escalation=loop_result.escalation,
                    human_review_case=loop_result.human_review_case,
                    rounds=loop_result.rounds,
                )
            )
            if loop_result.latest_review:
                counters[loop_result.latest_review.decision] += 1

        run.completed_at = datetime.utcnow()
        run.status = "completed"
        run.summary = {
            "outcomes": len(outcomes),
            "decision_counts": dict(counters),
        }
        db.flush()
        record_audit(
            db,
            action="orchestration_completed",
            actor_type="orchestrator",
            detail=run.summary,
            patient_id=request.patient_id,
            orchestration_run_id=run.id,
        )
        patient_state = rebuild_patient_state(db, request.patient_id)
        return OrchestrationResult(
            run=OrchestrationRunView.model_validate(run),
            patient_state=patient_state,
            outcomes=outcomes,
        )

    def regenerate_from_latest_review(self, db: Session, proposal: Proposal) -> ReviewLoopResult:
        latest_review = (
            db.query(ReviewDecision)
            .filter(ReviewDecision.proposal_id == proposal.id)
            .order_by(ReviewDecision.reviewed_at.desc())
            .first()
        )
        if latest_review is None:
            raise ValueError("No review found for proposal")
        patient_state = load_patient_state(db, proposal.patient_id)
        regenerated = self.rewriter.regenerate(
            ProposalView.model_validate(proposal),
            ReviewDecisionView.model_validate(latest_review),
            patient_state.model_dump(mode="json"),
        )
        next_proposal = self._create_proposal(
            db,
            regenerated,
            proposal.orchestration_run_id,
            parent_proposal_id=proposal.id,
            version_number=proposal.version_number + 1,
        )
        db.add(
            RegenerationAttempt(
                prior_proposal_id=proposal.id,
                proposal_id=next_proposal.id,
                review_decision_id=latest_review.id,
                strategy="manual_regenerate",
                feedback_snapshot=latest_review.structured_feedback,
            )
        )
        db.flush()
        return self._loop_review(db, next_proposal, patient_state)
