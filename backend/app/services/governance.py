from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.enums import RecipientType, ReviewDecisionType, ReviewSeverity, RiskLevel
from app.models import ConsentRule
from app.schemas import ProposalDraft, ProposalView, ReviewDraft, StructuredFeedbackItem


REJECTION_CODES = {
    "SAFETY_VIOLATION",
    "MISSING_RED_FLAG",
    "PRIVACY_CONSENT_VIOLATION",
    "WRONG_RECIPIENT",
    "EXCESSIVE_CERTAINTY",
    "INAPPROPRIATE_TONE",
    "INSUFFICIENT_EVIDENCE",
    "POLICY_MISMATCH",
    "OVERLOOKED_ESCALATION",
    "CLINICIAN_SUMMARY_TOO_VERBOSE",
    "CAREGIVER_MESSAGE_TOO_SENSITIVE",
}


def _feedback_item(
    issue_code: str,
    description: str,
    why: str,
    must_fix: str,
    strategy: str,
    evidence: list[str] | None = None,
    forbidden: list[str] | None = None,
    constraints: list[str] | None = None,
) -> StructuredFeedbackItem:
    return StructuredFeedbackItem(
        issue_code=issue_code,
        issue_description=description,
        why_it_matters=why,
        must_fix=must_fix,
        suggested_rewrite_strategy=strategy,
        evidence_to_include=evidence or [],
        forbidden_patterns=forbidden or [],
        target_recipient_constraints=constraints or [],
    )


def _patient_state_has_event(patient_state: dict[str, Any], event_type: str) -> bool:
    return any(item.get("event_type") == event_type for item in patient_state.get("recent_events", []))


def _count_behavioral_status(patient_state: dict[str, Any], event_type: str, status: str) -> int:
    return sum(
        1
        for item in patient_state.get("adherence_events", [])
        if item.get("event_type") == event_type and item.get("payload", {}).get("status") == status
    )


def _caregiver_consent_ok(
    db: Session,
    patient_id: str,
    recipient_id: str | None,
    consent_scope: str,
) -> bool:
    query = db.query(ConsentRule).filter(
        ConsentRule.patient_id == patient_id,
        ConsentRule.recipient_type == RecipientType.CAREGIVER.value,
        ConsentRule.consent_scope == consent_scope,
        ConsentRule.can_share.is_(True),
    )
    if recipient_id:
        query = query.filter(
            (ConsentRule.recipient_user_id.is_(None)) | (ConsentRule.recipient_user_id == recipient_id)
        )
    return query.first() is not None


def _contains_forbidden_diagnostic_tone(content: str) -> bool:
    lowered = content.lower()
    patterns = ["definitely", "you have", "diagnosis", "cured", "no need to worry"]
    return any(pattern in lowered for pattern in patterns)


