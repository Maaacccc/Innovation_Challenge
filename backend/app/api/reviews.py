from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.enums import UserRole
from app.models import Proposal, ReviewDecision, User
from app.schemas import ProposalView, ReviewDecisionView
from app.services.orchestration import Orchestrator
from app.services.state import load_patient_state


router = APIRouter(prefix="/reviews", tags=["reviews"])
orchestrator = Orchestrator()


@router.post("/{proposal_id}/run", response_model=ReviewDecisionView)
def run_review(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewDecisionView:
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
    patient_state = load_patient_state(db, proposal.patient_id)
    review_draft = orchestrator.reviewer.review_proposal(
        db,
        ProposalView.model_validate(proposal),
        patient_state.model_dump(mode="json"),
    )
    review = orchestrator._create_review(db, proposal, review_draft)
    db.commit()
    return ReviewDecisionView.model_validate(review)

