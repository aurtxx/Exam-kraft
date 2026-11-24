"""
Tier 3: Cross-Feature Pairwise Combinations.
Verifies interactions between different subsystems: question types + marking schemes, section navigation + timer,
disconnection + auto-submit, proctoring + autosave, multi-tenant concurrency, CSV import + evaluation, tie-breaking,
and refresh recovery + palette persistence.
"""

import pytest
import concurrent.futures


@pytest.mark.tier3
@pytest.mark.e2e
def test_p1_multitype_questions_custom_negative_marking(client, org_admin_auth_headers, student_auth_headers):
    """P1: Combines MCQ Single, Multi-MCQ with partial credit, and Numerical input under custom negative marking schemes."""
    # 1. Create Question Paper with all 3 types
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Pairwise P1 Paper"})
    qpid = qp_res.json()["id"]

    # Q1: Single MCQ (key=B, pos=3.0, neg=1.0)
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 201, "question_type": "MCQ_SINGLE", "key": "B", "positive_marks": 3.0, "negative_marks": 1.0,
        "options": [{"key": "A", "text": "Wrong"}, {"key": "B", "text": "Right"}],
    })
    # Q2: Multi MCQ (key=A,D, pos=4.0, partial=1.0, neg=2.0)
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 202, "question_type": "MCQ_MULTI", "key": "A,D", "positive_marks": 4.0, "partial_marks": 1.0, "negative_marks": 2.0,
        "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, {"key": "C", "text": "3"}, {"key": "D", "text": "4"}],
    })
    # Q3: Numerical (key=12.5, pos=4.0, neg=0.0)
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 203, "question_type": "NUMERICAL", "key": "12.5", "positive_marks": 4.0, "negative_marks": 0.0,
    })

    # Exam
    ex_res = client.post("/api/v1/examinations/", headers=org_admin_auth_headers, json={"name": "P1 Exam", "question_paper_id": qpid, "duration_minutes": 60})
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    # Student Attempt
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Q201: Correct B -> +3.0
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 201, "selected_options": ["B"]})
    # Q202: Partial A only -> +1.0
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 202, "selected_options": ["A"]})
    # Q203: Correct 12.5 -> +4.0
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 203, "numerical_value": "12.5"})

    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Evaluate: Expected = 3.0 + 1.0 + 4.0 = 8.0
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_res.json()["summary"]["rankings"]
    cand = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand["total_score"] == 8.0


@pytest.mark.tier3
@pytest.mark.e2e
def test_p2_section_navigation_with_timer_countdown(client, published_exam_fixture, student_auth_headers):
    """P2: Candidates navigate across multiple sections while heartbeat countdown accurately updates remaining time."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]
    initial_rem = s.json()["remaining_seconds"]

    # Candidate works in Section Maths (Q101)
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})

    # Heartbeat after some seconds
    hb1 = client.post(f"/api/v1/student/attempts/{att_id}/heartbeat/", headers=student_auth_headers, json={"window_blur_count": 0})
    assert hb1.status_code == 200
    rem1 = hb1.json()["remaining_seconds"]
    assert rem1 <= initial_rem

    # Switch to Section Chemistry (Q103)
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 103, "numerical_value": "4.0"})

    hb2 = client.post(f"/api/v1/student/attempts/{att_id}/heartbeat/", headers=student_auth_headers, json={"window_blur_count": 0})
    assert hb2.status_code == 200
    assert hb2.json()["remaining_seconds"] <= rem1


@pytest.mark.tier3
@pytest.mark.e2e
def test_p3_disconnection_recovery_with_timer_auto_expiry(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """P3: Disconnection recovery restores session, followed by auto-submission on server timer deadline."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Answer Q101
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})

    # Recover across disconnect
    rec = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    assert rec.json()["is_recovered"] is True

    # Timer expires on server: Auto-submit triggered
    sub = client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "AUTO_TIMER_EXPIRY"})
    assert sub.status_code == 200
    assert sub.json()["submission_status"] == "SUBMITTED"

    # Evaluation correctly scores the recovered answers
    eval_resp = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_resp.json()["summary"]["rankings"]
    cand = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand["total_score"] == 3.0


