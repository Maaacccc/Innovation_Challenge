from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import list_accessible_patient_ids, require_roles
from app.enums import UserRole
from app.schemas import MetricsOverview
from app.services.metrics import get_metrics_overview


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/overview", response_model=MetricsOverview)
def metrics_overview(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER, UserRole.NURSE, UserRole.CLINICIAN)),
) -> MetricsOverview:
    patient_ids = None
    if current_user.role == UserRole.REVIEWER.value:
        patient_ids = list_accessible_patient_ids(db, current_user)
    return get_metrics_overview(db, patient_ids=patient_ids)
