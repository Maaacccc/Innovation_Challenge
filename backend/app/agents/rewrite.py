from __future__ import annotations

import re

from app.agents.base import BaseAgent
from app.enums import RecipientType
from app.schemas import ProposalDraft, ProposalView, ReviewDecisionView


class RewriteOrRegenerationAgent(BaseAgent):
    name = "RewriteOrRegenerationAgent"

    def regenerate(
        self,
        proposal: ProposalView,
        review_decision: ReviewDecisionView,
        patient_state: dict,
    ) -> ProposalDraft:
        content = proposal.content
        structured_items = review_decision.structured_feedback.get("items", [])
        for item in structured_items:
            for forbidden in item.get("forbidden_patterns", []):
                content = re.sub(re.escape(forbidden), "", content, flags=re.IGNORECASE)

        if "EXCESSIVE_CERTAINTY" in review_decision.issues_found:
            content = (
                "We noticed a recent change that could be worth checking in on. "
                "Please take the next scheduled step if you feel able, and contact your care team if things feel worse or unclear."
            )

        if "CAREGIVER_MESSAGE_TOO_SENSITIVE" in review_decision.issues_found:
            content = (
                "Task card for today: support meals, note how transfers are going, and log whether sleep disruption continues. "
                "If appetite drops further or walking becomes less steady, update the care team."
            )

        if "CLINICIAN_SUMMARY_TOO_VERBOSE" in review_decision.issues_found:
            evidence_count = len(proposal.supporting_evidence)
            content = (
                f"7-day trend: risk {proposal.estimated_risk_level}; evidence items reviewed {evidence_count}; "
                "key concerns are adherence barriers, mobility decline, sleep change, and caregiver observations."
            )

        content = re.sub(r"\s+", " ", content).strip()
        if not content:
            content = proposal.content

        recipient = review_decision.revised_target_recipient_type or proposal.target_recipient_type
        title = proposal.title
        if recipient == RecipientType.INTERNAL_QUEUE and proposal.target_recipient_type != RecipientType.INTERNAL_QUEUE:
            title = f"Internal review required: {title}"

        return ProposalDraft(
            source_agent=self.name,
            patient_id=proposal.patient_id,
            encounter_context_id=proposal.encounter_context_id,
            target_recipient_type=recipient,
            target_recipient_id=None if recipient == RecipientType.INTERNAL_QUEUE else proposal.target_recipient_id,
            proposal_type=proposal.proposal_type,
            title=title,
            content=content,
            structured_payload={
                **proposal.structured_payload,
                "originating_agent": proposal.source_agent,
                "rewrite_reason": review_decision.decision,
            },
            supporting_evidence=proposal.supporting_evidence,
            confidence_score=min(proposal.confidence_score, 0.78),
            estimated_risk_level=proposal.estimated_risk_level,
            rationale=f"Regenerated from {proposal.id} using structured review feedback.",
            consent_scope_required=proposal.consent_scope_required,
            policy_tags=list(dict.fromkeys([*(proposal.policy_tags or []), "regenerated"])),
            needs_human_review=proposal.needs_human_review,
        )

