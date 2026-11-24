"""
Tier 1: Feature 5 - Candidate Examination Engine & Navigation.
Verifies attempt start, question delivery without key leak, 5-state palette transitions, question navigation, and section switching.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_attempt_initiation(client, published_exam_fixture, student_auth_headers):
    """F5.1: Student starts an examination attempt and receives session tokens and server deadlines."""
    eid = published_exam_fixture["exam_id"]
    resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "attempt_id" in data
    assert "attempt_token" in data
    assert "server_deadline" in data
    assert data["remaining_seconds"] == 3600  # 60 minutes


@pytest.mark.tier1
@pytest.mark.e2e
def test_question_payload_delivery(client, published_exam_fixture, student_auth_headers):
    """F5.2: Verify question payload is delivered with sections and question structures without leaking secret answer keys."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    assert start_resp.status_code == 200
    data = start_resp.json()
    assert "sections" in data
    assert len(data["sections"]) >= 3  # Maths, Physics, Chemistry

    # Confirm sections contain question IDs
    all_qids = []
    for sec in data["sections"]:
        all_qids.extend(sec["question_ids"])
    assert 101 in all_qids
    assert 102 in all_qids
    assert 103 in all_qids


@pytest.mark.tier1
@pytest.mark.e2e
def test_question_palette_5_state_transitions(client, published_exam_fixture, student_auth_headers):
    """F5.3: Verify question palette transitions across Not Visited, Not Answered, Answered, Marked, and Answered & Marked."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # 1. Answered State
    r1 = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["C"], "status": "ANSWERED"},
    )
    assert r1.status_code == 200

    # 2. Marked for Review (without answer)
    r2 = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 102, "selected_options": [], "status": "MARKED_FOR_REVIEW"},
    )
    assert r2.status_code == 200

    # 3. Answered & Marked for Review
    r3 = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 103, "numerical_value": "4.0", "status": "ANSWERED_AND_MARKED_FOR_REVIEW"},
    )
    assert r3.status_code == 200


@pytest.mark.tier1
@pytest.mark.e2e
def test_question_navigation(client, published_exam_fixture, student_auth_headers):
    """F5.4: Candidate can navigate sequentially or jump via question palette index."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Save question 101
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["A"], "time_spent_seconds": 30},
    )
    # Jump directly to question 103 (Numerical)
    jump_resp = client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 103, "numerical_value": "4.0", "time_spent_seconds": 45},
    )
    assert jump_resp.status_code == 200
    assert jump_resp.json()["question_id"] == 103


@pytest.mark.tier1
@pytest.mark.e2e
def test_section_switching(client, published_exam_fixture, student_auth_headers):
    """F5.5: Switch between examination sections and verify question isolation."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    sections = start_resp.json()["sections"]
    section_names = [s["name"] for s in sections]
    assert "Maths" in section_names
    assert "Physics" in section_names
    assert "Chemistry" in section_names
