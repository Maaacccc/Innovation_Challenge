from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.enums import (
    DeliveryChannel,
    EventCategory,
    HumanReviewStatus,
    ProposalStatus,
    ProposalType,
    RecipientType,
    ReviewDecisionType,
    ReviewSeverity,
    RiskLevel,
    UserRole,
)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserView"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserView(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    linked_patient_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PhysiologicalEventPayload(BaseModel):
    event_category: Literal[EventCategory.PHYSIOLOGICAL]
    event_type: Literal[
        "blood_pressure",
        "glucose",
        "heart_rate",
        "sleep_duration",
        "step_count",
        "weight",
        "spo2",
    ]
    value: float | dict[str, float]
    unit: str
    recorded_at: datetime
    note: str | None = None


class BehavioralEventPayload(BaseModel):
    event_category: Literal[EventCategory.BEHAVIORAL]
    event_type: Literal[
        "reminder_response",
        "medication_logging",
        "appointment_completion",
        "daily_routine_adherence",
        "activity_drop",
    ]
    status: str
    recorded_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AmbientEventPayload(BaseModel):
    event_category: Literal[EventCategory.AMBIENT]
    event_type: Literal[
        "fall_detected",
        "prolonged_inactivity",
        "night_wandering",
        "reduced_room_exit_frequency",
        "unusual_night_activity",
    ]
    severity: str
    recorded_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class ConversationalEventPayload(BaseModel):
    event_category: Literal[EventCategory.CONVERSATIONAL]
    event_type: Literal[
        "patient_symptom_text",
        "caregiver_observation_text",
        "voice_transcript_text",
        "structured_daily_check_in",
    ]
    text: str
    recorded_at: datetime
    author_role: str
    details: dict[str, Any] = Field(default_factory=dict)


NormalizedEventPayload = Annotated[
    Union[
        PhysiologicalEventPayload,
        BehavioralEventPayload,
        AmbientEventPayload,
        ConversationalEventPayload,
    ],
    Field(discriminator="event_category"),
]


class EventIngestRequest(BaseModel):
    patient_id: str
    encounter_context_id: str | None = None
    source: str
    event: NormalizedEventPayload


class EventView(BaseModel):
    id: str
    patient_id: str
    encounter_context_id: str | None = None
    event_category: str
    event_type: str
    source: str
    recorded_at: datetime
    payload: dict[str, Any]
    normalized_summary: str
    risk_hint: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CaregiverRelationshipView(BaseModel):
    caregiver_user_id: str
    relationship: str
    permissions: dict[str, Any]


class ConsentPreferenceView(BaseModel):
    recipient_type: str
    recipient_user_id: str | None = None
    consent_scope: str
    can_share: bool
    notes: str | None = None


class PatientSummaryView(BaseModel):
    id: str
    first_name: str
    last_name: str
    current_risk_status: str
    chronic_conditions: list[str]

    model_config = ConfigDict(from_attributes=True)


class PatientStateView(BaseModel):
    patient_id: str
    demographics: dict[str, Any]
    chronic_conditions: list[str]
    medications: list[dict[str, Any]]
    care_goals: list[str]
    caregiver_relationships: list[CaregiverRelationshipView]
    consent_preferences: list[ConsentPreferenceView]
    appointments: list[dict[str, Any]]
    recent_vitals: list[dict[str, Any]]
    recent_wearable_trends: list[dict[str, Any]]
    adherence_events: list[dict[str, Any]]
    symptoms: list[dict[str, Any]]
    functional_decline_indicators: list[dict[str, Any]]
    ambient_monitoring_events: list[dict[str, Any]]
    escalation_history: list[dict[str, Any]]
    clinician_notes_summary: str | None = None
    communication_preferences: dict[str, Any]
    language_literacy_cultural_preferences: dict[str, Any]
    current_risk_status: str
    pending_follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class ProposalDraft(BaseModel):
    source_agent: str
    patient_id: str
    encounter_context_id: str | None = None
    target_recipient_type: RecipientType
    target_recipient_id: str | None = None
    proposal_type: ProposalType
    title: str
    content: str
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    supporting_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1)
    estimated_risk_level: RiskLevel
    rationale: str
    consent_scope_required: str = "general"
    policy_tags: list[str] = Field(default_factory=list)
    needs_human_review: bool = False


