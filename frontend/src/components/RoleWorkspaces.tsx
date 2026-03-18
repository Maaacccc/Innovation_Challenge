import { useEffect, useMemo, useState, type ReactNode } from "react";

import { api } from "../api";
import type {
  CaregiverObservationResponse,
  ConsentPreference,
  Escalation,
  HumanReviewCase,
  MetricsOverview,
  PatientState,
  PatientSummary,
  Proposal,
  User,
} from "../types";

type WorkspaceProps = {
  token: string;
  user: User;
  onLogout: () => Promise<void>;
};

type WorkspaceData = {
  patients: PatientSummary[];
  selectedPatientId: string;
  setSelectedPatientId: (value: string) => void;
  state: PatientState | null;
  proposals: Proposal[];
  escalations: Escalation[];
  reviewQueue: HumanReviewCase[];
  metrics: MetricsOverview | null;
  error: string | null;
  stateAccessMessage: string | null;
  reload: () => Promise<void>;
};

type ReviewAction = "approve" | "reject" | "escalate";
type HistoryFilter = "all" | "patient" | "caregiver" | "clinician" | "nurse" | "internal_queue";

type RoleHistoryConfig = {
  key: HistoryFilter;
  label: string;
  description: string;
  responsibilities: string[];
  targets: string[];
};

const caregiverConsentScopes: Array<{ scope: string; label: string; help: string }> = [
  {
    scope: "caregiver_tasks",
    label: "Allow caregiver task cards",
    help: "Lets the system send concrete support tasks into the caregiver workspace.",
  },
  {
    scope: "basic_overview",
    label: "Allow caregiver basic overview",
    help: "Lets the caregiver see baseline health context like sleep, steps, blood pressure, and the next appointment.",
  },
  {
    scope: "general",
    label: "Allow broader caregiver updates",
    help: "Lets the caregiver see a broader summary beyond the basic overview when needed.",
  },
  {
    scope: "medication_reminders",
    label: "Allow medication-related caregiver support",
    help: "Lets the system share medication follow-up context with the caregiver.",
  },
];

const roleHistoryConfigs: RoleHistoryConfig[] = [
  {
    key: "all",
    label: "All recipient roles",
    description: "Use this to see the full reviewed history for the selected patient across every delivery destination.",
    responsibilities: [
      "Check whether routing matched the right recipient before release.",
      "Compare how the same patient story was rendered differently for each audience.",
      "Use this view when tracing lineage across review, rewrite, and escalation steps.",
    ],
    targets: [],
  },
  {
    key: "patient",
    label: "Patient-facing",
    description: "Patient messages should be supportive, plain-language, and non-diagnostic.",
    responsibilities: [
      "Use simple language and avoid diagnosis claims.",
      "Acknowledge uncertainty instead of sounding overly certain.",
      "Prefer practical next steps and calm tone over alarmist phrasing.",
    ],
    targets: ["patient"],
  },
  {
    key: "caregiver",
    label: "Caregiver-facing",
    description: "Caregiver outputs should be task-oriented, privacy-bounded, and useful during day-to-day care.",
    responsibilities: [
      "Focus on what the caregiver should observe or do next.",
      "Do not reveal broader clinical interpretation without consent.",
      "Keep the message action-focused and sensitive to caregiver burden.",
    ],
    targets: ["caregiver"],
  },
  {
    key: "clinician",
    label: "Clinician-facing",
    description: "Clinician summaries should be concise, evidence-backed, and signal-focused.",
    responsibilities: [
      "Lead with trends, red flags, and adherence changes.",
      "Avoid conversational filler and keep summaries concise.",
      "Ground each statement in observed events or trend evidence.",
    ],
    targets: ["clinician"],
  },
  {
    key: "nurse",
    label: "Nurse-facing",
    description: "Nurse items should support triage, follow-up prioritization, and structured escalation handling.",
    responsibilities: [
      "Highlight urgency, observations, and immediate next steps.",
      "Keep escalation rationale explicit and structured.",
      "Route unsafe coaching away from the patient into the triage workflow.",
    ],
    targets: ["nurse"],
  },
  {
    key: "internal_queue",
    label: "Internal queue",
    description: "Internal queue items are for blocked, rerouted, or escalation-oriented system handling.",
    responsibilities: [
      "Use this view to inspect proposals that should never have been delivered directly.",
      "Check why Risk Review rerouted or blocked release.",
      "Confirm that unresolved items stayed internal rather than reaching the patient or caregiver.",
    ],
    targets: ["internal_queue"],
  },
];

