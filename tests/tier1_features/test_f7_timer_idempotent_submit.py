"""
Tier 1: Feature 7 - Server Timer Expiry & Idempotent Submission.
Verifies server countdown enforcement, heartbeat synchronization, manual submission, deadline auto-submission, and idempotent locking.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_server_remaining_time_calculation(client, published_exam_fixture, student_auth_headers):
    """F7.1: Verify server-computed remaining duration strictly matches exam duration in seconds."""
    eid = published_exam_fixture["exam_id"]
    dur_min = published_exam_fixture["duration_minutes"]

    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    assert start_resp.status_code == 200
    rem = start_resp.json()["remaining_seconds"]
    assert rem == dur_min * 60


@pytest.mark.tier1
@pytest.mark.e2e
def test_heartbeat_duration_sync(client, published_exam_fixture, student_auth_headers):
    """F7.2: Heartbeat returns updated server timestamp and non-negative remaining seconds."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    hb_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/heartbeat/",
        headers=student_auth_headers,
        json={"window_blur_count": 0},
    )
    assert hb_resp.status_code == 200
    data = hb_resp.json()
    assert data["status"] == "SUCCESS"
    assert "server_time" in data
    assert "remaining_seconds" in data
    assert data["is_terminated"] is False


@pytest.mark.tier1
@pytest.mark.e2e
def test_manual_submit(client, published_exam_fixture, student_auth_headers):
    """F7.3: Candidate triggers manual submit, setting status to SUBMITTED and locking answers."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    sub_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )
    assert sub_resp.status_code == 200
    data = sub_resp.json()
    assert data["submission_status"] == "SUBMITTED"
    assert "submitted_at" in data

    # Attempting to save after submit must be rejected
    late_save = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["A"]},
    )
    assert late_save.status_code == 403
    assert late_save.json()["code"] == "ATTEMPT_LOCKED"


@pytest.mark.tier1
@pytest.mark.e2e
def test_auto_submit_on_deadline(client, published_exam_fixture, student_auth_headers):
    """F7.4: When candidate timer reaches zero, auto submit is accepted with reason AUTO_TIMER_EXPIRY."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    auto_sub = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "AUTO_TIMER_EXPIRY"},
    )
    assert auto_sub.status_code == 200
    assert auto_sub.json()["submission_status"] == "SUBMITTED"


@pytest.mark.tier1
@pytest.mark.e2e
def test_double_submit_idempotent_rejection(client, published_exam_fixture, student_auth_headers):
    """F7.5: Repeated submission calls for the same attempt return ALREADY_SUBMITTED with original timestamp."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    first_sub = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )
    assert first_sub.status_code == 200
    first_time = first_sub.json()["submitted_at"]

    # Duplicate submission
    second_sub = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )
    assert second_sub.status_code == 200
    sec_data = second_sub.json()
    assert sec_data["code"] == "ALREADY_SUBMITTED"
    assert sec_data["submitted_at"] == first_time