class ProposalView(ProposalDraft):
    id: str
    parent_proposal_id: str | None = None
    version_number: int
    created_at: datetime
    orchestration_run_id: str | None = None
    status: ProposalStatus

    model_config = ConfigDict(from_attributes=True)


class StructuredFeedbackItem(BaseModel):
    issue_code: str
    issue_description: str
    why_it_matters: str
    must_fix: str
    suggested_rewrite_strategy: str
    evidence_to_include: list[str] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    target_recipient_constraints: list[str] = Field(default_factory=list)


class ReviewDraft(BaseModel):
    decision: ReviewDecisionType
    severity: ReviewSeverity
    issues_found: list[str] = Field(default_factory=list)
    review_feedback: str
    structured_feedback: dict[str, Any] = Field(default_factory=dict)
    required_changes: list[str] = Field(default_factory=list)
    revised_target_recipient_type: RecipientType | None = None
    revised_policy_tags: list[str] | None = None
    escalation_reason: str | None = None
    require_second_review: bool = False
    block_release: bool = False


class ReviewDecisionView(ReviewDraft):
    id: str
    proposal_id: str
    reviewed_at: datetime
    reviewer_agent: str

    model_config = ConfigDict(from_attributes=True)


class DeliveryArtifactView(BaseModel):
    id: str
    proposal_id: str
    delivered_at: datetime
    recipient_type: RecipientType
    recipient_id: str | None = None
    channel: DeliveryChannel
    rendered_title: str
    rendered_content: str
    artifact_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class EscalationView(BaseModel):
    id: str
    proposal_id: str | None = None
    patient_id: str
    created_at: datetime
    reason: str
    severity: str
    status: str
    route_to: str
    artifact_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AuditLogView(BaseModel):
    id: str
    patient_id: str | None = None
    proposal_id: str | None = None
    review_id: str | None = None
    orchestration_run_id: str | None = None
    actor_type: str
    actor_id: str | None = None
    action: str
    detail: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HumanReviewCaseView(BaseModel):
    id: str
    patient_id: str
    proposal_id: str | None = None
    escalation_case_id: str | None = None
    status: HumanReviewStatus
    reason: str
    assigned_to_user_id: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class HumanReviewResolveRequest(BaseModel):
    action: Literal["approve", "reject", "escalate"]
    notes: str


class OrchestrationRunRequest(BaseModel):
    patient_id: str
    trigger_event_id: str | None = None
    encounter_context_id: str | None = None
    task_hints: list[str] = Field(default_factory=list)


class ProposalOutcome(BaseModel):
    proposal: ProposalView
    latest_review: ReviewDecisionView | None = None
    delivery: DeliveryArtifactView | None = None
    escalation: EscalationView | None = None
    human_review_case: HumanReviewCaseView | None = None
    rounds: int = 0


class OrchestrationRunView(BaseModel):
    id: str
    patient_id: str
    trigger_event_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    summary: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class OrchestrationResult(BaseModel):
    run: OrchestrationRunView
    patient_state: PatientStateView
    outcomes: list[ProposalOutcome]


class MetricsOverview(BaseModel):
    proposals_approved_directly: int
    proposals_revised: int
    proposals_rerouted: int
    escalations_created: int
    proposals_rejected_and_regenerated: int
    average_review_rounds: float
    blocked_unsafe_outputs_count: int
    recipient_mismatch_caught_by_review: int
    consent_violations_caught_by_review: int


class ConsentUpdateRequest(BaseModel):
    consent_scope: str
    can_share: bool
    notes: str | None = None


class CaregiverObservationRequest(BaseModel):
    text: str


class CaregiverObservationResponse(BaseModel):
    event: EventView
    orchestration_run_id: str | None = None
    outcomes_count: int = 0


UserView.model_rebuild()
