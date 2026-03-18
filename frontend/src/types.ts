export type User = {
  id: string;
  email: string;
  full_name: string;
  role: "patient" | "caregiver" | "nurse" | "clinician" | "reviewer" | "admin";
  linked_patient_id?: string | null;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
};

export type PatientSummary = {
  id: string;
  first_name: string;
  last_name: string;
  current_risk_status: string;
  chronic_conditions: string[];
};

export type ConsentPreference = {
  recipient_type: string;
  recipient_user_id?: string | null;
  consent_scope: string;
  can_share: boolean;
  notes?: string | null;
};

export type PatientState = {
  patient_id: string;
  demographics: Record<string, string>;
  chronic_conditions: string[];
  medications: Array<Record<string, unknown>>;
  care_goals: string[];
  caregiver_relationships: Array<Record<string, unknown>>;
  consent_preferences: ConsentPreference[];
  appointments: Array<Record<string, unknown>>;
  recent_vitals: Array<Record<string, unknown>>;
  recent_wearable_trends: Array<Record<string, unknown>>;
  adherence_events: Array<Record<string, unknown>>;
  symptoms: Array<Record<string, unknown>>;
  functional_decline_indicators: Array<Record<string, unknown>>;
  ambient_monitoring_events: Array<Record<string, unknown>>;
  escalation_history: Array<Record<string, unknown>>;
  clinician_notes_summary?: string | null;
  communication_preferences: Record<string, unknown>;
  language_literacy_cultural_preferences: Record<string, unknown>;
  current_risk_status: string;
  pending_follow_ups: Array<Record<string, unknown>>;
  recent_events: Array<Record<string, unknown>>;
};

export type Proposal = {
  id: string;
  parent_proposal_id?: string | null;
  version_number: number;
  source_agent: string;
  target_recipient_type: string;
  proposal_type: string;
  title: string;
  content: string;
  status: string;
  estimated_risk_level: string;
  created_at: string;
};

export type Escalation = {
  id: string;
  patient_id: string;
  reason: string;
  severity: string;
  status: string;
  created_at: string;
};

export type HumanReviewCase = {
  id: string;
  patient_id: string;
  proposal_id?: string | null;
  status: string;
  reason: string;
  created_at: string;
  resolution?: Record<string, unknown> | null;
};

export type MetricsOverview = {
  proposals_approved_directly: number;
  proposals_revised: number;
  proposals_rerouted: number;
  escalations_created: number;
  proposals_rejected_and_regenerated: number;
  average_review_rounds: number;
  blocked_unsafe_outputs_count: number;
  recipient_mismatch_caught_by_review: number;
  consent_violations_caught_by_review: number;
};

export type CaregiverObservationResponse = {
  event: {
    id: string;
    patient_id: string;
    event_type: string;
    normalized_summary: string;
  };
  orchestration_run_id?: string | null;
  outcomes_count: number;
};
