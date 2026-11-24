"""
Tier 4: Real-World End-to-End Application Scenarios.
Simulates realistic, production-grade examination lifecycles:
- Scenario 1: Complete High-Stakes Exam Lifecycle (Org setup -> Batches -> Questions -> Publish -> Attempt -> Answer -> Submit -> Ranking)
- Scenario 2: Sudden Crash & Session Recovery Under Time Pressure (Mid-exam crash -> reconnect -> preserve responses -> finish)
- Scenario 3: Multi-Candidate Simultaneous Submission Burst (Multiple candidates submitting concurrently without deadlock)
- Scenario 4: Partial Answering with Timer Auto-Submit (50% answered -> timer auto-expiry -> server grading)
- Scenario 5: Complex Marking Scheme with Negative & Partial Grading (Multi-section, differential scoring rules, aggregate percentile)
"""

import pytest
import concurrent.futures


@pytest.mark.tier4
@pytest.mark.e2e
def test_scenario_1_complete_high_stakes_lifecycle(client):
    """
    Scenario 1: Complete High-Stakes Exam Lifecycle.
    1. SuperAdmin provisions Organization Admin.
    2. OrgAdmin creates Batches, Exam Centers, and enrolls Students.
    3. Faculty authors a 3-section Question Paper (Maths, Physics, Chemistry).
    4. OrgAdmin configures, schedules, assigns candidates, and publishes the Exam.
    5. Candidate enters Lobby, begins Attempt, answers all sections, and submits.
    6. System computes automated evaluation, ranks, percentiles, and student scorecards.
    """
    # 1. Login as Org Admin
    login_res = client.post("/api/v1/auth/login/", json={"username": "admin@apex.edu", "password": "SecurePassword123!"})
    assert login_res.status_code == 200
    org_token = login_res.json()["access"]
    org_headers = {"Authorization": f"Bearer {org_token}", "Content-Type": "application/json"}

    # 2. Setup Master Data
    b_res = client.post("/api/v1/organizations/batches/", headers=org_headers, json={"name": "Class 12 JEE Elite", "code": "JEE-2026"})
    assert b_res.status_code == 201
    bid = b_res.json()["id"]

    c_res = client.post("/api/v1/organizations/centers/", headers=org_headers, json={"name": "Main Campus CBT Lab", "code": "MC-LAB1", "capacity": 300})
    assert c_res.status_code == 201

    stud_res = client.post("/api/v1/users/students/", headers=org_headers, json={
        "roll_number": "2026999", "name": "Vikram Sarabhai", "batch_id": bid
    })
    assert stud_res.status_code == 201

    # 3. Question Paper Authoring
    qp_res = client.post("/api/v1/question-papers/", headers=org_headers, json={"name": "All-India JEE Advanced Grand Test", "duration_minutes": 180})
    qpid = qp_res.json()["id"]

    # Maths MCQ Single
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_headers, json={
        "id": 501, "section": "Maths", "question_type": "MCQ_SINGLE", "key": "D", "positive_marks": 4.0, "negative_marks": 1.0,
        "content_text": "Calculate $\\int_0^1 x^2 dx$", "options": [{"key": "A", "text": "1"}, {"key": "D", "text": "1/3"}]
    })
    # Physics MCQ Multi
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_headers, json={
        "id": 502, "section": "Physics", "question_type": "MCQ_MULTI", "key": "A,B", "positive_marks": 4.0, "partial_marks": 1.0, "negative_marks": 2.0,
        "content_text": "Select conservative forces", "options": [{"key": "A", "text": "Gravity"}, {"key": "B", "text": "Electrostatic"}]
    })
    # Chemistry Numerical
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_headers, json={
        "id": 503, "section": "Chemistry", "question_type": "NUMERICAL", "key": "7.0", "positive_marks": 4.0, "negative_marks": 0.0,
        "content_text": "pH of neutral water at 25C"
    })

    # 4. Schedule, Assign and Publish Exam
    ex_res = client.post("/api/v1/examinations/", headers=org_headers, json={
        "name": "All India JEE Grand Mock 2026", "question_paper_id": qpid, "duration_minutes": 180
    })
    eid = ex_res.json()["id"]

    client.post(f"/api/v1/examinations/{eid}/assign-candidates/", headers=org_headers, json={"student_ids": ["user-student1"]})
    pub_res = client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_headers)
    assert pub_res.status_code == 200

    # 5. Candidate Journey
    stud_login = client.post("/api/v1/auth/login/", json={"username": "student1@apex.edu", "password": "StudentPassword123!"})
    stud_token = stud_login.json()["access"]
    stud_headers = {"Authorization": f"Bearer {stud_token}", "Content-Type": "application/json"}

    # Check Lobby
    lobby_res = client.get(f"/api/v1/student/lobby/{eid}/", headers=stud_headers)
    assert lobby_res.status_code == 200 and lobby_res.json()["can_start"] is True

    # Start Attempt
    start_res = client.post("/api/v1/student/attempts/start/", headers=stud_headers, json={"exam_id": eid})
    assert start_res.status_code == 200
    att_id = start_res.json()["attempt_id"]

    # Answer all questions correctly
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=stud_headers, json={"question_id": 501, "selected_options": ["D"]})
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=stud_headers, json={"question_id": 502, "selected_options": ["A", "B"]})
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=stud_headers, json={"question_id": 503, "numerical_value": "7.0"})

    # Submit
    sub_res = client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=stud_headers, json={"submission_reason": "MANUAL_SUBMIT"})
    assert sub_res.status_code == 200 and sub_res.json()["submission_status"] == "SUBMITTED"

    # 6. Evaluation & Reports
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_headers)
    assert eval_res.status_code == 200
    rankings = eval_res.json()["summary"]["rankings"]
    assert len(rankings) == 1
    assert rankings[0]["total_score"] == 12.0  # 4 + 4 + 4
    assert rankings[0]["rank"] == 1
    assert rankings[0]["percentile"] == 100.0

    # Candidate views report card
    rep_res = client.get(f"/api/v1/attempts/{att_id}/report/", headers=stud_headers)
    assert rep_res.status_code == 200
    assert rep_res.json()["report"]["total_score"] == 12.0


