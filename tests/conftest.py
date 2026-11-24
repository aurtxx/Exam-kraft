"""
Shared Pytest Fixtures and Client Configuration for EZExam E2E Test Suite.
Supports both in-process contract mock server and live deployment (via BASE_URL).
"""

import os
import pytest
import httpx
from tests.mock_server.contract_app import state, ContractHandler


@pytest.fixture(autouse=True)
def reset_contract_state():
    """Ensure in-memory contract state is clean and fresh before every test."""
    state.reset()
    yield


@pytest.fixture(scope="session")
def base_url():
    """Configurable Base URL for live backend target (e.g., http://localhost:8000)."""
    return os.environ.get("BASE_URL", "").rstrip("/")


@pytest.fixture
def client(base_url):
    """
    HTTP client configured for E2E testing.
    If BASE_URL is set in environment, routes to live server.
    Otherwise, routes in-process to the Contract validation engine via MockTransport.
    """
    if base_url:
        with httpx.Client(base_url=base_url, timeout=30.0) as http_client:
            yield http_client
    else:
        handler = ContractHandler(state)
        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport, base_url="http://testserver", timeout=30.0) as http_client:
            yield http_client


@pytest.fixture
def superadmin_auth_headers(client):
    """Returns authorization headers for Platform SuperAdmin."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "superadmin@ezexam.in", "password": "SuperPassword123!"},
    )
    assert resp.status_code == 200, f"SuperAdmin login failed: {resp.text}"
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def org_admin_auth_headers(client):
    """Returns authorization headers for Organization Admin."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "admin@apex.edu", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200, f"OrgAdmin login failed: {resp.text}"
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def faculty_auth_headers(client):
    """Returns authorization headers for Faculty."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "faculty@apex.edu", "password": "FacultyPassword123!"},
    )
    assert resp.status_code == 200, f"Faculty login failed: {resp.text}"
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def student_auth_headers(client):
    """Returns authorization headers for Candidate Student 1."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "student1@apex.edu", "password": "StudentPassword123!"},
    )
    assert resp.status_code == 200, f"Student login failed: {resp.text}"
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def student2_auth_headers(client):
    """Returns authorization headers for Candidate Student 2."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "student2@apex.edu", "password": "StudentPassword123!"},
    )
    assert resp.status_code == 200, f"Student 2 login failed: {resp.text}"
    token = resp.json()["access"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def published_exam_fixture(client, org_admin_auth_headers):
    """
    Creates and publishes an examination containing:
    - Section Maths: 1 Single MCQ (key=C, +3/-1)
    - Section Physics: 1 Multi MCQ (key=A,C, +4/partial=1/-1)
    - Section Chemistry: 1 Numerical (key=4, +4/0)
    Assigns candidates and returns the exam metadata.
    """
    # 1. Create Paper
    qp_resp = client.post(
        "/api/v1/question-papers/",
        headers=org_admin_auth_headers,
        json={"name": "Fixtured Grand Test", "duration_minutes": 60},
    )
    assert qp_resp.status_code == 201
    qpid = qp_resp.json()["id"]

    # 2. Add Questions
    q1 = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={
            "id": 101,
            "section": "Maths",
            "question_type": "MCQ_SINGLE",
            "key": "C",
            "positive_marks": 3.0,
            "negative_marks": 1.0,
            "content_text": "Solve $\\det(2A)$",
            "options": [{"key": "A", "text": "32"}, {"key": "C", "text": "128"}],
        },
    )
    assert q1.status_code == 201

    q2 = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={
            "id": 102,
            "section": "Physics",
            "question_type": "MCQ_MULTI",
            "key": "A,C",
            "positive_marks": 4.0,
            "negative_marks": 1.0,
            "partial_marks": 1.0,
            "content_text": "Select valid orbital statements",
            "options": [{"key": "A", "text": "Planar"}, {"key": "B", "text": "Linear"}, {"key": "C", "text": "Stable"}],
        },
    )
    assert q2.status_code == 201

    q3 = client.post(
        f"/api/v1/question-papers/{qpid}/questions/",
        headers=org_admin_auth_headers,
        json={
            "id": 103,
            "section": "Chemistry",
            "question_type": "NUMERICAL",
            "key": "4",
            "positive_marks": 4.0,
            "negative_marks": 0.0,
            "content_text": "Number of unpaired electrons in complex",
        },
    )
    assert q3.status_code == 201

    # 3. Create Exam
    ex_resp = client.post(
        "/api/v1/examinations/",
        headers=org_admin_auth_headers,
        json={"name": "Published Mock Exam", "question_paper_id": qpid, "duration_minutes": 60},
    )
    assert ex_resp.status_code == 201
    eid = ex_resp.json()["id"]

    # 4. Assign Candidate
    assign_resp = client.post(
        f"/api/v1/examinations/{eid}/assign-candidates/",
        headers=org_admin_auth_headers,
        json={"student_ids": ["user-student1", "user-student2"]},
    )
    assert assign_resp.status_code == 200

    # 5. Publish
    pub_resp = client.post(
        f"/api/v1/examinations/{eid}/publish/",
        headers=org_admin_auth_headers,
    )
    assert pub_resp.status_code == 200

    return {
        "exam_id": eid,
        "question_paper_id": qpid,
        "duration_minutes": 60,
        "question_ids": [101, 102, 103],
    }
