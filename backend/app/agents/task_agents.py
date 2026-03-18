from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent, TaskContext
from app.enums import ProposalType, RecipientType, RiskLevel
from app.schemas import PatientStateView, ProposalDraft


def _latest_event(patient_state: PatientStateView, event_type: str) -> dict[str, Any] | None:
    return next((item for item in patient_state.recent_events if item.get("event_type") == event_type), None)


def _caregiver_id(patient_state: PatientStateView) -> str | None:
    if not patient_state.caregiver_relationships:
        return None
    return patient_state.caregiver_relationships[0].caregiver_user_id


class CareCoordinatorAgent(BaseAgent):
    name = "CareCoordinatorAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        if patient_state.current_risk_status == RiskLevel.LOW.value and "care_coordinator" not in task_context.task_hints:
            return None
        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.INTERNAL_QUEUE,
            proposal_type=ProposalType.FOLLOW_UP_TASK,
            title="Coordinator follow-up",
            content="Review recent risk signals, confirm next outreach owner, and close the loop within 24 hours.",
            structured_payload={
                "actions": ["check open risks", "confirm outreach owner", "document completion window"],
                "patient_risk": patient_state.current_risk_status,
            },
            supporting_evidence=patient_state.recent_events[:3],
            confidence_score=0.73,
            estimated_risk_level=RiskLevel.MEDIUM
            if patient_state.current_risk_status != RiskLevel.LOW.value
            else RiskLevel.LOW,
            rationale="Coordinator oversight is needed when risk remains elevated or follow-ups are pending.",
            consent_scope_required="operations",
            policy_tags=["care_coordination", "follow_up"],
        )


class DigitalNurseAgent(BaseAgent):
    name = "DigitalNurseAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        trigger = task_context.trigger_event or {}
        abnormal_vitals = [
            item for item in patient_state.recent_vitals if item.get("event_type") in {"blood_pressure", "glucose", "spo2"}
        ]
        if not abnormal_vitals and trigger.get("event_type") not in {
            "patient_symptom_text",
            "fall_detected",
            "prolonged_inactivity",
        }:
            return None
        risk = RiskLevel.HIGH if trigger.get("event_type") in {"fall_detected", "prolonged_inactivity"} else RiskLevel.MEDIUM
        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.NURSE,
            proposal_type=ProposalType.TRIAGE_NOTE,
            title="Nursing triage review",
            content=(
                "Recent symptoms and monitoring data suggest the patient may need a same-day nursing review. "
                "Please assess deterioration risk, medication timing, hydration, and mobility safety."
            ),
            structured_payload={
                "triage_focus": ["deterioration", "hydration", "medication timing", "mobility safety"],
                "trigger": trigger.get("event_type"),
            },
            supporting_evidence=(patient_state.symptoms[:2] + patient_state.recent_vitals[:2] + patient_state.ambient_monitoring_events[:2])[:5],
            confidence_score=0.78 if risk == RiskLevel.MEDIUM else 0.9,
            estimated_risk_level=risk,
            rationale="Nurse-facing triage note consolidates symptom and monitoring evidence for early deterioration review.",
            consent_scope_required="clinical_review",
            policy_tags=["nursing_triage", "signal_detection"],
        )


class MedicationAdherenceAgent(BaseAgent):
    name = "MedicationAdherenceAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        missed_logs = [
            event
            for event in patient_state.adherence_events
            if event.get("event_type") == "medication_logging" and event.get("payload", {}).get("status") == "missed"
        ]
        if len(missed_logs) < 2 and "medication_adherence" not in task_context.task_hints:
            return None
        medication_name = patient_state.medications[0]["name"] if patient_state.medications else "your evening medication"
        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.PATIENT,
            proposal_type=ProposalType.REMINDER,
            title="Medication support reminder",
            content=(
                f"We noticed it has been harder to keep up with {medication_name}. "
                "If you are able, please take tonight's dose as scheduled and tell us if anything is making it difficult."
            ),
            structured_payload={
                "medication_name": medication_name,
                "pattern": "missed_evening_dose_twice_in_three_days",
                "recommended_actions": ["gentle reminder", "ask about barriers", "log response"],
            },
            supporting_evidence=missed_logs[:3],
            confidence_score=0.76,
            estimated_risk_level=RiskLevel.LOW,
            rationale="A supportive adherence reminder can address repeated missed medication logs before deterioration.",
            consent_scope_required="medication_reminders",
            policy_tags=["medication_adherence", "patient_safe"],
        )


