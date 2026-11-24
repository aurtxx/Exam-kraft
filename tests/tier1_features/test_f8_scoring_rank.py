"""
Tier 1: Feature 8 - Automated Scoring Engine, Negative Marking & Percentile Rankings.
Verifies full score calculation, negative penalty deduction, multi-MCQ partial credits, cohort rankings, and percentiles.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_full_score_calculation(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """F8.1: Candidate answers all 3 questions correctly and receives full marks (3 + 4 + 4 = 11.0)."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Q101: Single MCQ (key=C, pos=3)
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["C"]},
    )
    # Q102: Multi MCQ (key=A,C, pos=4)
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 102, "selected_options": ["A", "C"]},
    )
    # Q103: Numerical (key=4, pos=4)
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 103, "numerical_value": "4.0"},
    )

    # Submit
    client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )

    # Evaluate
    eval_resp = client.post(
        f"/api/v1/examinations/{eid}/evaluate/",
        headers=org_admin_auth_headers,
    )
    assert eval_resp.status_code == 200
    rankings = eval_resp.json()["summary"]["rankings"]
    cand_res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand_res["total_score"] == 11.0
    assert cand_res["total_correct"] == 3


@pytest.mark.tier1
@pytest.mark.e2e
def test_negative_penalty_deduction(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """F8.2: Incorrect choice on single MCQ incurs configured negative penalty."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Q101 wrong option (A instead of C, penalty = -1)
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 101, "selected_options": ["A"]},
    )
    # Submit
    client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )

    eval_resp = client.post(
        f"/api/v1/examinations/{eid}/evaluate/",
        headers=org_admin_auth_headers,
    )
    rankings = eval_resp.json()["summary"]["rankings"]
    cand_res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand_res["total_score"] == -1.0
    assert cand_res["total_incorrect"] == 1


@pytest.mark.tier1
@pytest.mark.e2e
def test_partial_credit_for_multi_mcq(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """F8.3: Selecting 1 correct option out of {A, C} with no incorrect option yields partial credit (+1.0)."""
    eid = published_exam_fixture["exam_id"]
    start_resp = client.post(
        "/api/v1/student/attempts/start/",
        headers=student_auth_headers,
        json={"exam_id": eid},
    )
    att_id = start_resp.json()["attempt_id"]

    # Q102: Selected only ["A"] (partial_marks = 1.0)
    client.post(
        f"/api/v1/student/attempts/{att_id}/responses/",
        headers=student_auth_headers,
        json={"question_id": 102, "selected_options": ["A"]},
    )
    client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "MANUAL_SUBMIT"},
    )

    eval_resp = client.post(
        f"/api/v1/examinations/{eid}/evaluate/",
        headers=org_admin_auth_headers,
    )
    rankings = eval_resp.json()["summary"]["rankings"]
    cand_res = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand_res["total_score"] == 1.0


@pytest.mark.tier1
@pytest.mark.e2e
def test_cohort_ranking_order(client, published_exam_fixture, student_auth_headers, student2_auth_headers, org_admin_auth_headers):
    """F8.4: Multi-candidate cohort evaluation orders candidates strictly in descending score order."""
    eid = published_exam_fixture["exam_id"]

    # Candidate 1: scores 11.0
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att1 = s1.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 102, "selected_options": ["A", "C"]})
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 103, "numerical_value": "4.0"})
    client.post(f"/api/v1/student/attempts/{att1}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Candidate 2: scores 3.0 (only Q101 correct)
    s2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    att2 = s2.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 101, "selected_options": ["C"]})
    client.post(f"/api/v1/student/attempts/{att2}/submit/", headers=student2_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    assert len(rankings) == 2
    assert rankings[0]["attempt_id"] == att1
    assert rankings[0]["rank"] == 1
    assert rankings[1]["attempt_id"] == att2
    assert rankings[1]["rank"] == 2


@pytest.mark.tier1
@pytest.mark.e2e
def test_percentile_computation(client, published_exam_fixture, student_auth_headers, student2_auth_headers, org_admin_auth_headers):
    """F8.5: Percentile computation reflects (count_le / total) * 100 accurately."""
    eid = published_exam_fixture["exam_id"]

    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att1 = s1.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})
    client.post(f"/api/v1/student/attempts/{att1}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    s2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    att2 = s2.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att2}/submit/", headers=student2_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    top_cand = next(r for r in rankings if r["attempt_id"] == att1)
    bottom_cand = next(r for r in rankings if r["attempt_id"] == att2)

    assert top_cand["percentile"] == 100.0  # 2/2 * 100
    assert bottom_cand["percentile"] == 50.0  # 1/2 * 100
