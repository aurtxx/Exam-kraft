"""
Tier 1: Feature 4 - Examination Authoring, Scheduling & Publishing.
Verifies exam creation, duration, marking scheme attachment, candidate assignment, and transition to PUBLISHED.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_exam_creation(client, org_admin_auth_headers):
    """F4.1: Create an examination blueprint linked to a question paper."""
    qp_res = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Paper 1"},
    )
    qpid = qp_res.json()["id"]

    exam_payload = {
        "name": "JEE Mock Test 01",
        "question_paper_id": qpid,
        "duration_minutes": 180,
    }
    create_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json=exam_payload,
    )
    assert create_res.status_code == 201
    assert "id" in create_res.json()
    assert create_res.json()["status"] == "SUCCESS"


@pytest.mark.tier1
@pytest.mark.e2e
def test_section_duration_definition(client, org_admin_auth_headers):
    """F4.2: Define examination schedule window and duration in minutes."""
    qp_res = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Scheduled Paper"},
    )
    qpid = qp_res.json()["id"]

    exam_payload = {
        "name": "Mid-Term Assessment",
        "question_paper_id": qpid,
        "duration_minutes": 120,
        "start_window": "2026-11-25T09:00:00Z",
        "end_window": "2026-11-25T17:00:00Z",
    }
    resp = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json=exam_payload,
    )
    assert resp.status_code == 201
    eid = resp.json()["id"]

    list_res = client.get(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
    )
    assert list_res.status_code == 200
    exam = next(e for e in list_res.json()["examinations"] if e["id"] == eid)
    assert exam["duration_minutes"] == 120
    assert exam["start_window"] == "2026-11-25T09:00:00Z"


@pytest.mark.tier1
@pytest.mark.e2e
def test_marking_scheme_attachment(client, org_admin_auth_headers):
    """F4.3: Validate question paper attached to exam retains configured positive and negative marking rules."""
    qp_res = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Marking Test Paper"},
    )
    qpid = qp_res.json()["id"]

    # Add question with +4, -1
    client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={
            "question_type": "MCQ_SINGLE",
            "section": "Maths",
            "key": "A",
            "positive_marks": 4.0,
            "negative_marks": 1.0,
            "options": [{"key": "A", "text": "1"}],
        },
    )

    fetch_res = client.get(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
    )
    assert fetch_res.status_code == 200
    q = fetch_res.json()["questions"][0]
    assert q["positive_marks"] == 4.0
    assert q["negative_marks"] == 1.0


@pytest.mark.tier1
@pytest.mark.e2e
def test_candidate_assignment(client, org_admin_auth_headers):
    """F4.4: Assign specific candidate students to a scheduled examination."""
    qp_res = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Assignment Test Paper"},
    )
    qpid = qp_res.json()["id"]

    exam_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Assigned Exam", "question_paper_id": qpid, "duration_minutes": 60},
    )
    eid = exam_res.json()["id"]

    assign_payload = {
        "student_ids": ["user-student1", "user-student2"],
    }
    assign_res = client.post(
        f"/api/v1/examinations/{eid}/assign-candidates/",
        headers=org_admin_auth_headers,
        json=assign_payload,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_count"] == 2


@pytest.mark.tier1
@pytest.mark.e2e
def test_state_transition_to_published(client, org_admin_auth_headers):
    """F4.5: Transition exam state from DRAFT to PUBLISHED and verify question lock."""
    qp_res = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Publishable Paper"},
    )
    qpid = qp_res.json()["id"]

    # Must contain at least 1 question
    client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={
            "question_type": "MCQ_SINGLE",
            "section": "Physics",
            "key": "A",
            "positive_marks": 4.0,
            "negative_marks": 1.0,
            "options": [{"key": "A", "text": "True"}],
        },
    )

    exam_res = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Live Exam", "question_paper_id": qpid, "duration_minutes": 60},
    )
    eid = exam_res.json()["id"]

    # Publish
    pub_res = client.post(
        f"/api/v1/examinations/{eid}/publish/",
        headers=org_admin_auth_headers,
    )
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "PUBLISHED"

    # Verify paper is now locked from further edits
    edit_res = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={"question_type": "MCQ_SINGLE", "key": "B", "options": [{"key": "B", "text": "2"}]},
    )
    assert edit_res.status_code == 400
    assert edit_res.json()["code"] == "LOCKED"
