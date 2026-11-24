"""
Tier 2: Boundary & Corner Cases - Feature 5: Candidate Engine & Attempt Navigation.
Tests nonexistent exam start, premature attempt launch, expired window launch, restarting submitted attempts, and lobby status.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_attempt_start_nonexistent_exam_returns_404(client, student_auth_headers):
    """B5.1: Attempting to start an exam that does not exist returns 404 EXAM_NOT_FOUND."""
    resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": "nonexistent-exam-xyz"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "EXAM_NOT_FOUND"


@pytest.mark.tier2
@pytest.mark.e2e
def test_attempt_start_before_start_window_rejected(client, org_admin_auth_headers, student_auth_headers):
    """B5.2: Candidate attempting to launch test before start_window opens returns 403 EXAM_NOT_STARTED."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Future Paper"})
    qpid = qp_res.json()["id"]
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={"question_type": "NUMERICAL", "key": "1"})

    # Future start window (year 2030)
    ex_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={
            "name": "Future Exam",
            "question_paper_id": qpid,
            "duration_minutes": 60,
            "start_window": "2030-01-01T00:00:00Z",
            "end_window": "2030-01-02T00:00:00Z",
        },
    )
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    start_res = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    assert start_res.status_code == 403
    assert start_res.json()["code"] == "EXAM_NOT_STARTED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_attempt_start_after_end_window_rejected(client, org_admin_auth_headers, student_auth_headers):
    """B5.3: Candidate attempting to launch test after end_window has passed returns 403 EXAM_EXPIRED."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Past Paper"})
    qpid = qp_res.json()["id"]
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={"question_type": "NUMERICAL", "key": "1"})

    # Past window (year 2020)
    ex_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={
            "name": "Past Exam",
            "question_paper_id": qpid,
            "duration_minutes": 60,
            "start_window": "2020-01-01T00:00:00Z",
            "end_window": "2020-01-02T00:00:00Z",
        },
    )
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    start_res = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    assert start_res.status_code == 403
    assert start_res.json()["code"] == "EXAM_EXPIRED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_restarting_already_submitted_attempt_rejected(client, published_exam_fixture, student_auth_headers):
    """B5.4: Calling /start/ after attempt has been SUBMITTED returns 409 ALREADY_SUBMITTED."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = start_resp.json()["attempt_id"]

    # Submit
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Try starting again
    restart_resp = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    assert restart_resp.status_code == 409
    assert restart_resp.json()["code"] == "ALREADY_SUBMITTED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_unassigned_exam_lobby_status(client, org_admin_auth_headers, student_auth_headers):
    """B5.5: Draft examination lobby returns can_start = False."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Draft Paper"})
    qpid = qp_res.json()["id"]
    ex_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Draft Exam", "question_paper_id": qpid, "duration_minutes": 60},
    )
    eid = ex_res.json()["id"]

    lobby_res = client.get(f"/api/v1/student/lobby/{eid}/", headers=student_auth_headers)
    assert lobby_res.status_code == 200
    assert lobby_res.json()["can_start"] is False
