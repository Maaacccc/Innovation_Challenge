from __future__ import annotations

from app.enums import RecipientType
from app.models import Proposal


def render_delivery_artifact(proposal: Proposal) -> dict:
    prefix_map = {
        RecipientType.PATIENT.value: "For you",
        RecipientType.CAREGIVER.value: "Caregiver task card",
        RecipientType.CLINICIAN.value: "Clinician summary",
        RecipientType.NURSE.value: "Nurse queue note",
        RecipientType.INTERNAL_QUEUE.value: "Internal coordination note",
    }
    prefix = prefix_map.get(proposal.target_recipient_type, "Care team output")
    return {
        "rendered_title": f"{prefix}: {proposal.title}",
        "rendered_content": proposal.content,
        "artifact_payload": {
            "proposal_type": proposal.proposal_type,
            "policy_tags": proposal.policy_tags,
            "structured_payload": proposal.structured_payload,
        },
    }