def evaluate_governance(
    db: Session,
    proposal: ProposalDraft | ProposalView,
    patient_state: dict[str, Any],
) -> ReviewDraft:
    structured_items: list[StructuredFeedbackItem] = []
    issues_found: list[str] = []
    required_changes: list[str] = []
    decision = ReviewDecisionType.APPROVE
    severity = ReviewSeverity.INFORMATIONAL
    review_feedback = "Proposal is safe to release."
    revised_recipient: RecipientType | None = None
    escalation_reason: str | None = None
    block_release = False

    if proposal.target_recipient_type == RecipientType.CAREGIVER and not _caregiver_consent_ok(
        db,
        proposal.patient_id,
        proposal.target_recipient_id,
        proposal.consent_scope_required,
    ):
        decision = ReviewDecisionType.REROUTE
        severity = ReviewSeverity.HIGH
        review_feedback = "Caregiver release blocked due to missing consent. Route to internal queue."
        issues_found.append("PRIVACY_CONSENT_VIOLATION")
        required_changes.append("Do not release caregiver-visible content without matching consent scope.")
        revised_recipient = RecipientType.INTERNAL_QUEUE
        block_release = True
        structured_items.append(
            _feedback_item(
                "PRIVACY_CONSENT_VIOLATION",
                "Caregiver content exceeds available consent.",
                "Sharing without consent can expose sensitive health information.",
                "Change the recipient or remove protected details.",
                "Reroute to an internal nurse or coordinator queue and preserve only operational detail.",
                constraints=["No caregiver-visible sensitive content without consent."],
            )
        )
        return ReviewDraft(
            decision=decision,
            severity=severity,
            issues_found=issues_found,
            review_feedback=review_feedback,
            structured_feedback={"items": [item.model_dump(mode="json") for item in structured_items]},
            required_changes=required_changes,
            revised_target_recipient_type=revised_recipient,
            revised_policy_tags=["consent_blocked"],
            escalation_reason=None,
            require_second_review=True,
            block_release=block_release,
        )

    fall_detected = _patient_state_has_event(patient_state, "fall_detected")
    prolonged_inactivity = _patient_state_has_event(patient_state, "prolonged_inactivity")
    missed_meds = _count_behavioral_status(patient_state, "medication_logging", "missed")
    confusion = "confused" in proposal.content.lower() or any(
        "confused" in item.get("summary", "").lower() for item in patient_state.get("symptoms", [])
    )
    if (fall_detected and prolonged_inactivity) or (confusion and prolonged_inactivity and missed_meds >= 1):
        decision = ReviewDecisionType.ESCALATE
        severity = ReviewSeverity.CRITICAL
        review_feedback = "Normal messaging blocked. Acute risk pattern requires escalation."
        escalation_reason = "Potential acute event from fall/inactivity or confusion cluster."
        issues_found.append("OVERLOOKED_ESCALATION")
        required_changes.append("Create escalation artifact instead of a normal user-facing message.")
        block_release = True
        structured_items.append(
            _feedback_item(
                "OVERLOOKED_ESCALATION",
                "The current proposal underestimates an acute risk combination.",
                "High-risk multimodal patterns should be escalated rather than coached through messaging.",
                "Replace this proposal with an escalation request.",
                "Summarize the acute signals and route to nurse/clinician review.",
                evidence=["fall_detected", "prolonged_inactivity", "missed medication or confusion signal"],
            )
        )
        return ReviewDraft(
            decision=decision,
            severity=severity,
            issues_found=issues_found,
            review_feedback=review_feedback,
            structured_feedback={"items": [item.model_dump(mode="json") for item in structured_items]},
            required_changes=required_changes,
            revised_target_recipient_type=RecipientType.NURSE,
            revised_policy_tags=["acute_risk", "escalation_required"],
            escalation_reason=escalation_reason,
            require_second_review=False,
            block_release=block_release,
        )

    if proposal.target_recipient_type == RecipientType.PATIENT and proposal.estimated_risk_level == RiskLevel.HIGH:
        decision = ReviewDecisionType.ESCALATE
        severity = ReviewSeverity.HIGH
        review_feedback = "High-risk patient-facing coaching is blocked pending escalation."
        issues_found.append("SAFETY_VIOLATION")
        required_changes.append("Escalate to nurse or clinician instead of direct patient coaching.")
        block_release = True

    elif proposal.target_recipient_type == RecipientType.CLINICIAN and len(proposal.content.split()) > 130:
        decision = ReviewDecisionType.REVISE
        severity = ReviewSeverity.CAUTION
        review_feedback = "Clinician summary is too verbose. Condense to signal-focused bullets."
        issues_found.append("CLINICIAN_SUMMARY_TOO_VERBOSE")
        required_changes.append("Limit the summary to key trends, risks, and actions.")
        structured_items.append(
            _feedback_item(
                "CLINICIAN_SUMMARY_TOO_VERBOSE",
                "The summary includes too much narrative detail.",
                "Verbose notes increase clinician scanning time and can bury red flags.",
                "Trim to concise evidence-backed trend statements.",
                "Use short sentences and highlight only changes, risks, adherence, and caregiver observations.",
            )
        )

    elif proposal.target_recipient_type == RecipientType.CAREGIVER and "diagnosis" in proposal.content.lower():
        decision = ReviewDecisionType.REJECT_AND_REGENERATE
        severity = ReviewSeverity.MODERATE
        review_feedback = "Caregiver content is too clinically sensitive. Rewrite as task-oriented guidance."
        issues_found.append("CAREGIVER_MESSAGE_TOO_SENSITIVE")
        required_changes.append("Remove diagnosis-oriented framing and use observable tasks only.")
        structured_items.append(
            _feedback_item(
                "CAREGIVER_MESSAGE_TOO_SENSITIVE",
                "The caregiver message contains diagnosis-style content.",
                "Caregiver communication should remain privacy-bounded and task-oriented.",
                "Rewrite without diagnostic language.",
                "Focus on concrete observations, meal support, mobility safety, and escalation instructions.",
                forbidden=["diagnosis", "definitely has"],
                constraints=["Use observable tasks only."],
            )
        )

    elif _contains_forbidden_diagnostic_tone(proposal.content):
        decision = ReviewDecisionType.REJECT_AND_REGENERATE
        severity = ReviewSeverity.MODERATE
        review_feedback = "Tone and certainty are unsafe for release. Regenerate with uncertainty and non-diagnostic phrasing."
        issues_found.append("EXCESSIVE_CERTAINTY")
        required_changes.append("Remove certainty claims and diagnosis-like language.")
        structured_items.append(
            _feedback_item(
                "EXCESSIVE_CERTAINTY",
                "The message overstates certainty or implies a diagnosis.",
                "In older adult care workflows, overclaiming can mislead recipients and suppress escalation.",
                "Use careful, supportive, non-diagnostic language.",
                "State observations, suggest next steps, and acknowledge when a clinician should review.",
                evidence=[item.get("summary", "") for item in proposal.supporting_evidence[:3]],
                forbidden=["definitely", "you have", "no need to worry"],
            )
        )

    elif proposal.confidence_score > 0.85 and not proposal.supporting_evidence:
        decision = ReviewDecisionType.REJECT_AND_REGENERATE
        severity = ReviewSeverity.CAUTION
        review_feedback = "Confidence is too high for the available evidence."
        issues_found.append("INSUFFICIENT_EVIDENCE")
        required_changes.append("Lower certainty and explicitly cite evidence.")
        structured_items.append(
            _feedback_item(
                "INSUFFICIENT_EVIDENCE",
                "The proposal claims more confidence than the evidence supports.",
                "Weak evidence with high confidence can create unsafe reassurance.",
                "Cite the exact evidence or lower the confidence.",
                "Use direct event references from the patient state and avoid speculation.",
            )
        )

    if decision == ReviewDecisionType.APPROVE:
        severity = ReviewSeverity.INFORMATIONAL if proposal.estimated_risk_level == RiskLevel.LOW else ReviewSeverity.CAUTION
        block_release = False

    return ReviewDraft(
        decision=decision,
        severity=severity,
        issues_found=issues_found,
        review_feedback=review_feedback,
        structured_feedback={"items": [item.model_dump(mode="json") for item in structured_items]},
        required_changes=required_changes,
        revised_target_recipient_type=revised_recipient,
        revised_policy_tags=["reviewed", f"risk:{proposal.estimated_risk_level.value if hasattr(proposal.estimated_risk_level, 'value') else proposal.estimated_risk_level}"],
        escalation_reason=escalation_reason,
        require_second_review=decision != ReviewDecisionType.APPROVE,
        block_release=block_release,
    )
