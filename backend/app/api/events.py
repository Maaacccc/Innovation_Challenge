from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_patient_access, get_current_user
from app.models import User
from app.schemas import EventIngestRequest, EventView
from app.services.state import ingest_event


router = APIRouter(prefix="/events", tags=["events"])


@router.post("/ingest", response_model=EventView)
def create_event(
    payload: EventIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventView:
    assert_patient_access(db, current_user, payload.patient_id)
    event = ingest_event(db, payload)
    db.commit()
    db.refresh(event)
    return EventView.model_validate(event)