@pytest.mark.tier4
@pytest.mark.e2e
def test_scenario_2_sudden_crash_and_session_recovery(client, published_exam_fixture, student_auth_headers):
    """
    Scenario 2: Sudden Crash & Session Recovery Under Time Pressure.
    1. Candidate starts exam, answers question 101, flags 102 for review.
    2. Simulated browser/computer crash occurs (session abruptly drops).
    3. Candidate launches browser again, logs in, and calls start endpoint.
    4. Server seamlessly restores attempt session, responses, palette statuses, and remaining time.
    5. Candidate completes remaining question 103 and successfully submits.
    """
    eid = published_exam_fixture["exam_id"]

    # Phase 1: Initial Answering
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s1.json()["attempt_id"]

    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={
        "question_id": 101, "selected_options": ["C"], "status": "ANSWERED", "time_spent_seconds": 40
    })
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={
        "question_id": 102, "selected_options": [], "status": "MARKED_FOR_REVIEW", "time_spent_seconds": 20
    })

    # Phase 2: Crash Simulation (New HTTP Client Session simulating fresh browser window)
    import os
    import httpx
    target_base_url = os.environ.get("BASE_URL", "").rstrip("/")
    if target_base_url:
        browser_client = httpx.Client(base_url=target_base_url, timeout=30.0)
    else:
        from tests.mock_server.contract_app import state, ContractHandler
        fresh_transport = httpx.MockTransport(ContractHandler(state))
        browser_client = httpx.Client(transport=fresh_transport, base_url="http://testserver", timeout=30.0)

    with browser_client as new_browser:
        # Re-login
        login = new_browser.post("/api/v1/auth/login/", json={"username": "student1@apex.edu", "password": "StudentPassword123!"})
        fresh_token = login.json()["access"]
        fresh_headers = {"Authorization": f"Bearer {fresh_token}", "Content-Type": "application/json"}

        # Recover attempt
        recovery = new_browser.post("/api/v1/student/attempts/start/", headers=fresh_headers, json={"exam_id": eid})
        assert recovery.status_code == 200
        rec_data = recovery.json()
        assert rec_data["attempt_id"] == att_id
        assert rec_data["is_recovered"] is True
        saved = rec_data["existing_responses"]
        assert (str(101) in saved or 101 in saved) and (str(102) in saved or 102 in saved)

        # Answer final question and submit
        new_browser.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=fresh_headers, json={
            "question_id": 103, "numerical_value": "4.0", "status": "ANSWERED"
        })
        sub = new_browser.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=fresh_headers, json={"submission_reason": "MANUAL_SUBMIT"})
        assert sub.status_code == 200
        assert sub.json()["submission_status"] == "SUBMITTED"


