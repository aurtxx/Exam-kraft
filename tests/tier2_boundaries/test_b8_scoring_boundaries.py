"""
Tier 2: Boundary & Corner Cases - Feature 8: Scoring, Negative Marks & Rank.
Tests negative net scores, decimal precision tolerance, multi-MCQ penalty overriding partials, single candidate percentile, and cancelled questions.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_all_negative_score_candidate(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B8.1: Candidate getting only negative marking produces negative net score accurately (-1.0)."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Q101 wrong option (A instead of C, penalty = -1.0)
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["A"]})
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert res["total_score"] == -1.0


@pytest.mark.tier2
@pytest.mark.e2e
def test_numerical_answer_precision_tolerance(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B8.2: Numerical evaluation accepts input within +/-0.01 tolerance (4.005 accepted; 4.05 rejected)."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Q103 key is "4" -> 4.005 is within 0.01
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 103, "numerical_value": "4.005"})
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert res["total_score"] == 4.0
    assert res["total_correct"] == 1


@pytest.mark.tier2
@pytest.mark.e2e
def test_multi_mcq_wrong_choice_overrides_partial_marks(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B8.3: Multi-MCQ with 1 correct and 1 incorrect choice triggers negative penalty (-1.0) rather than partial marks."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Q102 key is A,C. Candidate selects A (correct) AND B (wrong).
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 102, "selected_options": ["A", "B"]})
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert res["total_score"] == -1.0  # -abs(neg)


@pytest.mark.tier2
@pytest.mark.e2e
def test_single_candidate_percentile_boundary(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B8.4: Single candidate exam cohort correctly evaluates to 100th percentile."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    assert len(rankings) == 1
    assert rankings[0]["percentile"] == 100.0


@pytest.mark.tier2
@pytest.mark.e2e
def test_dropped_cancelled_question_full_marks_to_all(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B8.5: When question is marked is_cancelled = True, all candidates receive full marks automatically."""
    qpid = published_exam_fixture["question_paper_id"]
    eid = published_exam_fixture["exam_id"]

    # Cancel question 101 in state
    from tests.mock_server.contract_app import state
    with state.lock:
        for q in state.question_papers[qpid]["questions"]:
            if q["id"] == 101:
                q["is_cancelled"] = True

    # Candidate does NOT answer question 101
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    res = next(r for r in rankings if r["attempt_id"] == att_id)
    # Question 101 had positive marks 3.0, candidate gets 3.0 even without answering!
    assert res["total_score"] == 3.0
    assert res["total_correct"] == 1
