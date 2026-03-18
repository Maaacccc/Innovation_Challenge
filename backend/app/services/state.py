from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.enums import EventCategory, ProposalType, RiskLevel
from app.models import (
    Appointment,
    CaregiverRelationship,
    ConsentRule,
    EscalationCase,
    Medication,
    NormalizedEvent,
    Patient,
    PatientStateCurrent,
    Proposal,
)
from app.schemas import EventIngestRequest, PatientStateView


def summarize_event(payload: dict[str, Any], category: str, event_type: str) -> str:
    if category == EventCategory.PHYSIOLOGICAL.value:
        return f"{event_type} recorded: {payload.get('value')} {payload.get('unit', '')}".strip()
    if category == EventCategory.BEHAVIORAL.value:
        return f"{event_type} status: {payload.get('status')}"
    if category == EventCategory.AMBIENT.value:
        return f"{event_type} severity {payload.get('severity')}"
    return payload.get("text", "")[:180]


def derive_risk_hint(payload: dict[str, Any], category: str, event_type: str) -> str | None:
    if event_type in {"fall_detected", "prolonged_inactivity"}:
        return RiskLevel.HIGH.value
    if category == EventCategory.PHYSIOLOGICAL.value:
        value = payload.get("value")
        if isinstance(value, dict) and value.get("systolic", 0) >= 180:
            return RiskLevel.HIGH.value
        if isinstance(value, (float, int)) and event_type == "glucose" and value >= 250:
            return RiskLevel.HIGH.value
    return None


def ingest_event(db: Session, request: EventIngestRequest) -> NormalizedEvent:
    payload = request.event.model_dump(mode="json")
    event = NormalizedEvent(
        patient_id=request.patient_id,
        encounter_context_id=request.encounter_context_id,
        event_category=request.event.event_category.value,
        event_type=request.event.event_type,
        source=request.source,
        recorded_at=request.event.recorded_at,
        payload=payload,
        normalized_summary=summarize_event(payload, request.event.event_category.value, request.event.event_type),
        risk_hint=derive_risk_hint(payload, request.event.event_category.value, request.event.event_type),
    )
    db.add(event)
    db.flush()
    rebuild_patient_state(db, request.patient_id)
    return event


def _serialize_medication(medication: Medication) -> dict[str, Any]:
    return {
        "id": medication.id,
        "name": medication.name,
        "schedule": medication.schedule,
        "instructions": medication.instructions,
        "active": medication.active,
    }


