"""
Tier 1: Feature 6 - Dual-Layer Autosave & Disconnection / Refresh Recovery.
Verifies response persistence, debounced updates, attempt restoration on browser refresh, offline queue recovery, and timestamps.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_response_persistence(client, published_exam_fixture, student_auth_headers):
    """F6.1: Autosave response endpoint persists candidate answers and returns confirmation."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    save_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={
            "question_id": 101,
            "selected_options": ["C"],
            "status": "ANSWERED",
            "time_spent_seconds": 25,
        },
    )
    assert save_resp.status_code == 200
    data = save_resp.json()
    assert data["status"] == "SUCCESS"
    assert data["question_id"] == 101
    assert "saved_at" in data


@pytest.mark.tier1
@pytest.mark.e2e
def test_debounce_autosave_sync(client, published_exam_fixture, student_auth_headers):
    """F6.2: Debounced autosave simulates rapid consecutive updates, storing the latest state."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Initial selection: A
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["A"], "time_spent_seconds": 10},
    )
    # Changed selection: C (final debounced state)
    final_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["C"], "time_spent_seconds": 20},
    )
    assert final_resp.status_code == 200

    # Restart attempt to recover saved response
    recovery_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    saved = recovery_resp.json()["existing_responses"]
    assert str(101) in saved or 101 in saved
    stored = saved.get(str(101)) or saved.get(101)
    assert stored["selected_options"] == ["C"]


@pytest.mark.tier1
@pytest.mark.e2e
def test_refresh_attempt_recovery(client, published_exam_fixture, student_auth_headers):
    """F6.3: Candidate refreshes browser tab, recovers attempt state without losing previous answers."""
    eid = published_exam_fixture["exam_id"]
    start1 = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id1 = start1.json()["attempt_id"]

    # Save answers to 101 and 103
    client.post(
        f"/api/v1/student/attempts/{att_id1}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["C"]},
    )
    client.post(
        f"/api/v1/student/attempts/{att_id1}/responses/",
        headers=student_auth_headers,
        json={"question_id": 103, "numerical_value": "4.0"},
    )

    # Browser Refresh -> Re-call start
    refresh_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    assert refresh_resp.status_code == 200
    ref_data = refresh_resp.json()
    assert ref_data["attempt_id"] == att_id1
    assert ref_data["is_recovered"] is True
    assert len(ref_data["existing_responses"]) == 2


@pytest.mark.tier1
@pytest.mark.e2e
def test_offline_state_recovery(client, published_exam_fixture, student_auth_headers):
    """F6.4: Offline queued responses sync to server successfully when connectivity is re-established."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Candidate was disconnected, now flushes batched answers
    batch_sync = [
        {"question_id": 101, "selected_options": ["C"], "status": "ANSWERED"},
        {"question_id": 102, "selected_options": ["A", "C"], "status": "ANSWERED"},
    ]
    for resp in batch_sync:
        res = client.post(
            f"/api/v1/student/attempts/{att_id}/responses/",
            headers=student_auth_headers,
            json=resp,
        )
        assert res.status_code == 200

    # Verify both recorded
    recovery = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    resps = recovery.json()["existing_responses"]
    assert len(resps) >= 2


@pytest.mark.tier1
@pytest.mark.e2e
def test_response_timestamp_verification(client, published_exam_fixture, student_auth_headers):
    """F6.5: Verify server records an ISO-8601 UTC timestamp on every saved response."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    save_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["C"]},
    )
    assert save_resp.status_code == 200
    saved_at = save_resp.json()["saved_at"]
    assert "T" in saved_at and ("Z" in saved_at or "+" in saved_at)
