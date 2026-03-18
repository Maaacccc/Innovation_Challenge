from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_patient_access, get_current_user
from app.enums import UserRole
from app.models import Proposal, User
from app.schemas import ProposalOutcome, ProposalView, ReviewDecisionView
from app.services.orchestration import Orchestrator


router = APIRouter(prefix="/proposals", tags=["proposals"])
orchestrator = Orchestrator()


def _check_proposal_visibility(proposal: Proposal, current_user: User) -> bool:
    if current_user.role in {
        UserRole.ADMIN.value,
        UserRole.CLINICIAN.value,
        UserRole.NURSE.value,
        UserRole.REVIEWER.value,
    }:
        return True
    if current_user.role == UserRole.PATIENT.value:
        return proposal.target_recipient_type == "patient"
    if current_user.role == UserRole.CAREGIVER.value:
        return proposal.target_recipient_type == "caregiver" and proposal.target_recipient_id == current_user.id
    return False


@router.get("/{proposal_id}", response_model=ProposalView)
def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProposalView:
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    assert_patient_access(db, current_user, proposal.patient_id, proposal.consent_scope_required)
    if not _check_proposal_visibility(proposal, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Proposal not visible")
    return ProposalView.model_validate(proposal)


@router.post("/{proposal_id}/regenerate", response_model=ProposalOutcome)
def regenerate_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProposalOutcome:
    if current_user.role not in {
        UserRole.ADMIN.value,
        UserRole.CLINICIAN.value,
        UserRole.NURSE.value,
        UserRole.REVIEWER.value,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    result = orchestrator.regenerate_from_latest_review(db, proposal)
    db.commit()
    return ProposalOutcome(
        proposal=ProposalView.model_validate(result.proposal),
        latest_review=ReviewDecisionView.model_validate(result.latest_review) if result.latest_review else None,
        delivery=result.delivery,
        escalation=result.escalation,
        human_review_case=result.human_review_case,
        rounds=result.rounds,
    )

