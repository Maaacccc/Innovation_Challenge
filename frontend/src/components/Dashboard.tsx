import { useEffect, useMemo, useState } from "react";

import { api } from "../api";
import type {
  Escalation,
  HumanReviewCase,
  MetricsOverview,
  PatientState,
  PatientSummary,
  Proposal,
  User
} from "../types";

type DashboardProps = {
  token: string;
  refreshToken: string;
  user: User;
  onLogout: () => Promise<void>;
};

const privilegedRoles = new Set(["nurse", "clinician", "reviewer", "admin"]);
const reviewerRoles = new Set(["reviewer", "admin"]);

export function Dashboard({ token, user, onLogout }: DashboardProps) {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [state, setState] = useState<PatientState | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [reviewQueue, setReviewQueue] = useState<HumanReviewCase[]>([]);
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null);
  const [activeTab, setActiveTab] = useState("timeline");
  const [error, setError] = useState<string | null>(null);

  async function loadPatients() {
    const items = await api.listPatients(token);
    setPatients(items);
    if (!selectedPatientId && items.length > 0) {
      setSelectedPatientId(items[0].id);
    }
  }

  async function loadDashboard(patientId: string) {
    setError(null);
    try {
      const [patientState, patientProposals] = await Promise.all([
        api.getPatientState(patientId, token),
        api.getPatientProposals(patientId, token)
      ]);
      setState(patientState);
      setProposals(patientProposals);
      if (privilegedRoles.has(user.role)) {
        const [escalationItems, metricsOverview] = await Promise.all([
          api.getEscalations(token),
          api.getMetrics(token)
        ]);
        setEscalations(escalationItems);
        setMetrics(metricsOverview);
      }
      if (reviewerRoles.has(user.role)) {
        setReviewQueue(await api.getHumanReviewQueue(token));
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load dashboard");
    }
  }

  useEffect(() => {
    void loadPatients();
  }, []);

  useEffect(() => {
    if (selectedPatientId) {
      void loadDashboard(selectedPatientId);
    }
  }, [selectedPatientId]);

  const clinicianSummaries = useMemo(
    () => proposals.filter((proposal) => proposal.target_recipient_type === "clinician"),
    [proposals]
  );

  const patientName = useMemo(() => {
    const patient = patients.find((item) => item.id === selectedPatientId);
    return patient ? `${patient.first_name} ${patient.last_name}` : "Patient";
  }, [patients, selectedPatientId]);

  async function resolveCase(caseId: string, action: string) {
    await api.resolveHumanReview(caseId, action, `${action} by ${user.full_name}`, token);
    if (selectedPatientId) {
      await loadDashboard(selectedPatientId);
    }
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Eldercare coordination console</p>
          <h1>{patientName}</h1>
          <p className="lede">
            Signed in as {user.full_name} ({user.role})
          </p>
        </div>
        <div className="topbar-actions">
          <select value={selectedPatientId} onChange={(event) => setSelectedPatientId(event.target.value)}>
            {patients.map((patient) => (
              <option key={patient.id} value={patient.id}>
                {patient.first_name} {patient.last_name}
              </option>
            ))}
          </select>
          <button className="secondary" onClick={() => void onLogout()}>
            Logout
          </button>
        </div>
      </header>

      <section className="status-strip">
        <article>
          <span>Risk</span>
          <strong>{state?.current_risk_status ?? "unknown"}</strong>
        </article>
        <article>
          <span>Proposals</span>
          <strong>{proposals.length}</strong>
        </article>
        <article>
          <span>Escalations</span>
          <strong>{escalations.length}</strong>
        </article>
        <article>
          <span>Human review</span>
          <strong>{reviewQueue.length}</strong>
        </article>
      </section>

      <nav className="tab-row">
        {["timeline", "proposals", "clinician", "escalations", "review"].map((tab) => (
          <button
            key={tab}
            className={activeTab === tab ? "tab-active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>

      {error ? <p className="error-text">{error}</p> : null}

      {activeTab === "timeline" && state ? (
        <section className="grid two-col">
          <article className="panel">
            <h2>Patient timeline</h2>
            <ul className="stack-list">
              {state.recent_events.map((event) => (
                <li key={String(event.id)}>
                  <strong>{String(event.event_type)}</strong>
                  <p>{String(event.summary ?? "")}</p>
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h2>Pending follow-ups</h2>
            <ul className="stack-list">
              {state.pending_follow_ups.length > 0 ? (
                state.pending_follow_ups.map((item) => (
                  <li key={String(item.proposal_id)}>
                    <strong>{String(item.title)}</strong>
                    <p>Status: {String(item.status)}</p>
                  </li>
                ))
              ) : (
                <li>No pending follow-ups.</li>
              )}
            </ul>
          </article>
        </section>
      ) : null}

      {activeTab === "proposals" ? (
        <section className="grid two-col">
          <article className="panel">
            <h2>Proposal queue</h2>
            <ul className="stack-list">
              {proposals.map((proposal) => (
                <li key={proposal.id}>
                  <strong>{proposal.title}</strong>
                  <p>{proposal.content}</p>
                  <small>
                    {proposal.source_agent} · {proposal.target_recipient_type} · {proposal.status} · v{proposal.version_number}
                  </small>
                </li>
              ))}
            </ul>
          </article>
          <article className="panel">
            <h2>Safety metrics</h2>
            {metrics ? (
              <dl className="metric-list">
                <div><dt>Direct approvals</dt><dd>{metrics.proposals_approved_directly}</dd></div>
                <div><dt>Revisions</dt><dd>{metrics.proposals_revised}</dd></div>
                <div><dt>Reroutes</dt><dd>{metrics.proposals_rerouted}</dd></div>
                <div><dt>Unsafe outputs blocked</dt><dd>{metrics.blocked_unsafe_outputs_count}</dd></div>
              </dl>
            ) : (
              <p>Metrics are available for privileged roles.</p>
            )}
          </article>
        </section>
      ) : null}

      {activeTab === "clinician" ? (
        <section className="panel">
          <h2>Clinician summary preview</h2>
          <ul className="stack-list">
            {clinicianSummaries.length > 0 ? (
              clinicianSummaries.map((proposal) => (
                <li key={proposal.id}>
                  <strong>{proposal.title}</strong>
                  <p>{proposal.content}</p>
                </li>
              ))
            ) : (
              <li>No clinician-targeted summaries yet.</li>
            )}
          </ul>
        </section>
      ) : null}

      {activeTab === "escalations" ? (
        <section className="panel">
          <h2>Escalation events</h2>
          <ul className="stack-list">
            {escalations.length > 0 ? (
              escalations.map((item) => (
                <li key={item.id}>
                  <strong>{item.reason}</strong>
                  <p>{item.severity} · {item.status}</p>
                </li>
              ))
            ) : (
              <li>No escalation cases visible.</li>
            )}
          </ul>
        </section>
      ) : null}

      {activeTab === "review" ? (
        <section className="panel">
          <h2>Human review queue</h2>
          {reviewerRoles.has(user.role) ? (
            <ul className="stack-list">
              {reviewQueue.length > 0 ? (
                reviewQueue.map((item) => (
                  <li key={item.id}>
                    <strong>{item.reason}</strong>
                    <p>Status: {item.status}</p>
                    <div className="button-row">
                      <button onClick={() => void resolveCase(item.id, "approve")}>Approve</button>
                      <button className="secondary" onClick={() => void resolveCase(item.id, "reject")}>
                        Reject
                      </button>
                      <button className="danger" onClick={() => void resolveCase(item.id, "escalate")}>
                        Escalate
                      </button>
                    </div>
                  </li>
                ))
              ) : (
                <li>No human review cases are currently open.</li>
              )}
            </ul>
          ) : (
            <p>This queue is restricted to reviewer and admin roles.</p>
          )}
        </section>
      ) : null}
    </main>
  );
}

