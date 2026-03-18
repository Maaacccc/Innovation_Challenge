from __future__ import annotations

from datetime import datetime, timedelta


def _ingest(client, headers, patient_id, payload):
    response = client.post(
        "/api/events/ingest",
        json={"patient_id": patient_id, "encounter_context_id": "demo", "source": "test-suite", "event": payload},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _run(client, headers, patient_id, trigger_event_id=None, task_hints=None):
    response = client.post(
        "/api/orchestrations/run",
        json={
            "patient_id": patient_id,
            "trigger_event_id": trigger_event_id,
            "encounter_context_id": "demo",
            "task_hints": task_hints or [],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_scenario_missed_medication_pattern(client, auth_headers, patient_id):
    headers = auth_headers("nurse@example.com")
    first = _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "behavioral",
            "event_type": "medication_logging",
            "status": "missed",
            "recorded_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "details": {"slot": "evening"},
        },
    )
    second = _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "behavioral",
            "event_type": "medication_logging",
            "status": "missed",
            "recorded_at": datetime.utcnow().isoformat(),
            "details": {"slot": "evening"},
        },
    )
    result = _run(client, headers, patient_id, second["id"], ["medication_adherence"])
    delivered = [item for item in result["outcomes"] if item["delivery"]]
    assert delivered
    assert delivered[0]["proposal"]["target_recipient_type"] == "patient"
    assert delivered[0]["latest_review"]["decision"] == "APPROVE"


def test_scenario_caregiver_task_card(client, auth_headers, patient_id):
    headers = auth_headers("nurse@example.com")
    event = _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "conversational",
            "event_type": "caregiver_observation_text",
            "text": "Poor appetite today and transfer looked harder.",
            "recorded_at": datetime.utcnow().isoformat(),
            "author_role": "caregiver",
            "details": {},
        },
    )
    result = _run(client, headers, patient_id, event["id"], ["caregiver_support"])
    caregiver_outputs = [item for item in result["outcomes"] if item["proposal"]["target_recipient_type"] == "caregiver"]
    assert caregiver_outputs
    assert caregiver_outputs[0]["delivery"] is not None


def test_scenario_escalation_case(client, auth_headers, patient_id):
    headers = auth_headers("nurse@example.com")
    _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "ambient",
            "event_type": "fall_detected",
            "severity": "critical",
            "recorded_at": (datetime.utcnow() - timedelta(minutes=6)).isoformat(),
            "details": {"location": "bedroom"},
        },
    )
    inactivity = _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "ambient",
            "event_type": "prolonged_inactivity",
            "severity": "critical",
            "recorded_at": datetime.utcnow().isoformat(),
            "details": {"minutes": 45},
        },
    )
    result = _run(client, headers, patient_id, inactivity["id"])
    assert any(item["escalation"] is not None for item in result["outcomes"])


def test_scenario_reject_and_regenerate(client, auth_headers, patient_id):
    headers = auth_headers("nurse@example.com")
    event = _ingest(
        client,
        headers,
        patient_id,
        {
            "event_category": "behavioral",
            "event_type": "activity_drop",
            "status": "decline",
            "recorded_at": datetime.utcnow().isoformat(),
            "details": {"steps_change_pct": -35},
        },
    )
    result = _run(client, headers, patient_id, event["id"], ["force_risky_health_coach"])
    regenerated = [item for item in result["outcomes"] if item["proposal"]["source_agent"] == "RewriteOrRegenerationAgent"]
    assert regenerated
    assert regenerated[0]["proposal"]["version_number"] == 2
    assert regenerated[0]["latest_review"]["decision"] == "APPROVE"


def test_scenario_clinician_summary(client, auth_headers, patient_id):
    headers = auth_headers("clinician@example.com")
    result = _run(client, headers, patient_id, None, ["clinician_summary"])
    summaries = [item for item in result["outcomes"] if item["proposal"]["target_recipient_type"] == "clinician"]
    assert summaries
    assert summaries[0]["delivery"] is not None

