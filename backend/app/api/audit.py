from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_patient_access, get_current_user
from app.models import AuditLog, Proposal, User
from app.schemas import AuditLogView


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/{proposal_id}", response_model=list[AuditLogView])
def get_audit_trail(
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogView]:
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        return []
    assert_patient_access(db, current_user, proposal.patient_id, proposal.consent_scope_required)
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.proposal_id == proposal_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    return [AuditLogView.model_validate(row) for row in rows]
