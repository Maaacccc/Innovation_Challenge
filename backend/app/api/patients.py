from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import assert_patient_access, caregiver_has_consent, get_current_user, list_accessible_patient_ids
from app.enums import UserRole
from app.models import CaregiverRelationship, ConsentRule, Patient, Proposal, User
from app.schemas import (
    CaregiverObservationRequest,
    CaregiverObservationResponse,
    ConsentPreferenceView,
    ConsentUpdateRequest,
    EventIngestRequest,
    EventView,
    OrchestrationRunRequest,
    PatientStateView,
    PatientSummaryView,
    ProposalView,
)
from app.services.orchestration import Orchestrator
from app.services.state import ingest_event, load_patient_state, rebuild_patient_state


router = APIRouter(prefix="/patients", tags=["patients"])
orchestrator = Orchestrator()


def _sanitize_state_for_user(db: Session, state: PatientStateView, current_user: User) -> PatientStateView:
    if current_user.role != UserRole.CAREGIVER.value:
        return state

    has_basic_overview = caregiver_has_consent(db, state.patient_id, current_user.id, "basic_overview")
    has_general = caregiver_has_consent(db, state.patient_id, current_user.id, "general")
    has_medication = caregiver_has_consent(db, state.patient_id, current_user.id, "medication_reminders")

    data = state.model_dump(mode="json")
    data["clinician_notes_summary"] = None
    data["consent_preferences"] = []

    if not has_basic_overview and not has_general:
        data["recent_vitals"] = []
        data["recent_wearable_trends"] = []
        data["appointments"] = []
        data["chronic_conditions"] = []

    if not has_general:
        data["care_goals"] = []
        data["symptoms"] = []
        data["ambient_monitoring_events"] = []
        data["functional_decline_indicators"] = []
        data["escalation_history"] = []
        data["recent_events"] = [
            event
            for event in data["recent_events"]
            if event["event_type"] in {"sleep_duration", "step_count", "blood_pressure", "heart_rate", "spo2", "weight"}
        ]

    if not has_medication:
        data["medications"] = []
        data["adherence_events"] = [
            event
            for event in data["adherence_events"]
            if event["event_type"] != "medication_logging"
        ]

    return PatientStateView.model_validate(data)


@router.get("/{patient_id}/state", response_model=PatientStateView)
def get_patient_state(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientStateView:
    if current_user.role == UserRole.CAREGIVER.value:
        relationship = (
            db.query(CaregiverRelationship)
            .filter(
                CaregiverRelationship.patient_id == patient_id,
                CaregiverRelationship.caregiver_user_id == current_user.id,
            )
            .first()
        )
        if relationship is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No caregiver relationship")
    else:
        assert_patient_access(db, current_user, patient_id)

    return _sanitize_state_for_user(db, load_patient_state(db, patient_id), current_user)


@router.get("", response_model=list[PatientSummaryView])
def list_accessible_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PatientSummaryView]:
    patient_ids = list_accessible_patient_ids(db, current_user)
    patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).order_by(Patient.last_name.asc()).all() if patient_ids else []
    return [PatientSummaryView.model_validate(patient) for patient in patients if patient]


@router.get("/{patient_id}/proposals", response_model=list[ProposalView])
def list_patient_proposals(
    patient_id: str,
    status: str | None = Query(default=None),
    risk: str | None = Query(default=None),
    recipient_type: str | None = Query(default=None),
    source_agent: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProposalView]:
    assert_patient_access(db, current_user, patient_id)
    query = db.query(Proposal).filter(Proposal.patient_id == patient_id)
    if status:
        query = query.filter(Proposal.status == status)
    if risk:
        query = query.filter(Proposal.estimated_risk_level == risk)
    if recipient_type:
        query = query.filter(Proposal.target_recipient_type == recipient_type)
    if source_agent:
        query = query.filter(Proposal.source_agent == source_agent)
    proposals = query.order_by(Proposal.created_at.desc()).all()

    if current_user.role == UserRole.PATIENT.value:
        proposals = [
            proposal
            for proposal in proposals
            if proposal.target_recipient_type == "patient" and proposal.status in {"approved", "delivered"}
        ]
    elif current_user.role == UserRole.CAREGIVER.value:
        proposals = [
            proposal
            for proposal in proposals
            if proposal.target_recipient_type == "caregiver"
            and proposal.target_recipient_id == current_user.id
            and proposal.status in {"approved", "delivered"}
        ]
    return [ProposalView.model_validate(proposal) for proposal in proposals]


@router.post("/{patient_id}/consent/caregiver", response_model=list[ConsentPreferenceView])
def update_caregiver_consent(
    patient_id: str,
    payload: ConsentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConsentPreferenceView]:
    if current_user.role not in {UserRole.PATIENT.value, UserRole.ADMIN.value, UserRole.REVIEWER.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    assert_patient_access(db, current_user, patient_id)

    relationships = db.query(CaregiverRelationship).filter(CaregiverRelationship.patient_id == patient_id).all()
    caregiver_user_ids = [relationship.caregiver_user_id for relationship in relationships]
    if not caregiver_user_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No caregiver relationship found")

    rules = (
        db.query(ConsentRule)
        .filter(
            ConsentRule.patient_id == patient_id,
            ConsentRule.recipient_type == "caregiver",
            ConsentRule.consent_scope == payload.consent_scope,
        )
        .all()
    )

    if not rules:
        for caregiver_user_id in caregiver_user_ids:
            db.add(
                ConsentRule(
                    patient_id=patient_id,
                    recipient_type="caregiver",
                    recipient_user_id=caregiver_user_id,
                    consent_scope=payload.consent_scope,
                    can_share=payload.can_share,
                    notes=payload.notes,
                )
            )
    else:
        for rule in rules:
            rule.can_share = payload.can_share
            rule.notes = payload.notes

    db.flush()
    state = rebuild_patient_state(db, patient_id)
    db.commit()
    return [
        ConsentPreferenceView.model_validate(item)
        for item in state.consent_preferences
        if item.recipient_type == "caregiver"
    ]


@router.post("/{patient_id}/caregiver-observations", response_model=CaregiverObservationResponse)
def submit_caregiver_observation(
    patient_id: str,
    payload: CaregiverObservationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaregiverObservationResponse:
    if current_user.role != UserRole.CAREGIVER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only caregivers can submit observations")

    relationship = (
        db.query(CaregiverRelationship)
        .filter(
            CaregiverRelationship.patient_id == patient_id,
            CaregiverRelationship.caregiver_user_id == current_user.id,
        )
        .first()
    )
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No caregiver relationship")

    event = ingest_event(
        db,
        EventIngestRequest(
            patient_id=patient_id,
            encounter_context_id="caregiver-observation",
            source="caregiver_workspace",
            event={
                "event_category": "conversational",
                "event_type": "caregiver_observation_text",
                "text": payload.text,
                "recorded_at": datetime.utcnow(),
                "author_role": "caregiver",
                "details": {"submitted_by": current_user.id},
            },
        ),
    )
    db.commit()
    result = orchestrator.run(
        db,
        OrchestrationRunRequest(
            patient_id=patient_id,
            trigger_event_id=event.id,
            encounter_context_id="caregiver-observation",
            task_hints=["caregiver_support", "care_coordinator"],
        ),
    )
    db.commit()
    return CaregiverObservationResponse(
        event=EventView.model_validate(event),
        orchestration_run_id=result.run.id,
        outcomes_count=len(result.outcomes),
    )
