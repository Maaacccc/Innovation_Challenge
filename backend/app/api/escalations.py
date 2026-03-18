from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, list_accessible_patient_ids, require_roles
from app.enums import UserRole
from app.models import EscalationCase
from app.schemas import EscalationView


router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("", response_model=list[EscalationView])
def list_escalations(
    status: str | None = Query(default=None),
    patient_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.CLINICIAN, UserRole.NURSE, UserRole.REVIEWER)),
) -> list[EscalationView]:
    query = db.query(EscalationCase)
    if status:
        query = query.filter(EscalationCase.status == status)
    if patient_id:
        query = query.filter(EscalationCase.patient_id == patient_id)
    if current_user.role == UserRole.REVIEWER.value:
        accessible_patient_ids = list_accessible_patient_ids(db, current_user)
        if not accessible_patient_ids:
            return []
        query = query.filter(EscalationCase.patient_id.in_(accessible_patient_ids))
    return [EscalationView.model_validate(case) for case in query.order_by(EscalationCase.created_at.desc()).all()]