const reviewActionConfig: Record<ReviewAction, { label: string; help: string }> = {
  approve: {
    label: "Approve for release",
    help: "Use this when the current proposal is acceptable and can safely move forward as the reviewed output.",
  },
  reject: {
    label: "Reject and keep blocked",
    help: "Use this when the proposal should not be delivered and should stop here instead of reaching the recipient.",
  },
  escalate: {
    label: "Escalate to urgent handling",
    help: "Use this when normal delivery is the wrong channel and the item should become a manual escalation case.",
  },
};

function useWorkspaceData(token: string, user: User): WorkspaceData {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [state, setState] = useState<PatientState | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [reviewQueue, setReviewQueue] = useState<HumanReviewCase[]>([]);
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stateAccessMessage, setStateAccessMessage] = useState<string | null>(null);

  const privileged = new Set(["nurse", "clinician", "reviewer", "admin"]);
  const reviewerRoles = new Set(["reviewer", "admin"]);

  async function loadPatients() {
    const items = await api.listPatients(token);
    setPatients(items);
    setSelectedPatientId((current) => current || items[0]?.id || "");
  }

  async function loadWorkspace(patientId: string) {
    setError(null);
    setStateAccessMessage(null);

    try {
      const proposalPromise = api.getPatientProposals(patientId, token);
      const statePromise = api
        .getPatientState(patientId, token)
        .then((patientState) => {
          setState(patientState);
          return patientState;
        })
        .catch((fetchError) => {
          setState(null);
          setStateAccessMessage(fetchError instanceof Error ? fetchError.message : "Detailed patient state is not visible for this role.");
          return null;
        });

      const sidecarPromises: Promise<unknown>[] = [];
      if (privileged.has(user.role)) {
        sidecarPromises.push(
          api.getEscalations(token).then((items) => setEscalations(items)),
          api.getMetrics(token).then((overview) => setMetrics(overview)),
        );
      } else {
        setEscalations([]);
        setMetrics(null);
      }

      if (reviewerRoles.has(user.role)) {
        sidecarPromises.push(api.getHumanReviewQueue(token).then((items) => setReviewQueue(items)));
      } else {
        setReviewQueue([]);
      }

      const [proposalResult] = await Promise.all([proposalPromise, statePromise, ...sidecarPromises]);
      setProposals(proposalResult as Proposal[]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load workspace");
    }
  }

  useEffect(() => {
    void loadPatients();
  }, []);

  useEffect(() => {
    if (selectedPatientId) {
      void loadWorkspace(selectedPatientId);
    }
  }, [selectedPatientId]);

  async function reload() {
    if (selectedPatientId) {
      await loadWorkspace(selectedPatientId);
    }
  }

  return {
    patients,
    selectedPatientId,
    setSelectedPatientId,
    state,
    proposals,
    escalations,
    reviewQueue,
    metrics,
    error,
    stateAccessMessage,
    reload,
  };
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function StackList({
  items,
  emptyText,
  render,
}: {
  items: unknown[];
  emptyText: string;
  render: (item: unknown, index: number) => React.ReactNode;
}) {
  if (items.length === 0) {
    return <p>{emptyText}</p>;
  }
  return <ul className="stack-list">{items.map((item, index) => render(item, index))}</ul>;
}

function WorkspaceHeader({
  title,
  subtitle,
  user,
  patients,
  selectedPatientId,
  setSelectedPatientId,
  onLogout,
}: {
  title: string;
  subtitle: string;
  user: User;
  patients: PatientSummary[];
  selectedPatientId: string;
  setSelectedPatientId: (value: string) => void;
  onLogout: () => Promise<void>;
}) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">Role-specific workspace</p>
        <h1>{title}</h1>
        <p className="lede">
          {subtitle} Signed in as {user.full_name} ({user.role}).
        </p>
      </div>
      <div className="topbar-actions">
        {patients.length > 0 ? (
          <select value={selectedPatientId} onChange={(event) => setSelectedPatientId(event.target.value)}>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.first_name} {patient.last_name}
              </option>
            ))}
          </select>
        ) : null}
        <button className="secondary" onClick={() => void onLogout()}>
          Logout
        </button>
      </div>
    </header>
  );
}

