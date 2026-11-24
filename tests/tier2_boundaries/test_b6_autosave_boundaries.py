"""
Tier 2: Boundary & Corner Cases - Feature 6: Dual-Layer Response Autosave & Recovery.
Tests missing question ID, invalid attempt ID, autosave after submit, late submission past grace period, and clearing response.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_autosave_missing_question_id_returns_400(client, published_exam_fixture, student_auth_headers):
    """B6.1: Autosave response payload missing question_id returns 400 MISSING_QUESTION_ID."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"selected_options": ["A"]},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MISSING_QUESTION_ID"


@pytest.mark.tier2
@pytest.mark.e2e
def test_autosave_nonexistent_attempt_returns_404(client, student_auth_headers):
    """B6.2: Autosave against an invalid or unknown attempt ID returns 404 ATTEMPT_NOT_FOUND."""
    resp = client.post(
        "/api/v1/student/attempts/nonexistent-att-999/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["A"]},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ATTEMPT_NOT_FOUND"


@pytest.mark.tier2
@pytest.mark.e2e
def test_autosave_after_submission_returns_403(client, published_exam_fixture, student_auth_headers):
    """B6.3: Post-submission autosave request returns 403 ATTEMPT_LOCKED."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["B"]},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ATTEMPT_LOCKED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_autosave_after_deadline_plus_grace_period_rejected(client, org_admin_auth_headers, student_auth_headers):
    """B6.4: Response saved after server_deadline + 15s grace period is strictly rejected with 403 DEADLINE_EXPIRED."""
    # Create an exam with 1 min duration and past start
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Quick Paper"})
    qpid = qp_res.json()["id"]
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={"id": 999, "question_type": "NUMERICAL", "key": "1"})

    ex_res = client.post("/api/v1/examinations/", headers=org_admin_auth_headers, json={"name": "Past Expired Exam", "question_paper_id": qpid, "duration_minutes": 1})
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Manually backdate server_deadline in state to simulate expired deadline
    from tests.mock_server.contract_app import state
    with state.lock:
        state.attempts[att_id]["server_deadline"] = "2020-01-01T00:00:00Z"

    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 999, "numerical_value": "1.0"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "DEADLINE_EXPIRED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_autosave_cleared_response_persistence(client, published_exam_fixture, student_auth_headers):
    """B6.5: Clearing a previously answered question (sending empty selected_options) persists the cleared status."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Select C
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"], "status": "ANSWERED"})

    # Clear Response
    clear_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": [], "status": "NOT_ANSWERED"},
    )
    assert clear_resp.status_code == 200

    # Verify recovery has empty selection
    rec = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    saved = rec.json()["existing_responses"]
    entry = saved.get(str(101)) or saved.get(101)
    assert entry["selected_options"] == []
    assert entry["status"] == "NOT_ANSWERED"
