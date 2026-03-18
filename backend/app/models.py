from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


def json_type():
    return JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    linked_patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    date_of_birth: Mapped[str] = mapped_column(String)
    gender: Mapped[str] = mapped_column(String)
    demographics: Mapped[dict] = mapped_column(json_type(), default=dict)
    chronic_conditions: Mapped[list] = mapped_column(json_type(), default=list)
    care_goals: Mapped[list] = mapped_column(json_type(), default=list)
    communication_preferences: Mapped[dict] = mapped_column(json_type(), default=dict)
    cultural_preferences: Mapped[dict] = mapped_column(json_type(), default=dict)
    clinician_notes_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_risk_status: Mapped[str] = mapped_column(String, default="low", nullable=False)

    medications: Mapped[list["Medication"]] = relationship(back_populates="patient")


class CaregiverRelationship(Base, TimestampMixin):
    __tablename__ = "caregiver_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    caregiver_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    relationship: Mapped[str] = mapped_column(String)
    permissions: Mapped[dict] = mapped_column(json_type(), default=dict)


class CareTeamAssignment(Base, TimestampMixin):
    __tablename__ = "care_team_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_role: Mapped[str] = mapped_column(String, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConsentRule(Base, TimestampMixin):
    __tablename__ = "consent_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    recipient_type: Mapped[str] = mapped_column(String, index=True)
    recipient_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    consent_scope: Mapped[str] = mapped_column(String, index=True)
    can_share: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    schedule: Mapped[dict] = mapped_column(json_type(), default=dict)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patient: Mapped[Patient] = relationship(back_populates="medications")


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    provider_name: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="scheduled")


class NormalizedEvent(Base):
    __tablename__ = "normalized_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_context_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_category: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(json_type(), default=dict)
    normalized_summary: Mapped[str] = mapped_column(Text, default="")
    risk_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class PatientStateCurrent(Base):
    __tablename__ = "patient_state_current"

    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    state: Mapped[dict] = mapped_column(json_type(), default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OrchestrationRun(Base):
    __tablename__ = "orchestration_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    trigger_event_id: Mapped[str | None] = mapped_column(ForeignKey("normalized_events.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running", nullable=False)
    summary: Mapped[dict] = mapped_column(json_type(), default=dict)


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    parent_proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_agent: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_context_id: Mapped[str | None] = mapped_column(String, nullable=True)
    orchestration_run_id: Mapped[str | None] = mapped_column(ForeignKey("orchestration_runs.id"), nullable=True)
    target_recipient_type: Mapped[str] = mapped_column(String, index=True)
    target_recipient_id: Mapped[str | None] = mapped_column(String, nullable=True)
    proposal_type: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    structured_payload: Mapped[dict] = mapped_column(json_type(), default=dict)
    supporting_evidence: Mapped[list] = mapped_column(json_type(), default=list)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    estimated_risk_level: Mapped[str] = mapped_column(String, default="low", nullable=False)
    rationale: Mapped[str] = mapped_column(Text)
    consent_scope_required: Mapped[str] = mapped_column(String, default="general")
    policy_tags: Mapped[list] = mapped_column(json_type(), default=list)
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False, index=True)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    reviewer_agent: Mapped[str] = mapped_column(String, default="RiskReviewAgent")
    decision: Mapped[str] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, default="informational")
    issues_found: Mapped[list] = mapped_column(json_type(), default=list)
    review_feedback: Mapped[str] = mapped_column(Text, default="")
    structured_feedback: Mapped[dict] = mapped_column(json_type(), default=dict)
    required_changes: Mapped[list] = mapped_column(json_type(), default=list)
    revised_target_recipient_type: Mapped[str | None] = mapped_column(String, nullable=True)
    revised_policy_tags: Mapped[list | None] = mapped_column(json_type(), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    require_second_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    block_release: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RegenerationAttempt(Base):
    __tablename__ = "regeneration_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    prior_proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    review_decision_id: Mapped[str] = mapped_column(ForeignKey("review_decisions.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    strategy: Mapped[str] = mapped_column(String, default="rewrite")
    feedback_snapshot: Mapped[dict] = mapped_column(json_type(), default=dict)


class DeliveryArtifact(Base):
    __tablename__ = "delivery_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    recipient_type: Mapped[str] = mapped_column(String, index=True)
    recipient_id: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[str] = mapped_column(String, default="in_app")
    rendered_title: Mapped[str] = mapped_column(String)
    rendered_content: Mapped[str] = mapped_column(Text)
    artifact_payload: Mapped[dict] = mapped_column(json_type(), default=dict)


class EscalationCase(Base):
    __tablename__ = "escalation_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), nullable=True, index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    reason: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String, default="high")
    status: Mapped[str] = mapped_column(String, default="open")
    route_to: Mapped[str] = mapped_column(String, default="nurse_queue")
    artifact_payload: Mapped[dict] = mapped_column(json_type(), default=dict)


class HumanReviewCase(Base):
    __tablename__ = "human_review_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), nullable=True)
    escalation_case_id: Mapped[str | None] = mapped_column(
        ForeignKey("escalation_cases.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, default="open", index=True)
    reason: Mapped[str] = mapped_column(Text)
    assigned_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution: Mapped[dict | None] = mapped_column(json_type(), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey("proposals.id"), nullable=True, index=True)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("review_decisions.id"), nullable=True)
    orchestration_run_id: Mapped[str | None] = mapped_column(ForeignKey("orchestration_runs.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, index=True)
    detail: Mapped[dict] = mapped_column(json_type(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
