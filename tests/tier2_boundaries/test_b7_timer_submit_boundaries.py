"""
Tier 2: Boundary & Corner Cases - Feature 7: Timer Enforcement & Idempotent Submission.
Tests negative heartbeat metrics, window blur termination threshold, late manual submit rejection, 404 submission, and rapid submit burst.
"""

import pytest
import concurrent.futures


@pytest.mark.tier2
@pytest.mark.e2e
def test_negative_heartbeat_blur_count_rejected(client, published_exam_fixture, student_auth_headers):
    """B7.1: Heartbeat payload with negative window_blur_count returns 400 INVALID_METRIC."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/heartbeat/",
        headers=student_auth_headers,
        json={"window_blur_count": -5},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_METRIC"


@pytest.mark.tier2
@pytest.mark.e2e
def test_excessive_window_blur_switches_triggers_termination_flag(client, published_exam_fixture, student_auth_headers):
    """B7.2: Window blur switches exceeding max limit (3) triggers is_terminated = True."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # 4 tab switches (exceeds threshold 3)
    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/heartbeat/",
        headers=student_auth_headers,
        json={"window_blur_count": 4},
    )
    assert resp.status_code == 200
    assert resp.json()["is_terminated"] is True


@pytest.mark.tier2
@pytest.mark.e2e
def test_submission_after_deadline_without_auto_flag_rejected(client, published_exam_fixture, student_auth_headers):
    """B7.3: Manual submission received past server deadline + grace period returns 403 DEADLINE_EXPIRED."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Simulate expired deadline
    from tests.mock_server.contract_app import state
    with state.lock:
        state.attempts[att_id]["server_deadline"] = "2020-01-01T00:00:00Z"

    resp = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "DEADLINE_EXPIRED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_submit_nonexistent_attempt_returns_404(client, student_auth_headers):
    """B7.4: Submission targeting a nonexistent attempt returns 404 ATTEMPT_NOT_FOUND."""
    resp = client.post(
        "/api/v1/student/attempts/nonexistent-att-888/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "ATTEMPT_NOT_FOUND"


@pytest.mark.tier2
@pytest.mark.e2e
def test_rapid_burst_double_submit_consistency(client, published_exam_fixture, student_auth_headers):
    """B7.5: Rapid succession of submit requests consistently reports successful submission without crashing."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    def do_submit():
        return client.post(
            f"/api/v1/student/attempts/{att_id}/submit/",
            headers=student_auth_headers,
            json={"submission_reason": "MANUAL_SUBMIT"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(do_submit)
        f2 = executor.submit(do_submit)
        f3 = executor.submit(do_submit)
        r1, r2, r3 = f1.result(), f2.result(), f3.result()

    assert all(r.status_code == 200 for r in [r1, r2, r3])