@pytest.mark.tier4
@pytest.mark.e2e
def test_scenario_3_multi_candidate_submission_burst(client, published_exam_fixture, student_auth_headers, student2_auth_headers, org_admin_auth_headers):
    """
    Scenario 3: Multi-Candidate Simultaneous Submission Burst.
    Simulates high-load submission traffic at exam deadline; verifies zero deadlocks and 100% submission recording.
    """
    eid = published_exam_fixture["exam_id"]

    # Start attempts for both candidates
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    s2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    att1 = s1.json()["attempt_id"]
    att2 = s2.json()["attempt_id"]

    # Answer questions
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 101, "selected_options": ["A"]})

    # Burst simultaneous submissions
    def submit(att, headers):
        return client.post(f"/api/v1/student/attempts/{att}/submit/", headers=headers, json={"submission_reason": "MANUAL_SUBMIT"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(submit, att1, student_auth_headers)
        f2 = executor.submit(submit, att2, student2_auth_headers)
        r1 = f1.result()
        r2 = f2.result()

    assert r1.status_code == 200 and r1.json()["submission_status"] == "SUBMITTED"
    assert r2.status_code == 200 and r2.json()["submission_status"] == "SUBMITTED"

    # Evaluation processes both cleanly
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    assert eval_res.status_code == 200
    assert len(eval_res.json()["summary"]["rankings"]) == 2


@pytest.mark.tier4
@pytest.mark.e2e
def test_scenario_4_partial_answering_with_timer_auto_submit(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """
    Scenario 4: Partial Answering with Timer Auto-Submit.
    Candidate answers 1 of 3 questions. Time runs out; server automatically finalizes attempt,
    grading only answered questions and treating unanswered as 0 marks.
    """
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    # Candidate answers only Q101 (Maths: +3.0)
    client.post(f"/api/v1/student/attempts/{att_id}/responses/", headers=student_auth_headers, json={"question_id": 101, "selected_options": ["C"]})

    # Timer auto-submit event triggered by deadline daemon
    auto_sub = client.post(
        f"/api/v1/student/attempts/{att_id}/submit/",
        headers=student_auth_headers,
        json={"submission_reason": "AUTO_TIMER_EXPIRY"},
    )
    assert auto_sub.status_code == 200
    assert auto_sub.json()["submission_status"] == "SUBMITTED"

    # Evaluate
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_res.json()["summary"]["rankings"]
    cand = next(r for r in rankings if r["attempt_id"] == att_id)
    assert cand["total_score"] == 3.0  # +3 for Q101, 0 for Q102, 0 for Q103
    assert cand["total_correct"] == 1
    assert cand["total_incorrect"] == 0


@pytest.mark.tier4
@pytest.mark.e2e
def test_scenario_5_complex_marking_scheme_and_percentiles(client, org_admin_auth_headers, student_auth_headers, student2_auth_headers):
    """
    Scenario 5: Complex Marking Scheme with Negative & Partial Grading.
    Differential rules across multiple sections:
    - Section A (Maths): Strict negative marking (+4 / -2)
    - Section B (Physics): Multi-correct with partial credit (+4 / partial=1 / neg=-1)
    - Section C (Chemistry): Numerical tolerance match (+4 / 0)
    Evaluates aggregate score, sectional subtotals, and percentile distribution.
    """
    # 1. Author Paper
    qp_res = client.post("/api/v1/question-papers/", headers=org_admin_auth_headers, json={"name": "Complex Grading Paper"})
    qpid = qp_res.json()["id"]

    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 601, "section": "Maths", "question_type": "MCQ_SINGLE", "key": "A", "positive_marks": 4.0, "negative_marks": 2.0,
        "options": [{"key": "A", "text": "Correct"}],
    })
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 602, "section": "Physics", "question_type": "MCQ_MULTI", "key": "A,B,C", "positive_marks": 4.0, "partial_marks": 1.0, "negative_marks": 1.0,
        "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, {"key": "C", "text": "3"}],
    })
    client.post(f"/api/v1/question-papers/{qpid}/questions/", headers=org_admin_auth_headers, json={
        "id": 603, "section": "Chemistry", "question_type": "NUMERICAL", "key": "100.0", "positive_marks": 4.0, "negative_marks": 0.0,
    })

    # 2. Exam
    ex_res = client.post("/api/v1/examinations/", headers=org_admin_auth_headers, json={"name": "Complex Exam", "question_paper_id": qpid, "duration_minutes": 60})
    eid = ex_res.json()["id"]
    client.post(f"/api/v1/examinations/{eid}/publish/", headers=org_admin_auth_headers)

    # Candidate 1:
    # Q601: Correct (+4.0)
    # Q602: Partial 2 keys A, B (+2.0)
    # Q603: Correct 100.0 (+4.0) -> Total = 10.0
    s1 = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att1 = s1.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 601, "selected_options": ["A"]})
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 602, "selected_options": ["A", "B"]})
    client.post(f"/api/v1/student/attempts/{att1}/responses/", headers=student_auth_headers, json={"question_id": 603, "numerical_value": "100.0"})
    client.post(f"/api/v1/student/attempts/{att1}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Candidate 2:
    # Q601: Wrong (-2.0)
    # Q602: Wrong with invalid option (-1.0)
    # Q603: Correct (+4.0) -> Total = 1.0
    s2 = client.post("/api/v1/student/attempts/start/", headers=student2_auth_headers, json={"exam_id": eid})
    att2 = s2.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 601, "selected_options": ["B"]})
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 602, "selected_options": ["A", "D"]})
    client.post(f"/api/v1/student/attempts/{att2}/responses/", headers=student2_auth_headers, json={"question_id": 603, "numerical_value": "100.0"})
    client.post(f"/api/v1/student/attempts/{att2}/submit/", headers=student2_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    # Evaluate
    eval_res = client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)
    rankings = eval_res.json()["summary"]["rankings"]
    cand1 = next(r for r in rankings if r["attempt_id"] == att1)
    cand2 = next(r for r in rankings if r["attempt_id"] == att2)

    assert cand1["total_score"] == 10.0
    assert cand1["rank"] == 1
    assert cand1["percentile"] == 100.0

    assert cand2["total_score"] == 1.0
    assert cand2["rank"] == 2
    assert cand2["percentile"] == 50.0
