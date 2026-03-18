from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, list_accessible_patient_ids, require_roles
from app.enums import HumanReviewStatus, ProposalStatus, UserRole
from app.models import EscalationCase, HumanReviewCase, Proposal
from app.schemas import HumanReviewCaseView, HumanReviewResolveRequest
from app.services.audit import record_audit


router = APIRouter(prefix="/human-review", tags=["human-review"])


@router.get("", response_model=list[HumanReviewCaseView])
def list_human_review_cases(
    status: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> list[HumanReviewCaseView]:
    query = db.query(HumanReviewCase)
    if status:
        query = query.filter(HumanReviewCase.status == status)
    if current_user.role == UserRole.REVIEWER.value:
        accessible_patient_ids = list_accessible_patient_ids(db, current_user)
        if not accessible_patient_ids:
            return []
        query = query.filter(HumanReviewCase.patient_id.in_(accessible_patient_ids))
    if patient_id:
        query = query.filter(HumanReviewCase.patient_id == patient_id)
    return [HumanReviewCaseView.model_validate(case) for case in query.order_by(HumanReviewCase.created_at.desc()).all()]


@router.post("/{case_id}/resolve", response_model=HumanReviewCaseView)
def resolve_human_review(
    case_id: str,
    payload: HumanReviewResolveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> HumanReviewCaseView:
    case = db.get(HumanReviewCase, case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if current_user.role == UserRole.REVIEWER.value:
        accessible_patient_ids = set(list_accessible_patient_ids(db, current_user))
        if case.patient_id not in accessible_patient_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case not assigned to this reviewer")

    case.assigned_to_user_id = current_user.id
    case.resolved_at = datetime.utcnow()
    case.resolution = {"action": payload.action, "notes": payload.notes}
    proposal = db.get(Proposal, case.proposal_id) if case.proposal_id else None

    if payload.action == "approve":
        case.status = HumanReviewStatus.APPROVED.value
        if proposal:
            proposal.status = ProposalStatus.APPROVED.value
    elif payload.action == "reject":
        case.status = HumanReviewStatus.REJECTED.value
        if proposal:
            proposal.status = ProposalStatus.REJECTED.value
    elif payload.action == "escalate":
        case.status = HumanReviewStatus.ESCALATED.value
        if proposal:
            proposal.status = ProposalStatus.ESCALATED.value
            db.add(
                EscalationCase(
                    proposal_id=proposal.id,
                    patient_id=proposal.patient_id,
                    reason=payload.notes,
                    severity="high",
                    route_to="reviewer_escalation",
                    artifact_payload={"manual": True},
                )
            )
    else:  # pragma: no cover - literal enforcement
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported action")

    record_audit(
        db,
        action="human_review_resolved",
        actor_type="human_reviewer",
        actor_id=current_user.id,
        detail=case.resolution,
        patient_id=case.patient_id,
        proposal_id=case.proposal_id,
    )
    db.commit()
    db.refresh(case)
    return HumanReviewCaseView.model_validate(case)
