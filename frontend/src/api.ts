import type {
  CaregiverObservationResponse,
  ConsentPreference,
  Escalation,
  HumanReviewCase,
  MetricsOverview,
  PatientState,
  PatientSummary,
  Proposal,
  TokenResponse,
  User
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {})
    }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail ?? `Request failed with ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  login(email: string, password: string) {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
  },
  me(token: string) {
    return request<User>("/auth/me", {}, token);
  },
  logout(refreshToken: string, token: string) {
    return request<{ ok: boolean }>(
      "/auth/logout",
      { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
      token
    );
  },
  listPatients(token: string) {
    return request<PatientSummary[]>("/patients", {}, token);
  },
  getPatientState(patientId: string, token: string) {
    return request<PatientState>(`/patients/${patientId}/state`, {}, token);
  },
  getPatientProposals(patientId: string, token: string) {
    return request<Proposal[]>(`/patients/${patientId}/proposals`, {}, token);
  },
  getEscalations(token: string) {
    return request<Escalation[]>("/escalations", {}, token);
  },
  getHumanReviewQueue(token: string) {
    return request<HumanReviewCase[]>("/human-review", {}, token);
  },
  resolveHumanReview(caseId: string, action: string, notes: string, token: string) {
    return request<HumanReviewCase>(
      `/human-review/${caseId}/resolve`,
      { method: "POST", body: JSON.stringify({ action, notes }) },
      token
    );
  },
  getMetrics(token: string) {
    return request<MetricsOverview>("/metrics/overview", {}, token);
  },
  updateCaregiverConsent(
    patientId: string,
    payload: { consent_scope: string; can_share: boolean; notes?: string | null },
    token: string
  ) {
    return request<ConsentPreference[]>(
      `/patients/${patientId}/consent/caregiver`,
      { method: "POST", body: JSON.stringify(payload) },
      token
    );
  },
  submitCaregiverObservation(patientId: string, text: string, token: string) {
    return request<CaregiverObservationResponse>(
      `/patients/${patientId}/caregiver-observations`,
      { method: "POST", body: JSON.stringify({ text }) },
      token
    );
  }
};