def rebuild_patient_state(db: Session, patient_id: str) -> PatientStateView:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise ValueError("Patient not found")

    events = (
        db.query(NormalizedEvent)
        .filter(NormalizedEvent.patient_id == patient_id)
        .order_by(NormalizedEvent.recorded_at.desc())
        .all()
    )
    medications = db.query(Medication).filter(Medication.patient_id == patient_id).all()
    appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).order_by(Appointment.scheduled_at.desc()).all()
    relationships = (
        db.query(CaregiverRelationship)
        .filter(CaregiverRelationship.patient_id == patient_id)
        .all()
    )
    consent_rules = db.query(ConsentRule).filter(ConsentRule.patient_id == patient_id).all()
    escalations = (
        db.query(EscalationCase)
        .filter(EscalationCase.patient_id == patient_id)
        .order_by(EscalationCase.created_at.desc())
        .all()
    )
    pending_follow_ups = (
        db.query(Proposal)
        .filter(
            Proposal.patient_id == patient_id,
            Proposal.proposal_type == ProposalType.FOLLOW_UP_TASK.value,
            Proposal.status.in_(["draft", "under_review", "approved"]),
        )
        .order_by(Proposal.created_at.desc())
        .all()
    )

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events[:30]:
        entry = {
            "id": event.id,
            "event_type": event.event_type,
            "recorded_at": event.recorded_at.isoformat(),
            "summary": event.normalized_summary,
            "payload": event.payload,
            "risk_hint": event.risk_hint,
        }
        if event.event_category == EventCategory.PHYSIOLOGICAL.value:
            buckets["recent_vitals"].append(entry)
            if event.event_type in {"sleep_duration", "step_count"}:
                buckets["recent_wearable_trends"].append(entry)
        elif event.event_category == EventCategory.BEHAVIORAL.value:
            buckets["adherence_events"].append(entry)
            if event.event_type == "activity_drop":
                buckets["functional_decline_indicators"].append(entry)
        elif event.event_category == EventCategory.AMBIENT.value:
            buckets["ambient_monitoring_events"].append(entry)
            if event.event_type in {"prolonged_inactivity", "reduced_room_exit_frequency"}:
                buckets["functional_decline_indicators"].append(entry)
        elif event.event_category == EventCategory.CONVERSATIONAL.value:
            buckets["symptoms"].append(entry)
        buckets["recent_events"].append(entry)

    current_risk = RiskLevel.LOW.value
    if any(case.status == "open" for case in escalations):
        current_risk = RiskLevel.HIGH.value
    elif any(event.risk_hint == RiskLevel.HIGH.value for event in events[:10]):
        current_risk = RiskLevel.HIGH.value
    elif any(event.risk_hint == RiskLevel.MEDIUM.value for event in events[:10]):
        current_risk = RiskLevel.MEDIUM.value

    state = PatientStateView(
        patient_id=patient.id,
        demographics={
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            **patient.demographics,
        },
        chronic_conditions=list(patient.chronic_conditions or []),
        medications=[_serialize_medication(medication) for medication in medications],
        care_goals=list(patient.care_goals or []),
        caregiver_relationships=[
            {
                "caregiver_user_id": rel.caregiver_user_id,
                "relationship": rel.relationship,
                "permissions": rel.permissions,
            }
            for rel in relationships
        ],
        consent_preferences=[
            {
                "recipient_type": rule.recipient_type,
                "recipient_user_id": rule.recipient_user_id,
                "consent_scope": rule.consent_scope,
                "can_share": rule.can_share,
                "notes": rule.notes,
            }
            for rule in consent_rules
        ],
        appointments=[
            {
                "id": appointment.id,
                "scheduled_at": appointment.scheduled_at.isoformat(),
                "provider_name": appointment.provider_name,
                "purpose": appointment.purpose,
                "status": appointment.status,
            }
            for appointment in appointments[:10]
        ],
        recent_vitals=buckets["recent_vitals"][:10],
        recent_wearable_trends=buckets["recent_wearable_trends"][:10],
        adherence_events=buckets["adherence_events"][:10],
        symptoms=buckets["symptoms"][:10],
        functional_decline_indicators=buckets["functional_decline_indicators"][:10],
        ambient_monitoring_events=buckets["ambient_monitoring_events"][:10],
        escalation_history=[
            {
                "id": case.id,
                "reason": case.reason,
                "severity": case.severity,
                "status": case.status,
                "created_at": case.created_at.isoformat(),
            }
            for case in escalations[:10]
        ],
        clinician_notes_summary=patient.clinician_notes_summary,
        communication_preferences=patient.communication_preferences or {},
        language_literacy_cultural_preferences=patient.cultural_preferences or {},
        current_risk_status=current_risk,
        pending_follow_ups=[
            {
                "proposal_id": proposal.id,
                "title": proposal.title,
                "status": proposal.status,
                "recipient_type": proposal.target_recipient_type,
            }
            for proposal in pending_follow_ups
        ],
        recent_events=buckets["recent_events"][:15],
    )

    projection = db.get(PatientStateCurrent, patient_id)
    if projection is None:
        projection = PatientStateCurrent(patient_id=patient_id, state=state.model_dump(mode="json"), version=1)
        db.add(projection)
    else:
        projection.state = state.model_dump(mode="json")
        projection.version += 1
    patient.current_risk_status = current_risk
    db.flush()
    return state


def load_patient_state(db: Session, patient_id: str) -> PatientStateView:
    projection = db.get(PatientStateCurrent, patient_id)
    if not projection:
        return rebuild_patient_state(db, patient_id)
    return PatientStateView.model_validate(projection.state)

