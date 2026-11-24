"""
Tier 2: Boundary & Corner Cases - Feature 4: Exam Authoring & Scheduling.
Tests zero duration, duration overflow (>24h), inverted schedule windows, publishing empty exams, and 404 assignments.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_exam_zero_or_negative_duration_rejected(client, org_admin_auth_headers):
    """B4.1: Defining exam duration <= 0 minutes returns 400 INVALID_DURATION."""
    resp = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Zero Duration Exam", "duration_minutes": 0},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_DURATION"


@pytest.mark.tier2
@pytest.mark.e2e
def test_exam_max_duration_overflow_rejected(client, org_admin_auth_headers):
    """B4.2: Defining exam duration greater than 1440 minutes (24h) returns 400 DURATION_OVERFLOW."""
    resp = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Excessive Exam", "duration_minutes": 2000},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "DURATION_OVERFLOW"


@pytest.mark.tier2
@pytest.mark.e2e
def test_exam_start_window_after_end_window_rejected(client, org_admin_auth_headers):
    """B4.3: Scheduling start_window chronologically after end_window returns 400 INVALID_WINDOW."""
    resp = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={
            "name": "Time Travel Exam",
            "duration_minutes": 60,
            "start_window": "2026-12-31T12:00:00Z",
            "end_window": "2026-12-01T12:00:00Z",  # End is before start
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_WINDOW"


@pytest.mark.tier2
@pytest.mark.e2e
def test_publishing_exam_with_zero_questions_rejected(client, org_admin_auth_headers):
    """B4.4: Attempting to publish an examination linked to an empty question paper returns 400 EMPTY_EXAM."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Empty Paper"})
    qpid = qp_res.json()["id"]

    ex_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Empty Live Exam", "question_paper_id": qpid, "duration_minutes": 60},
    )
    eid = ex_res.json()["id"]

    pub_res = client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)
    assert pub_res.status_code == 400
    assert pub_res.json()["code"] == "EMPTY_EXAM"


@pytest.mark.tier2
@pytest.mark.e2e
def test_assigning_candidates_to_nonexistent_exam_returns_404(client, org_admin_auth_headers):
    """B4.5: Candidate assignment targeting an unknown exam ID returns 404 NOT_FOUND."""
    resp = client.post(
        "/api/v1/examinations/nonexistent-exam-id-999/assign-candidates/",
        headers=org_admin_auth_headers,
        json={"student_ids": ["user-student1"]},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"