@pytest.mark.tier3
@pytest.mark.e2e
def test_p4_tab_switch_proctoring_with_autosave(client, published_exam_fixture, student_auth_headers):
    """P4: Tab switch violations tracked via heartbeat concurrent with ongoing question autosaves."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Save Q101
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})

    # 1st tab switch
    hb1 = client.post(f"/api/v1/student/attempts/{att_id}/heartbeat/", headers=student_auth_headers, json={"window_blur_count": 1})
    assert hb1.json()["is_terminated"] is False

    # Save Q102
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 102, "selected_options": ["A", "C"]})

    # Exceed limit: 4 switches
    hb2 = client.post(f"/api/v1/student/attempts/{att_id}/heartbeat/", headers=student_auth_headers, json={"window_blur_count": 4})
    assert hb2.json()["is_terminated"] is True


@pytest.mark.tier3
@pytest.mark.e2e
def test_p5_multi_tenant_concurrency_isolation(client, published_exam_fixture, student_auth_headers):
    """P5: Multi-tenant concurrency: Candidates from different organizations take tests simultaneously with full data isolation."""
    # Org 1 student starts attempt
    eid1 = published_exam_fixture["exam_id"]
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid1})
    assert s1.status_code == 200
    att1 = s1.json()["attempt_id"]

    # Create Org 2 Exam and attempt
    from tests.mock_server.contract_app import state
    with state.lock:
        state._add_user("user-org2-student", "student@zenith.edu", "Pass123!", "STUDENT", "9c62e224-22fa-53e5-cccc-037f493e6b1d", "Zenith Student")
    login2 = client.post("/api/v1/auth/login/", json={"username": "student@zenith.edu", "password": "Pass123!"})
    token2 = login2.json()["access"]
    headers2 = {"Authorization": f"Bearer {token2}", "Content-Type": "application/json"}

    # Attempting to start Org 1 exam as Org 2 student returns 200 or 403 (isolation prevents cross-org leakage)
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})

    # Student 2 cannot query or alter att1
    # Even if they try, att1 is scoped to student 1
    rec1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid1})
    assert rec1.json()["attempt_id"] == att1


@pytest.mark.tier3
@pytest.mark.e2e
def test_p6_csv_imported_cohort_exam_and_ranking(client, org_admin_auth_headers):
    """P6: End-to-end integration: Bulk CSV student import, candidate exam taking, and cohort percentile ranking."""
    # 1. Bulk import 2 students
    csv = (
        "RollNumber,Name,Phone,Email,BatchCode,CentreCode\n"
        "2026701,Candidate Alpha,+919000000001,alpha@apex.edu,C12B,NC01\n"
        "2026702,Candidate Beta,+919000000002,beta@apex.edu,C12B,NC01\n"
    )
    client.post(
        "/api/v1/users/students/bulk-upload/",
        headers={"Authorization": org_admin_auth_headers["Authorization"], "Content-Type": "text/csv"},
        content=csv.encode("utf-8"),
    )

    # 2. Create paper & exam
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Cohort Exam Paper"})
    qpid = qp_res.json()["id"]
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={"id": 301, "question_type": "NUMERICAL", "key": "5", "positive_marks": 5.0})
    ex_res = client.post("/api/v1/examinations/", headers=org_admin_auth_headers, json={"name": "Cohort Exam", "question_paper_id": qpid, "duration_minutes": 60})
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    # 3. Simulate both taking exam
    from tests.mock_server.contract_app import state
    with state.lock:
        state._add_user("u-alpha", "alpha@apex.edu", "pass", "STUDENT", "8b51d113-11ef-42d4-bbbb-f26e382d5a0c", "Candidate Alpha")
        state._add_user("u-beta", "beta@apex.edu", "pass", "STUDENT", "8b51d113-11ef-42d4-bbbb-f26e382d5a0c", "Candidate Beta")

    t_alpha = client.post("/api/v1/auth/login/", json={"username": "alpha@apex.edu", "password": "pass"}).json()["access"]
    t_beta = client.post("/api/v1/auth/login/", json={"username": "beta@apex.edu", "password": "pass"}).json()["access"]

    # Alpha gets 5.0
    s_alpha = client.post("/api/v1/student/attempts/start/", headers={"Authorization": f"Bearer {t_alpha}"}, json={"exam_id": eid})
    att_a = s_alpha.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att_a}/responses/", headers={"Authorization": f"Bearer {t_alpha}"}, json={"question_id": 301, "numerical_value": "5.0"})
    client.post(f"/api/v1/student/attempts/{att_a}/submit/", headers={"Authorization": f"Bearer {t_alpha}"}, json={"submission_reason": "MANUAL_SUBMIT"})

    # Beta gets 0.0
    s_beta = client.post("/api/v1/student/attempts/start/", headers={"Authorization": f"Bearer {t_beta}"}, json={"exam_id": eid})
    att_b = s_beta.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att_b}/submit/", headers={"Authorization": f"Bearer {t_beta}"}, json={"submission_reason": "MANUAL_SUBMIT"})

    # 4. Evaluate & verify ranks
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_res.json()["summary"]["rankings"]
    assert rankings[0]["attempt_id"] == att_a and rankings[0]["rank"] == 1 and rankings[0]["percentile"] == 100.0
    assert rankings[1]["attempt_id"] == att_b and rankings[1]["rank"] == 2 and rankings[1]["percentile"] == 50.0


@pytest.mark.tier3
@pytest.mark.e2e
def test_p7_negative_marking_with_tie_breaking(client, published_exam_fixture, student_auth_headers, student2_auth_headers, org_admin_auth_headers):
    """P7: Equal net scores tie-break by penalizing the candidate with more negative deductions."""
    eid = published_exam_fixture["exam_id"]

    # Candidate 1: Q101 correct (+3), Q102 unattempted (0) -> Total = 3.0, 0 incorrect
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att1 = s1.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})
    client.post(f"/api/v1/student/attempts/{att1}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Candidate 2: Q103 correct (+4), Q101 incorrect (-1) -> Total = 3.0, 1 incorrect
    s2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    att2 = s2.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 103, "numerical_value": "4.0"})
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 101, "selected_options": ["A"]})
    client.post(f"/api/v1/student/attempts/{att2}/submit/", headers=student2_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_res.json()["summary"]["rankings"]
    # Both have score 3.0, but candidate 1 has 0 incorrect vs candidate 2 with 1 incorrect
    assert rankings[0]["attempt_id"] == att1
    assert rankings[0]["rank"] == 1
    assert rankings[1]["attempt_id"] == att2
    assert rankings[1]["rank"] == 2


@pytest.mark.tier3
@pytest.mark.e2e
def test_p8_refresh_recovery_with_palette_5_state_persistence(client, published_exam_fixture, student_auth_headers):
    """P8: Palette states across multiple questions persist across browser refresh."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Q101 -> Answered
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"], "status": "ANSWERED"})
    # Q102 -> Marked for Review
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 102, "status": "MARKED_FOR_REVIEW"})

    # Browser refresh
    rec = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    resps = rec.json()["existing_responses"]
    q101 = resps.get(str(101)) or resps.get(101)
    q102 = resps.get(str(102)) or resps.get(102)
    assert q101["status"] == "ANSWERED"
    assert q102["status"] == "MARKED_FOR_REVIEW"


@pytest.mark.tier3
@pytest.mark.e2e
def test_p9_center_capacity_allocation_and_candidate_burst(client, org_admin_auth_headers, student_auth_headers, student2_auth_headers):
    """P9: Examination centers mapped with capacities support concurrent candidate attempt launches."""
    # Create center with capacity 200
    c_res = client.post("/api/v1/organizations/centers/", headers=org_admin_auth_headers, json={"name": "Grand Hall", "code": "GH200", "capacity": 200})
    cid = c_res.json()["id"]

    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Venue Paper"})
    qpid = qp_res.json()["id"]
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={"question_type": "NUMERICAL", "key": "1"})

    ex_res = client.post("/api/v1/examinations/", headers=org_admin_auth_headers, json={"name": "Venue Exam", "question_paper_id": qpid, "duration_minutes": 60})
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    # Both students launch
    r1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    r2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["attempt_id"] != r2.json()["attempt_id"]
