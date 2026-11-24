"""
Tier 2: Boundary & Corner Cases - Feature 3: Question Bank & Authoring.
Tests negative marks exceeding positive marks, missing options, invalid numerical key, invalid question types, and locks.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_negative_marks_exceeding_positive_marks_rejected(client, org_admin_auth_headers):
    """B3.1: Defining negative marks penalty greater than positive marks awarded is rejected."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Boundary Paper"})
    qpid = qp_res.json()["id"]

    bad_payload = {
        "question_type": "MCQ_SINGLE",
        "key": "A",
        "positive_marks": 2.0,
        "negative_marks": 5.0,  # Negative penalty exceeds positive
        "options": [{"key": "A", "text": "1"}],
    }
    resp = client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json=bad_payload)
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_MARKING"


@pytest.mark.tier2
@pytest.mark.e2e
def test_mcq_missing_options_rejected(client, org_admin_auth_headers):
    """B3.2: MCQ authored without option choices returns 400 MISSING_OPTIONS."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Optionless Paper"})
    qpid = qp_res.json()["id"]

    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={"question_type": "MCQ_SINGLE", "key": "A", "options": []},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MISSING_OPTIONS"


@pytest.mark.tier2
@pytest.mark.e2e
def test_numerical_invalid_non_numeric_key_rejected(client, org_admin_auth_headers):
    """B3.3: Numerical question with non-numeric key string returns 400 INVALID_KEY."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Numeric Paper"})
    qpid = qp_res.json()["id"]

    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={"question_type": "NUMERICAL", "key": "not-a-number-xyz"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_KEY"


@pytest.mark.tier2
@pytest.mark.e2e
def test_unsupported_question_type_rejected(client, org_admin_auth_headers):
    """B3.4: Submitting an unknown/unsupported question type returns 400 INVALID_QUESTION_TYPE."""
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Type Paper"})
    qpid = qp_res.json()["id"]

    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={"question_type": "ESSAY_ARBITRARY", "key": "A"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_QUESTION_TYPE"


@pytest.mark.tier2
@pytest.mark.e2e
def test_modifying_questions_in_published_paper_rejected(client, published_exam_fixture, org_admin_auth_headers):
    """B3.5: Attempting to add or alter questions in a paper linked to a PUBLISHED exam returns 403 LOCKED."""
    qpid = published_exam_fixture["question_paper_id"]
    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={"question_type": "MCQ_SINGLE", "key": "A", "options": [{"key": "A", "text": "1"}]},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "LOCKED"
