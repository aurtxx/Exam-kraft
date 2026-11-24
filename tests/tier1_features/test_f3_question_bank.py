"""
Tier 1: Feature 3 - Question Bank & Section Categorization.
Verifies MCQ Single, MCQ Multi, Numerical question authoring, LaTeX formula preservation, and section partitioning.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_mcq_single_authoring(client, org_admin_auth_headers):
    """F3.1: Author a single-choice MCQ with options, answer key, and marking scheme."""
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Physics Unit Test", "exam_type": "JEE-Main"},
    )
    assert qp_resp.status_code == 201
    qpid = qp_resp.json()["id"]

    q_payload = {
        "question_type": "MCQ_SINGLE",
        "section": "Physics",
        "key": "B",
        "positive_marks": 4.0,
        "negative_marks": 1.0,
        "content_text": "What is the SI unit of magnetic flux?",
        "options": [
            {"key": "A", "text": "Tesla"},
            {"key": "B", "text": "Weber"},
            {"key": "C", "text": "Henry"},
            {"key": "D", "text": "Gauss"},
        ],
        "explanation": "Magnetic flux is measured in Weber ($Wb$)."
    }
    q_resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json=q_payload,
    )
    assert q_resp.status_code == 201
    qid = q_resp.json()["id"]

    # Verify via paper questions payload
    get_resp = client.get(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
    )
    assert get_resp.status_code == 200
    questions = get_resp.json()["questions"]
    match = next((q for q in questions if q["id"] == qid), None)
    assert match is not None
    assert match["key"] == "B"
    assert match["question_type"] == "MCQ_SINGLE"
    assert len(match["options"]) == 4


@pytest.mark.tier1
@pytest.mark.e2e
def test_mcq_multi_authoring(client, org_admin_auth_headers):
    """F3.2: Author a multi-correct MCQ supporting multiple keys and partial credit."""
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Advanced Physics Paper"},
    )
    qpid = qp_resp.json()["id"]

    q_payload = {
        "question_type": "MCQ_MULTI",
        "section": "Physics",
        "key": "A,C,D",
        "positive_marks": 4.0,
        "negative_marks": 1.0,
        "partial_marks": 1.0,
        "content_text": "Which of the following are Maxwell's thermodynamic relations?",
        "options": [
            {"key": "A", "text": "(\\partial T / \\partial V)_S = -(\\partial P / \\partial S)_V"},
            {"key": "B", "text": "Invalid relation"},
            {"key": "C", "text": "(\\partial T / \\partial P)_S = (\\partial V / \\partial S)_P"},
            {"key": "D", "text": "(\\partial P / \\partial T)_V = (\\partial S / \\partial V)_T"},
        ],
    }
    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json=q_payload,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"


@pytest.mark.tier1
@pytest.mark.e2e
def test_numerical_authoring(client, org_admin_auth_headers):
    """F3.3: Author a numerical input question with float/integer key and zero negative marks."""
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Physical Chemistry Paper"},
    )
    qpid = qp_resp.json()["id"]

    q_payload = {
        "question_type": "NUMERICAL",
        "section": "Chemistry",
        "key": "24.5",
        "positive_marks": 4.0,
        "negative_marks": 0.0,
        "content_text": "Calculate the molar volume of an ideal gas at $298K$ and $1 atm$ in liters.",
        "explanation": "From ideal gas law, $V = nRT/P = 24.5 L$."
    }
    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json=q_payload,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "SUCCESS"


@pytest.mark.tier1
@pytest.mark.e2e
def test_latex_markup_parsing(client, org_admin_auth_headers):
    """F3.4: Author a question containing LaTeX syntax and ensure special escape characters are preserved."""
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Calculus Exam"},
    )
    qpid = qp_resp.json()["id"]

    complex_latex = r"Compute $\lim_{x \to 0} \frac{\int_0^x \sin(t^2) dt}{x^3}$."
    q_payload = {
        "question_type": "NUMERICAL",
        "section": "Mathematics",
        "key": "0.33",
        "positive_marks": 4.0,
        "negative_marks": 0.0,
        "content_text": complex_latex,
    }
    resp = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json=q_payload,
    )
    assert resp.status_code == 201
    qid = resp.json()["id"]

    fetch_resp = client.get(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
    )
    questions = fetch_resp.json()["questions"]
    q = next(item for item in questions if item["id"] == qid)
    assert complex_latex in q["content_text"]


@pytest.mark.tier1
@pytest.mark.e2e
def test_section_categorization(client, org_admin_auth_headers):
    """F3.5: Populate questions across multiple distinct sections and verify section separation."""
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Multi-Section JEE Grand Mock"},
    )
    qpid = qp_resp.json()["id"]

    sections = ["Mathematics", "Physics", "Chemistry"]
    for sname in sections:
        q_payload = {
            "question_type": "MCQ_SINGLE",
            "section": sname,
            "key": "A",
            "positive_marks": 4.0,
            "negative_marks": 1.0,
            "content_text": f"Question for {sname}",
            "options": [{"key": "A", "text": "Correct"}],
        }
        res = client.post(
            f"/api/v1/question-papers/{qpid}/questions/",
            headers=org_admin_auth_headers,
            json=q_payload,
        )
        assert res.status_code == 201

    fetch_resp = client.get(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
    )
    questions = fetch_resp.json()["questions"]
    recorded_sections = {q["section"] for q in questions}
    assert recorded_sections == set(sections)
