from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Appointment,
    CareTeamAssignment,
    CaregiverRelationship,
    ConsentRule,
    Medication,
    NormalizedEvent,
    Patient,
    User,
)
from app.services.state import rebuild_patient_state


DEMO_PASSWORD = "demo1234"


def _create_patient(config: dict) -> Patient:
    return Patient(
        first_name=config["first_name"],
        last_name=config["last_name"],
        date_of_birth=config["date_of_birth"],
        gender=config["gender"],
        demographics=config["demographics"],
        chronic_conditions=config["chronic_conditions"],
        care_goals=config["care_goals"],
        communication_preferences=config["communication_preferences"],
        cultural_preferences=config["cultural_preferences"],
        clinician_notes_summary=config["clinician_notes_summary"],
        current_risk_status="low",
    )


def seed_demo_data(db: Session) -> None:
    if db.query(User).count() > 0:
        return

    patient_configs = {
        "a": {
            "first_name": "Alice",
            "last_name": "Tan",
            "date_of_birth": "1942-06-08",
            "gender": "female",
            "demographics": {"city": "Singapore", "living_arrangement": "with caregiver 1"},
            "chronic_conditions": ["hypertension", "type 2 diabetes", "osteoarthritis"],
            "care_goals": ["avoid missed evening medication", "keep sleep above 6 hours", "maintain safe mobility"],
            "communication_preferences": {"tone": "gentle", "channel": "in_app", "literacy": "plain_language"},
            "cultural_preferences": {"language": "English", "cultural_context": "family-centered"},
            "clinician_notes_summary": "Monitor evening adherence, joint pain, and overnight sleep variability.",
            "patient_email": "patient.a@example.com",
            "caregiver_email": "caregiver.1@example.com",
            "reviewer_email": "reviewer.w@example.com",
            "caregiver_relationship": "domestic_helper",
            "consents": {
                "caregiver_tasks": True,
                "basic_overview": True,
                "general": True,
                "medication_reminders": False,
            },
            "medication": {
                "name": "Metformin evening dose",
                "schedule": {"time": "20:00", "frequency": "daily"},
                "instructions": "Take with food.",
            },
            "appointment": {
                "provider_name": "Community Geriatrics Clinic",
                "purpose": "Chronic care review",
                "days_from_now": 5,
            },
            "baseline_events": [
                ("blood_pressure", {"systolic": 146, "diastolic": 88}, "mmHg", 2),
                ("sleep_duration", 5.1, "hours", 1),
                ("step_count", 3840, "steps", 1),
            ],
        },
        "b": {
            "first_name": "Bernard",
            "last_name": "Ong",
            "date_of_birth": "1939-11-23",
            "gender": "male",
            "demographics": {"city": "Singapore", "living_arrangement": "with caregiver 1"},
            "chronic_conditions": ["heart failure", "chronic insomnia"],
            "care_goals": ["improve appetite support", "sleep more consistently", "avoid exertional fatigue"],
            "communication_preferences": {"tone": "direct_but_warm", "channel": "in_app", "literacy": "plain_language"},
            "cultural_preferences": {"language": "English", "cultural_context": "practical"},
            "clinician_notes_summary": "Watch for fatigue, appetite decline, and caregiver-observed transfer difficulty.",
            "patient_email": "patient.b@example.com",
            "caregiver_email": "caregiver.1@example.com",
            "reviewer_email": "reviewer.m@example.com",
            "caregiver_relationship": "daughter",
            "consents": {
                "caregiver_tasks": True,
                "basic_overview": True,
                "general": False,
                "medication_reminders": True,
            },
            "medication": {
                "name": "Furosemide morning dose",
                "schedule": {"time": "08:00", "frequency": "daily"},
                "instructions": "Monitor dizziness and hydration.",
            },
            "appointment": {
                "provider_name": "Heart Failure Outreach Team",
                "purpose": "Volume status follow-up",
                "days_from_now": 3,
            },
            "baseline_events": [
                ("blood_pressure", {"systolic": 138, "diastolic": 82}, "mmHg", 2),
                ("sleep_duration", 4.2, "hours", 1),
                ("step_count", 2650, "steps", 1),
                ("weight", 64.8, "kg", 1),
            ],
        },
        "c": {
            "first_name": "Clara",
            "last_name": "Lee",
            "date_of_birth": "1945-03-14",
            "gender": "female",
            "demographics": {"city": "Singapore", "living_arrangement": "with caregiver 2"},
            "chronic_conditions": ["copd", "osteoporosis"],
            "care_goals": ["reduce night wandering risk", "maintain oxygenation", "keep daily walking routine"],
            "communication_preferences": {"tone": "reassuring", "channel": "in_app", "literacy": "plain_language"},
            "cultural_preferences": {"language": "English", "cultural_context": "independent"},
            "clinician_notes_summary": "Track night activity, fall risk, and exertional dyspnea trends.",
            "patient_email": "patient.c@example.com",
            "caregiver_email": "caregiver.2@example.com",
            "reviewer_email": "reviewer.w@example.com",
            "caregiver_relationship": "son",
            "consents": {
                "caregiver_tasks": True,
                "basic_overview": True,
                "general": False,
                "medication_reminders": False,
            },
            "medication": {
                "name": "COPD inhaler",
                "schedule": {"time": "09:00", "frequency": "daily"},
                "instructions": "Rinse mouth after use.",
            },
            "appointment": {
                "provider_name": "Pulmonary and Falls Clinic",
                "purpose": "Breathing and mobility review",
                "days_from_now": 7,
            },
            "baseline_events": [
                ("blood_pressure", {"systolic": 132, "diastolic": 78}, "mmHg", 2),
                ("sleep_duration", 6.4, "hours", 1),
                ("step_count", 1780, "steps", 1),
                ("spo2", 93, "%", 0),
            ],
        },
    }

    patients: dict[str, Patient] = {}
    for key, config in patient_configs.items():
        patient = _create_patient(config)
        db.add(patient)
        patients[key] = patient
    db.flush()

    users = [
        User(
            email="patient.a@example.com",
            full_name="Alice Tan",
            role="patient",
            linked_patient_id=patients["a"].id,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="patient.b@example.com",
            full_name="Bernard Ong",
            role="patient",
            linked_patient_id=patients["b"].id,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="patient.c@example.com",
            full_name="Clara Lee",
            role="patient",
            linked_patient_id=patients["c"].id,
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="caregiver.1@example.com",
            full_name="Caregiver 1",
            role="caregiver",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="caregiver.2@example.com",
            full_name="Caregiver 2",
            role="caregiver",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="reviewer.w@example.com",
            full_name="Reviewer W",
            role="reviewer",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="reviewer.m@example.com",
            full_name="Reviewer M",
            role="reviewer",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="nurse@example.com",
            full_name="Nurse Lee",
            role="nurse",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="clinician@example.com",
            full_name="Dr Lim",
            role="clinician",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
        User(
            email="admin@example.com",
            full_name="System Admin",
            role="admin",
            password_hash=hash_password(DEMO_PASSWORD),
        ),
    ]
    db.add_all(users)
    db.flush()

    users_by_email = {user.email: user for user in users}
    now = datetime.utcnow()

    for key, config in patient_configs.items():
        patient = patients[key]
        caregiver_user = users_by_email[config["caregiver_email"]]
        reviewer_user = users_by_email[config["reviewer_email"]]

        db.add(
            CaregiverRelationship(
                patient_id=patient.id,
                caregiver_user_id=caregiver_user.id,
                relationship=config["caregiver_relationship"],
                permissions={"task_cards": True, "basic_overview": True, "updates": True},
            )
        )
        db.add(
            CareTeamAssignment(
                patient_id=patient.id,
                user_id=reviewer_user.id,
                assignment_role="reviewer",
                notes=f"Seed assignment for patient {key.upper()}",
            )
        )

        for scope, can_share in config["consents"].items():
            db.add(
                ConsentRule(
                    patient_id=patient.id,
                    recipient_type="caregiver",
                    recipient_user_id=caregiver_user.id,
                    consent_scope=scope,
                    can_share=can_share,
                    notes=f"Seeded {scope} visibility for caregiver workspace.",
                )
            )

        db.add(
            Medication(
                patient_id=patient.id,
                name=config["medication"]["name"],
                schedule=config["medication"]["schedule"],
                instructions=config["medication"]["instructions"],
                active=True,
            )
        )
        db.add(
            Appointment(
                patient_id=patient.id,
                scheduled_at=now + timedelta(days=config["appointment"]["days_from_now"]),
                provider_name=config["appointment"]["provider_name"],
                purpose=config["appointment"]["purpose"],
                status="scheduled",
            )
        )

        for event_type, value, unit, days_ago in config["baseline_events"]:
            recorded_at = now - timedelta(days=days_ago)
            db.add(
                NormalizedEvent(
                    patient_id=patient.id,
                    encounter_context_id="baseline",
                    event_category="physiological",
                    event_type=event_type,
                    source="seed",
                    recorded_at=recorded_at,
                    payload={
                        "event_category": "physiological",
                        "event_type": event_type,
                        "value": value,
                        "unit": unit,
                        "recorded_at": recorded_at.isoformat(),
                    },
                    normalized_summary=f"{event_type} recorded: {value} {unit}",
                    risk_hint=None,
                )
            )

    db.flush()
    for patient in patients.values():
        rebuild_patient_state(db, patient.id)