function StatusStrip({
  items,
}: {
  items: Array<{ label: string; value: string | number }>;
}) {
  return (
    <section className="status-strip">
      {items.map((item) => (
        <article key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      ))}
    </section>
  );
}

function ProposalList({
  proposals,
  emptyText,
}: {
  proposals: Proposal[];
  emptyText: string;
}) {
  return (
    <StackList
      items={proposals}
      emptyText={emptyText}
      render={(item) => {
        const proposal = item as Proposal;
        return (
          <li key={proposal.id}>
            <strong>{proposal.title}</strong>
            <p>{proposal.content}</p>
            <small>
              {proposal.source_agent} · {proposal.target_recipient_type} · {proposal.status} · v{proposal.version_number}
            </small>
          </li>
        );
      }}
    />
  );
}

function findLatestEvent(state: PatientState | null, eventType: string): Record<string, unknown> | null {
  if (!state) {
    return null;
  }
  const pools = [
    state.recent_wearable_trends,
    state.recent_vitals,
    state.recent_events,
    state.adherence_events,
  ];
  for (const pool of pools) {
    const match = pool.find((item: Record<string, unknown>) => String(item.event_type) === eventType);
    if (match) {
      return match;
    }
  }
  return null;
}

function formatEventMetric(event: Record<string, unknown> | null, fallback = "Not available"): string {
  if (!event) {
    return fallback;
  }
  const payload = (event.payload as Record<string, unknown> | undefined) ?? {};
  const value = payload.value;
  const unit = typeof payload.unit === "string" ? payload.unit : "";
  if (typeof value === "number") {
    return `${value}${unit ? ` ${unit}` : ""}`;
  }
  if (value && typeof value === "object" && "systolic" in value && "diastolic" in value) {
    const bloodPressure = value as { systolic: number; diastolic: number };
    return `${bloodPressure.systolic}/${bloodPressure.diastolic}${unit ? ` ${unit}` : ""}`;
  }
  return typeof event.summary === "string" ? event.summary : fallback;
}

function formatAppointment(state: PatientState | null): string {
  if (!state || state.appointments.length === 0) {
    return "No upcoming visit";
  }
  const nextAppointment = state.appointments[0];
  return `${String(nextAppointment.provider_name)} · ${String(nextAppointment.status)}`;
}

function buildOverviewCards(state: PatientState | null): Array<{ label: string; value: string; help: string }> {
  return [
    {
      label: "Sleep",
      value: formatEventMetric(findLatestEvent(state, "sleep_duration"), "Not shared"),
      help: "Most recent recorded sleep duration.",
    },
    {
      label: "Steps",
      value: formatEventMetric(findLatestEvent(state, "step_count"), "Not shared"),
      help: "Most recent activity count or step trend.",
    },
    {
      label: "Blood pressure",
      value: formatEventMetric(findLatestEvent(state, "blood_pressure"), "Not shared"),
      help: "Most recent recorded blood pressure reading.",
    },
    {
      label: "Next appointment",
      value: formatAppointment(state),
      help: "Upcoming visit currently on the care plan.",
    },
  ];
}

function OverviewGrid({ state }: { state: PatientState | null }) {
  const cards = buildOverviewCards(state);
  return (
    <div className="overview-grid">
      {cards.map((card) => (
        <article key={card.label} className="overview-card">
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <p>{card.help}</p>
        </article>
      ))}
    </div>
  );
}

