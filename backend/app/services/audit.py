from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    actor_type: str,
    detail: dict,
    patient_id: str | None = None,
    proposal_id: str | None = None,
    review_id: str | None = None,
    orchestration_run_id: str | None = None,
    actor_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        patient_id=patient_id,
        proposal_id=proposal_id,
        review_id=review_id,
        orchestration_run_id=orchestration_run_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        detail=detail,
    )
    db.add(entry)
    db.flush()
    return entry

