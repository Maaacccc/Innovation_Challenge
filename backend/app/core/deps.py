from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.enums import UserRole
from app.models import CareTeamAssignment, CaregiverRelationship, ConsentRule, Patient, User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.replace("Bearer ", "", 1)
    try:
        payload = decode_token(token)
    except Exception as exc:  # pragma: no cover - jwt variations
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


def require_roles(*roles: UserRole) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if roles and current_user.role not in {role.value for role in roles}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current_user

    return dependency


def caregiver_has_consent(db: Session, patient_id: str, caregiver_user_id: str, consent_scope: str) -> bool:
    consent = (
        db.query(ConsentRule)
        .filter(
            ConsentRule.patient_id == patient_id,
            ConsentRule.recipient_type == "caregiver",
            ConsentRule.consent_scope == consent_scope,
            ConsentRule.can_share.is_(True),
        )
        .filter(
            (ConsentRule.recipient_user_id.is_(None))
            | (ConsentRule.recipient_user_id == caregiver_user_id)
        )
        .first()
    )
    return consent is not None


def list_accessible_patient_ids(db: Session, current_user: User) -> list[str]:
    if current_user.role == UserRole.ADMIN.value:
        return [row[0] for row in db.query(Patient.id).order_by(Patient.last_name.asc()).all()]

    if current_user.role in {UserRole.CLINICIAN.value, UserRole.NURSE.value}:
        return [row[0] for row in db.query(Patient.id).order_by(Patient.last_name.asc()).all()]

    if current_user.role == UserRole.REVIEWER.value:
        return [
            row[0]
            for row in (
                db.query(CareTeamAssignment.patient_id)
                .filter(
                    CareTeamAssignment.user_id == current_user.id,
                    CareTeamAssignment.assignment_role == UserRole.REVIEWER.value,
                )
                .distinct()
                .all()
            )
        ]

    if current_user.role == UserRole.PATIENT.value and current_user.linked_patient_id:
        return [current_user.linked_patient_id]

    if current_user.role == UserRole.CAREGIVER.value:
        return [
            row[0]
            for row in (
                db.query(CaregiverRelationship.patient_id)
                .filter(CaregiverRelationship.caregiver_user_id == current_user.id)
                .distinct()
                .all()
            )
        ]

    return []


def assert_patient_access(db: Session, current_user: User, patient_id: str, consent_scope: str = "general") -> None:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    privileged_roles = {UserRole.ADMIN.value, UserRole.CLINICIAN.value, UserRole.NURSE.value}
    if current_user.role in privileged_roles:
        return

    if current_user.role == UserRole.REVIEWER.value:
        assignment = (
            db.query(CareTeamAssignment)
            .filter(
                CareTeamAssignment.patient_id == patient_id,
                CareTeamAssignment.user_id == current_user.id,
                CareTeamAssignment.assignment_role == UserRole.REVIEWER.value,
            )
            .first()
        )
        if assignment:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer not assigned to this patient")

    if current_user.role == UserRole.PATIENT.value and current_user.linked_patient_id == patient_id:
        return

    if current_user.role == UserRole.CAREGIVER.value:
        relationship = (
            db.query(CaregiverRelationship)
            .filter(
                CaregiverRelationship.patient_id == patient_id,
                CaregiverRelationship.caregiver_user_id == current_user.id,
            )
            .first()
        )
        if not relationship:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No caregiver relationship")
        if caregiver_has_consent(db, patient_id, current_user.id, consent_scope):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Consent not granted")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
