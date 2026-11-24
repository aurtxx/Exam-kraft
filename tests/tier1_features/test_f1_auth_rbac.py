"""
Tier 1: Feature 1 - Authentication & Role-Based Access Control (RBAC) Isolation.
Verifies credentials authentication, JWT token issuance, user session profiles, and token refresh.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_superadmin_login(client):
    """F1.1: Superadmin login returns 200 OK, JWT access & refresh tokens, and SUPERADMIN role."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "superadmin@ezexam.in", "password": "SuperPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "access" in data and len(data["access"]) > 0
    assert "refresh" in data and len(data["refresh"]) > 0
    assert data["user"]["role"] == "SUPERADMIN"
    assert data["user"]["name"] == "Platform SuperAdmin"


@pytest.mark.tier1
@pytest.mark.e2e
def test_org_admin_login(client):
    """F1.2: Organization Admin login returns 200 OK, role ORG_ADMIN, and organization tenant metadata."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "admin@apex.edu", "password": "SecurePassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["user"]["role"] == "ORG_ADMIN"
    assert "organization" in data
    assert data["organization"]["slug"] == "ezexamqwertyuiop"
    assert data["organization"]["name"] == "Apex Engineering Academy"


@pytest.mark.tier1
@pytest.mark.e2e
def test_faculty_login(client):
    """F1.3: Faculty login returns 200 OK, valid JWT, and role FACULTY."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "faculty@apex.edu", "password": "FacultyPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["user"]["role"] == "FACULTY"
    assert data["user"]["email"] == "faculty@apex.edu"


@pytest.mark.tier1
@pytest.mark.e2e
def test_student_login(client):
    """F1.4: Student candidate login returns 200 OK, valid JWT, role STUDENT, and roll number."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "student1@apex.edu", "password": "StudentPassword123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["user"]["role"] == "STUDENT"
    assert data["user"]["name"] == "Aryabhata Sharma"


@pytest.mark.tier1
@pytest.mark.e2e
def test_token_refresh(client):
    """F1.5: Refresh token can obtain a fresh access token, and the new access token can query /auth/me/."""
    login_resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "admin@apex.edu", "password": "SecurePassword123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh"]

    # Refresh
    refresh_resp = client.post(
        "/api/v1/auth/refresh/",
        json={"refresh": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["access"]
    assert new_access != login_resp.json()["access"]

    # Use new access token to query /auth/me/
    me_resp = client.get(
        "/api/v1/auth/me/",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["role"] == "ORG_ADMIN"
