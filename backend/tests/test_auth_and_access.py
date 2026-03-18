from __future__ import annotations


def test_login_refresh_and_logout(client):
    login = client.post("/api/auth/login", json={"email": "reviewer.w@example.com", "password": "demo1234"})
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200

    logout = client.post(
        "/api/auth/logout",
        json={"refresh_token": refreshed.json()["refresh_token"]},
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert logout.status_code == 200


def test_caregiver_state_access_shows_basic_overview_without_general_consent(client, auth_headers, patient_id):
    response = client.get(f"/api/patients/{patient_id}/state", headers=auth_headers("caregiver.1@example.com"))
    assert response.status_code == 200
    payload = response.json()
    assert payload["recent_wearable_trends"]
    assert payload["clinician_notes_summary"] is None


def test_patient_can_update_caregiver_consent(client, auth_headers, patient_id):
    response = client.post(
        f"/api/patients/{patient_id}/consent/caregiver",
        json={"consent_scope": "general", "can_share": True, "notes": "Allow broader updates"},
        headers=auth_headers("patient.a@example.com"),
    )
    assert response.status_code == 200
    payload = response.json()
    general_rule = next(item for item in payload if item["consent_scope"] == "general")
    assert general_rule["can_share"] is True


def test_caregiver_can_submit_observation(client, auth_headers, patient_id):
    response = client.post(
        f"/api/patients/{patient_id}/caregiver-observations",
        json={"text": "Observed lower appetite and slower transfers this morning."},
        headers=auth_headers("caregiver.1@example.com"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["event"]["event_type"] == "caregiver_observation_text"
    assert payload["outcomes_count"] >= 1


def test_reviewer_scope_is_limited_to_assigned_patients(client, auth_headers, patient_id):
    allowed = client.get("/api/patients", headers=auth_headers("reviewer.w@example.com"))
    denied = client.get(f"/api/patients/{patient_id}/state", headers=auth_headers("reviewer.m@example.com"))

    allowed_names = {(item["first_name"], item["last_name"]) for item in allowed.json()}
    assert ("Alice", "Tan") in allowed_names
    assert ("Clara", "Lee") in allowed_names
    assert ("Bernard", "Ong") not in allowed_names
    assert denied.status_code == 403
