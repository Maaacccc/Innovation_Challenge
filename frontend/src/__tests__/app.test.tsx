import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "../App";

const responses: Array<Response> = [];

function queueJson(payload: unknown) {
  responses.push(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    })
  );
}

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    responses.length = 0;
    globalThis.fetch = vi.fn(async () => {
      const response = responses.shift();
      if (!response) {
        throw new Error("No mocked response queued");
      }
      return response;
    }) as typeof fetch;
  });

  it("logs in and renders the dashboard", async () => {
    queueJson({
      access_token: "token",
      refresh_token: "refresh",
      token_type: "bearer",
      user: {
        id: "reviewer-1",
        email: "reviewer.w@example.com",
        full_name: "Reviewer W",
        role: "reviewer"
      }
    });
    queueJson([
      {
        id: "patient-1",
        first_name: "Maria",
        last_name: "Tan",
        current_risk_status: "medium",
        chronic_conditions: ["hypertension"]
      }
    ]);
    queueJson({
      patient_id: "patient-1",
      demographics: { first_name: "Maria", last_name: "Tan" },
      chronic_conditions: ["hypertension"],
      medications: [],
      care_goals: [],
      consent_preferences: [],
      recent_vitals: [],
      adherence_events: [],
      symptoms: [],
      ambient_monitoring_events: [],
      escalation_history: [],
      current_risk_status: "medium",
      pending_follow_ups: [],
      recent_events: []
    });
    queueJson([]);
    queueJson([]);
    queueJson({
      proposals_approved_directly: 1,
      proposals_revised: 0,
      proposals_rerouted: 0,
      escalations_created: 0,
      proposals_rejected_and_regenerated: 0,
      average_review_rounds: 1,
      blocked_unsafe_outputs_count: 0,
      recipient_mismatch_caught_by_review: 0,
      consent_violations_caught_by_review: 0
    });
    queueJson([]);

    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Reviewer operations console" })).toBeInTheDocument();
    });
    expect(screen.getByText(/action center/i)).toBeInTheDocument();
    expect(screen.getByText(/proposal history/i)).toBeInTheDocument();
  });
});