class HealthCoachAgent(BaseAgent):
    name = "HealthCoachAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        step_drop = _latest_event(patient_state, "activity_drop") or _latest_event(patient_state, "step_count")
        if not step_drop and "force_risky_health_coach" not in task_context.task_hints and "health_coach" not in task_context.task_hints:
            return None

        content = (
            "Your recent sleep and activity changes may be making the day feel harder. "
            "A short walk, a glass of water, and a regular bedtime tonight could help. "
            "If symptoms are getting worse, let your care team know."
        )
        confidence = 0.66
        if "force_risky_health_coach" in task_context.task_hints:
            content = (
                "Your poor sleep definitely means your condition is getting worse, so there is no need to ask anyone else first. "
                "Just follow this plan and you will avoid problems."
            )
            confidence = 0.92

        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.PATIENT,
            proposal_type=ProposalType.EDUCATION,
            title="Daily routine support",
            content=content,
            structured_payload={
                "focus": ["sleep routine", "hydration", "light activity"],
                "cultural_considerations": patient_state.language_literacy_cultural_preferences,
            },
            supporting_evidence=[step_drop] if step_drop else [],
            confidence_score=confidence,
            estimated_risk_level=RiskLevel.LOW,
            rationale="Health coaching can support self-management when activity and sleep patterns slip.",
            consent_scope_required="coaching",
            policy_tags=["health_coaching", "empathetic_support"],
        )


class CaregiverSupportAgent(BaseAgent):
    name = "CaregiverSupportAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        caregiver_id = _caregiver_id(patient_state)
        observation = _latest_event(patient_state, "caregiver_observation_text")
        mobility_signal = _latest_event(patient_state, "reduced_room_exit_frequency") or _latest_event(patient_state, "activity_drop")
        poor_sleep = _latest_event(patient_state, "sleep_duration")
        if not caregiver_id or (not observation and not mobility_signal and "caregiver_support" not in task_context.task_hints):
            return None
        content = (
            "Task card for today: encourage small frequent meals, watch for increased fatigue during transfers, "
            "and note whether sleep disruption is continuing tonight. If appetite drops further or walking becomes less steady, update the care team."
        )
        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.CAREGIVER,
            target_recipient_id=caregiver_id,
            proposal_type=ProposalType.CAREGIVER_TASK_CARD,
            title="Caregiver support task card",
            content=content,
            structured_payload={
                "tasks": ["offer small meals", "assist safe transfers", "observe appetite and sleep"],
                "observation_prompt": "Record appetite, transfer effort, and overnight sleep quality.",
            },
            supporting_evidence=[item for item in [observation, mobility_signal, poor_sleep] if item],
            confidence_score=0.72,
            estimated_risk_level=RiskLevel.MEDIUM,
            rationale="Caregiver task cards help coordinate daily observations and support when mobility and sleep decline.",
            consent_scope_required="caregiver_tasks",
            policy_tags=["caregiver_support", "privacy_bounded"],
        )


class ClinicianCopilotAgent(BaseAgent):
    name = "ClinicianCopilotAgent"

    def generate_proposal(self, patient_state: PatientStateView, task_context: TaskContext) -> ProposalDraft | None:
        if "clinician_summary" not in task_context.task_hints:
            return None
        evidence = (
            patient_state.recent_vitals[:3]
            + patient_state.adherence_events[:2]
            + patient_state.symptoms[:2]
            + patient_state.ambient_monitoring_events[:2]
        )[:7]
        lines = [
            f"7-day summary for patient {patient_state.demographics.get('first_name')}:",
            f"- Current risk status: {patient_state.current_risk_status}.",
            f"- Adherence events reviewed: {len(patient_state.adherence_events)} with missed medication pattern noted.",
            f"- Symptom reports: {len(patient_state.symptoms)} recent narrative entries.",
            f"- Ambient signals: {len(patient_state.ambient_monitoring_events)} monitored events.",
            "- Suggested clinician focus: adherence barriers, sleep decline, mobility safety, and caregiver updates.",
        ]
        return ProposalDraft(
            source_agent=self.name,
            patient_id=patient_state.patient_id,
            encounter_context_id=task_context.encounter_context_id,
            target_recipient_type=RecipientType.CLINICIAN,
            proposal_type=ProposalType.CLINICIAN_SUMMARY,
            title="7-day clinician summary",
            content=" ".join(lines),
            structured_payload={"window_days": 7, "evidence_count": len(evidence)},
            supporting_evidence=evidence,
            confidence_score=0.81,
            estimated_risk_level=RiskLevel.MEDIUM if patient_state.current_risk_status != RiskLevel.LOW.value else RiskLevel.LOW,
            rationale="Clinicians benefit from concise evidence-backed recaps before reviewing the chart.",
            consent_scope_required="clinical_review",
            policy_tags=["clinician_summary", "signal_focused"],
        )

