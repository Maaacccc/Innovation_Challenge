from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_patient_access, get_current_user
from app.models import User
from app.schemas import OrchestrationResult, OrchestrationRunRequest
from app.services.orchestration import Orchestrator


router = APIRouter(prefix="/orchestrations", tags=["orchestrations"])
orchestrator = Orchestrator()


@router.post("/run", response_model=OrchestrationResult)
def run_orchestration(
    payload: OrchestrationRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrchestrationResult:
    assert_patient_access(db, current_user, payload.patient_id)
    result = orchestrator.run(db, payload)
    db.commit()
    return result