function BasicsList({ state }: { state: PatientState | null }) {
  const conditions = state?.chronic_conditions.join(", ") || "Not shared";
  const goals = state?.care_goals.join(", ") || "No active goals listed";
  const medications = state?.medications.map((item) => String(item.name)).join(", ") || "Not shared";
  return (
    <ul className="stack-list">
      <li>
        <strong>Chronic conditions</strong>
        <p>{conditions}</p>
      </li>
      <li>
        <strong>Current goals</strong>
        <p>{goals}</p>
      </li>
      <li>
        <strong>Medications in view</strong>
        <p>{medications}</p>
      </li>
    </ul>
  );
}

function PatientPortal({ token, user, onLogout }: WorkspaceProps) {
  const workspace = useWorkspaceData(token, user);
  const patientFacing = workspace.proposals.filter(
    (proposal) =>
      proposal.target_recipient_type === "patient" &&
      (proposal.status === "approved" || proposal.status === "delivered"),
  );
  const [savingScope, setSavingScope] = useState<string | null>(null);
  const [consentMessage, setConsentMessage] = useState<string | null>(null);

  const consentMap = useMemo(() => {
    const map = new Map<string, ConsentPreference>();
    (workspace.state?.consent_preferences ?? []).forEach((item) => {
      if (item.recipient_type === "caregiver") {
        map.set(item.consent_scope, item);
      }
    });
    return map;
  }, [workspace.state]);

  async function updateConsent(scope: string, canShare: boolean) {
    if (!workspace.selectedPatientId) {
      return;
    }
    setSavingScope(scope);
    setConsentMessage(null);
    try {
      await api.updateCaregiverConsent(
        workspace.selectedPatientId,
        {
          consent_scope: scope,
          can_share: canShare,
          notes: canShare ? "Updated by patient from patient workspace." : "Revoked by patient from patient workspace.",
        },
        token,
      );
      setConsentMessage("Caregiver visibility preference updated.");
      await workspace.reload();
    } catch (error) {
      setConsentMessage(error instanceof Error ? error.message : "Unable to update preference.");
    } finally {
      setSavingScope(null);
    }
  }

  return (
    <main className="dashboard-shell">
      <WorkspaceHeader
        title="Patient care companion"
        subtitle="This view shows approved patient-safe items, a personal health overview, and explicit controls for what the caregiver is allowed to see."
        user={user}
        patients={workspace.patients}
        selectedPatientId={workspace.selectedPatientId}
        setSelectedPatientId={workspace.setSelectedPatientId}
        onLogout={onLogout}
      />
      <StatusStrip
        items={[
          { label: "Approved items", value: patientFacing.length },
          { label: "Risk", value: workspace.state?.current_risk_status ?? "unknown" },
          { label: "Sleep", value: formatEventMetric(findLatestEvent(workspace.state, "sleep_duration"), "Not available") },
          { label: "Caregiver permissions", value: caregiverConsentScopes.filter((item) => consentMap.get(item.scope)?.can_share).length },
        ]}
      />
      {workspace.error ? <p className="error-text">{workspace.error}</p> : null}
      <section className="grid two-col">
        <Section title="Approved care items">
          <ProposalList proposals={patientFacing} emptyText="No approved patient-facing care items are available." />
        </Section>
        <Section title="Basic health overview">
          <OverviewGrid state={workspace.state} />
        </Section>
      </section>
      <section className="grid two-col">
        <Section title="Caregiver sharing choices">
          {consentMessage ? <p className="info-text">{consentMessage}</p> : null}
          <ul className="stack-list">
            {caregiverConsentScopes.map((item) => {
              const enabled = consentMap.get(item.scope)?.can_share ?? false;
              return (
                <li key={item.scope}>
                  <strong>{item.label}</strong>
                  <p>{item.help}</p>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={enabled}
                      disabled={savingScope === item.scope}
                      onChange={(event) => void updateConsent(item.scope, event.target.checked)}
                    />
                    <span>{enabled ? "Allowed" : "Not allowed"}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </Section>
        <Section title="Current plan snapshot">
          <BasicsList state={workspace.state} />
        </Section>
      </section>
      <Section title="Recent changes">
        <StackList
          items={workspace.state?.recent_events ?? []}
          emptyText="No recent events are visible."
          render={(item) => {
            const event = item as Record<string, string>;
            return (
              <li key={String(event.id)}>
                <strong>{String(event.event_type)}</strong>
                <p>{String(event.summary ?? "")}</p>
              </li>
            );
          }}
        />
      </Section>
    </main>
  );
}

function CaregiverPortal({ token, user, onLogout }: WorkspaceProps) {
  const workspace = useWorkspaceData(token, user);
  const caregiverCards = workspace.proposals.filter((proposal) => proposal.target_recipient_type === "caregiver");
  const [observationText, setObservationText] = useState("");
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submitObservation() {
    if (!workspace.selectedPatientId || !observationText.trim()) {
      return;
    }
    setSubmitting(true);
    setSubmitMessage(null);
    try {
      const result: CaregiverObservationResponse = await api.submitCaregiverObservation(
        workspace.selectedPatientId,
        observationText.trim(),
        token,
      );
      setObservationText("");
      setSubmitMessage(
        `Observation submitted. The system processed ${result.outcomes_count} follow-up item(s).`,
      );
      await workspace.reload();
    } catch (error) {
      setSubmitMessage(error instanceof Error ? error.message : "Unable to submit observation.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <WorkspaceHeader
        title="Caregiver task workspace"
        subtitle="This workspace now combines actual caregiver work with a patient-approved basic overview, so the caregiver can act with context instead of seeing empty privacy walls."
        user={user}
        patients={workspace.patients}
        selectedPatientId={workspace.selectedPatientId}
        setSelectedPatientId={workspace.setSelectedPatientId}
        onLogout={onLogout}
      />
      <StatusStrip
        items={[
          { label: "Task cards", value: caregiverCards.length },
          { label: "Risk", value: workspace.state?.current_risk_status ?? "unknown" },
          { label: "Sleep", value: formatEventMetric(findLatestEvent(workspace.state, "sleep_duration"), "Not shared") },
          { label: "Patient switch", value: workspace.patients.length },
        ]}
      />
      {workspace.error ? <p className="error-text">{workspace.error}</p> : null}
      {workspace.stateAccessMessage ? <p className="info-text">{workspace.stateAccessMessage}</p> : null}
      <p className="info-text">
        The caregiver view now shows patient-approved basics like sleep and blood pressure. Sensitive clinician notes
        and anything outside consent stay hidden automatically.
      </p>
      <section className="grid two-col">
        <Section title="Patient basic overview">
          <OverviewGrid state={workspace.state} />
        </Section>
        <Section title="Caregiver task cards">
          <ProposalList proposals={caregiverCards} emptyText="No caregiver task cards are currently available." />
        </Section>
      </section>
      <section className="grid two-col">
        <Section title="Submit caregiver observation">
          {submitMessage ? <p className="info-text">{submitMessage}</p> : null}
          <div className="form-stack">
            <textarea
              value={observationText}
              onChange={(event) => setObservationText(event.target.value)}
              placeholder="Example: appetite was poor at lunch, needed more support standing up, and slept poorly overnight."
              rows={6}
            />
            <button disabled={submitting || observationText.trim().length === 0} onClick={() => void submitObservation()}>
              {submitting ? "Submitting..." : "Submit observation"}
            </button>
          </div>
        </Section>
        <Section title="Visible care context">
          <BasicsList state={workspace.state} />
        </Section>
      </section>
    </main>
  );
}

function ClinicianWorkspace({ token, user, onLogout }: WorkspaceProps) {
  const workspace = useWorkspaceData(token, user);
  const clinicianSummaries = workspace.proposals.filter((proposal) => proposal.target_recipient_type === "clinician");

  return (
    <main className="dashboard-shell">
      <WorkspaceHeader
        title="Clinician review console"
        subtitle="This view emphasizes concise summaries, current risk, and escalated signal clusters."
        user={user}
        patients={workspace.patients}
        selectedPatientId={workspace.selectedPatientId}
        setSelectedPatientId={workspace.setSelectedPatientId}
        onLogout={onLogout}
      />
      <StatusStrip
        items={[
          { label: "Summaries", value: clinicianSummaries.length },
          { label: "Escalations", value: workspace.escalations.length },
          { label: "Risk", value: workspace.state?.current_risk_status ?? "unknown" },
          { label: "Sleep", value: formatEventMetric(findLatestEvent(workspace.state, "sleep_duration"), "Not available") },
        ]}
      />
      {workspace.error ? <p className="error-text">{workspace.error}</p> : null}
      <section className="grid two-col">
        <Section title="Clinician summaries">
          <ProposalList proposals={clinicianSummaries} emptyText="No clinician summaries are available." />
        </Section>
        <Section title="Escalation board">
          <StackList
            items={workspace.escalations}
            emptyText="No escalations are visible."
            render={(item) => {
              const escalation = item as Escalation;
              return (
                <li key={escalation.id}>
                  <strong>{escalation.reason}</strong>
                  <p>
                    {escalation.severity} · {escalation.status}
                  </p>
                </li>
              );
            }}
          />
        </Section>
      </section>
    </main>
  );
}

function NurseWorkspace({ token, user, onLogout }: WorkspaceProps) {
  const workspace = useWorkspaceData(token, user);
  const triageNotes = workspace.proposals.filter(
    (proposal) => proposal.target_recipient_type === "nurse" || proposal.target_recipient_type === "internal_queue",
  );

  return (
    <main className="dashboard-shell">
      <WorkspaceHeader
        title="Nurse triage board"
        subtitle="This workspace focuses on escalations, triage notes, and recent deterioration signals."
        user={user}
        patients={workspace.patients}
        selectedPatientId={workspace.selectedPatientId}
        setSelectedPatientId={workspace.setSelectedPatientId}
        onLogout={onLogout}
      />
      <StatusStrip
        items={[
          { label: "Triage items", value: triageNotes.length },
          { label: "Escalations", value: workspace.escalations.length },
          { label: "Risk", value: workspace.state?.current_risk_status ?? "unknown" },
          { label: "Recent events", value: workspace.state?.recent_events.length ?? 0 },
        ]}
      />
      {workspace.error ? <p className="error-text">{workspace.error}</p> : null}
      <section className="grid two-col">
        <Section title="Triage and internal queue">
          <ProposalList proposals={triageNotes} emptyText="No nurse-facing or internal queue items are available." />
        </Section>
        <Section title="Recent risk signals">
          <StackList
            items={workspace.state?.recent_events ?? []}
            emptyText="No recent event signals are visible."
            render={(item) => {
              const event = item as Record<string, string>;
              return (
                <li key={String(event.id)}>
                  <strong>{String(event.event_type)}</strong>
                  <p>{String(event.summary ?? "")}</p>
                </li>
              );
            }}
          />
        </Section>
      </section>
    </main>
  );
}

function ReviewerWorkspace({ token, user, onLogout }: WorkspaceProps) {
  const workspace = useWorkspaceData(token, user);
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>("all");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<ReviewAction | null>(null);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [submittingDecision, setSubmittingDecision] = useState(false);

  const patientMap = useMemo(() => {
    const map = new Map<string, PatientSummary>();
    workspace.patients.forEach((patient) => map.set(patient.id, patient));
    return map;
  }, [workspace.patients]);

  const patientName = useMemo(() => {
    const patient = patientMap.get(workspace.selectedPatientId);
    return patient ? `${patient.first_name} ${patient.last_name}` : "current patient";
  }, [patientMap, workspace.selectedPatientId]);

  const selectedRoleConfig = roleHistoryConfigs.find((item) => item.key === historyFilter) ?? roleHistoryConfigs[0];
  const openReviewQueue = useMemo(
    () => workspace.reviewQueue.filter((item) => item.status === "open"),
    [workspace.reviewQueue],
  );
  const filteredHistory = useMemo(() => {
    if (selectedRoleConfig.targets.length === 0) {
      return workspace.proposals;
    }
    return workspace.proposals.filter((proposal) => selectedRoleConfig.targets.includes(proposal.target_recipient_type));
  }, [selectedRoleConfig, workspace.proposals]);

  useEffect(() => {
    if (openReviewQueue.length === 0) {
      setSelectedCaseId(null);
      return;
    }
    const stillVisible = openReviewQueue.some((item) => item.id === selectedCaseId);
    if (!stillVisible) {
      setSelectedCaseId(openReviewQueue[0].id);
    }
  }, [openReviewQueue, selectedCaseId]);

  const selectedCase = openReviewQueue.find((item) => item.id === selectedCaseId) ?? null;
  const selectedCasePatient = selectedCase ? patientMap.get(selectedCase.patient_id) : null;
  const selectedProposal =
    selectedCase && selectedCase.proposal_id
      ? workspace.proposals.find((proposal) => proposal.id === selectedCase.proposal_id) ?? null
      : null;

  function focusCase(reviewCase: HumanReviewCase) {
    setSelectedCaseId(reviewCase.id);
    setSelectedAction(null);
    setDecisionNotes("");
    setActionMessage(null);
    if (reviewCase.patient_id !== workspace.selectedPatientId) {
      workspace.setSelectedPatientId(reviewCase.patient_id);
    }
  }

  async function resolveCase() {
    if (!selectedCase || !selectedAction) {
      return;
    }
    setSubmittingDecision(true);
    setActionMessage(null);
    try {
      const notes = decisionNotes.trim() || `${reviewActionConfig[selectedAction].label} by ${user.full_name}`;
      await api.resolveHumanReview(selectedCase.id, selectedAction, notes, token);
      setActionMessage("Reviewer decision saved.");
      setSelectedAction(null);
      setDecisionNotes("");
      await workspace.reload();
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "Unable to apply reviewer decision.");
    } finally {
      setSubmittingDecision(false);
    }
  }

  return (
    <main className="dashboard-shell">
      <WorkspaceHeader
        title="Reviewer operations console"
        subtitle={`This internal view starts with action-required work, then lets you inspect ${patientName}'s history by recipient role.`}
        user={user}
        patients={workspace.patients}
        selectedPatientId={workspace.selectedPatientId}
        setSelectedPatientId={workspace.setSelectedPatientId}
        onLogout={onLogout}
      />
      <StatusStrip
        items={[
          { label: "Risk", value: workspace.state?.current_risk_status ?? "unknown" },
          { label: "Proposals", value: workspace.proposals.length },
          { label: "Escalations", value: workspace.escalations.length },
          { label: "Open review cases", value: openReviewQueue.length },
        ]}
      />
      {workspace.error ? <p className="error-text">{workspace.error}</p> : null}
      <section className="grid two-col">
        <Section title="Action center">
          <StackList
            items={openReviewQueue}
            emptyText="No human review cases are currently open."
            render={(item) => {
              const reviewCase = item as HumanReviewCase;
              const patient = patientMap.get(reviewCase.patient_id);
              return (
                <li
                  key={reviewCase.id}
                  className={reviewCase.id === selectedCaseId ? "card-active" : undefined}
                  onClick={() => focusCase(reviewCase)}
                >
                  <strong>{reviewCase.reason}</strong>
                  <p>
                    {patient ? `${patient.first_name} ${patient.last_name}` : reviewCase.patient_id} · {reviewCase.status}
                  </p>
                  <small>Click to load this case into the decision workspace.</small>
                </li>
              );
            }}
          />
        </Section>
        <Section title="Decision workspace">
          {selectedCase ? (
            <div className="form-stack">
              <div className="detail-card">
                <strong>{selectedCasePatient ? `${selectedCasePatient.first_name} ${selectedCasePatient.last_name}` : selectedCase.patient_id}</strong>
                <p>{selectedCase.reason}</p>
                <small>Case status: {selectedCase.status}</small>
              </div>
              {selectedProposal ? (
                <div className="detail-card">
                  <strong>Linked proposal</strong>
                  <p>{selectedProposal.title}</p>
                  <small>
                    {selectedProposal.target_recipient_type} · {selectedProposal.source_agent} · v{selectedProposal.version_number}
                  </small>
                </div>
              ) : (
                <p className="info-text">This case is not tied to a currently visible proposal version yet.</p>
              )}
              <div className="option-stack">
                {(["approve", "reject", "escalate"] as ReviewAction[]).map((action) => (
                  <button
                    key={action}
                    className={selectedAction === action ? "option-card option-card-active" : "option-card"}
                    onClick={() => setSelectedAction(action)}
                  >
                    <strong>{reviewActionConfig[action].label}</strong>
                    <span>{reviewActionConfig[action].help}</span>
                  </button>
                ))}
              </div>
              {selectedAction ? <p className="info-text">{reviewActionConfig[selectedAction].help}</p> : null}
              <textarea
                value={decisionNotes}
                onChange={(event) => setDecisionNotes(event.target.value)}
                rows={4}
                placeholder="Add reviewer reasoning or handoff notes."
              />
              {actionMessage ? <p className="info-text">{actionMessage}</p> : null}
              <button disabled={!selectedAction || submittingDecision} onClick={() => void resolveCase()}>
                {submittingDecision ? "Applying decision..." : "Apply reviewer decision"}
              </button>
            </div>
          ) : (
            <p>No open case is selected.</p>
          )}
        </Section>
      </section>
      <section className="grid two-col">
        <Section title="Proposal history by recipient role">
          <div className="pill-row">
            {roleHistoryConfigs.map((item) => (
              <button
                key={item.key}
                className={historyFilter === item.key ? "pill-button pill-button-active" : "pill-button"}
                onClick={() => setHistoryFilter(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <ProposalList proposals={filteredHistory} emptyText="No proposals match this recipient role for the selected patient." />
        </Section>
        <Section title="Selected role responsibilities">
          <div className="detail-card">
            <strong>{selectedRoleConfig.label}</strong>
            <p>{selectedRoleConfig.description}</p>
          </div>
          <ul className="stack-list">
            {selectedRoleConfig.responsibilities.map((item) => (
              <li key={item}>
                <p>{item}</p>
              </li>
            ))}
          </ul>
        </Section>
      </section>
      <section className="grid two-col">
        <Section title="Active escalations">
          <StackList
            items={workspace.escalations}
            emptyText="No escalation cases are visible."
            render={(item) => {
              const escalation = item as Escalation;
              const patient = patientMap.get(escalation.patient_id);
              return (
                <li key={escalation.id}>
                  <strong>{escalation.reason}</strong>
                  <p>
                    {patient ? `${patient.first_name} ${patient.last_name}` : escalation.patient_id} · {escalation.severity} · {escalation.status}
                  </p>
                </li>
              );
            }}
          />
        </Section>
        <Section title="Safety metrics">
          {workspace.metrics ? (
            <dl className="metric-list">
              <div><dt>Direct approvals</dt><dd>{workspace.metrics.proposals_approved_directly}</dd></div>
              <div><dt>Revisions</dt><dd>{workspace.metrics.proposals_revised}</dd></div>
              <div><dt>Reroutes</dt><dd>{workspace.metrics.proposals_rerouted}</dd></div>
              <div><dt>Escalations</dt><dd>{workspace.metrics.escalations_created}</dd></div>
              <div><dt>Rejected and regenerated</dt><dd>{workspace.metrics.proposals_rejected_and_regenerated}</dd></div>
              <div><dt>Blocked unsafe outputs</dt><dd>{workspace.metrics.blocked_unsafe_outputs_count}</dd></div>
            </dl>
          ) : (
            <p>Metrics are unavailable.</p>
          )}
        </Section>
      </section>
    </main>
  );
}

export function RoleWorkspace(props: WorkspaceProps) {
  switch (props.user.role) {
    case "patient":
      return <PatientPortal {...props} />;
    case "caregiver":
      return <CaregiverPortal {...props} />;
    case "clinician":
      return <ClinicianWorkspace {...props} />;
    case "nurse":
      return <NurseWorkspace {...props} />;
    case "reviewer":
    case "admin":
      return <ReviewerWorkspace {...props} />;
    default:
      return <ReviewerWorkspace {...props} />;
  }
}
