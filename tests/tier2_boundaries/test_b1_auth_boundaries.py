"""
Tier 2: Boundary & Corner Cases - Feature 1: Auth & RBAC Isolation.
Tests expired tokens, invalid credentials, missing payloads, RBAC violations, and malformed OTP inputs.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_expired_or_invalid_jwt_token_rejected(client):
    """B1.1: Requests with forged or expired JWT token return 401 Unauthorized."""
    resp = client.get(
        "/api/v1/auth/me/",
        headers={"Authorization": "Bearer forged-garbage-token-xyz"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


@pytest.mark.tier2
@pytest.mark.e2e
def test_invalid_credentials_returns_401(client):
    """B1.2: Providing an incorrect password returns 401 INVALID_CREDENTIALS."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "admin@apex.edu", "password": "WrongPassword!999"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.tier2
@pytest.mark.e2e
def test_missing_credentials_returns_400(client):
    """B1.3: Empty username or missing password returns 400 Bad Request."""
    resp = client.post(
        "/api/v1/auth/login/",
        json={"username": "", "password": ""},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "MISSING_CREDENTIALS"


@pytest.mark.tier2
@pytest.mark.e2e
def test_student_role_forbidden_from_admin_endpoints(client, student_auth_headers):
    """B1.4: Student candidate credentials attempting to access administrative batch creation return 403 Forbidden."""
    resp = client.post(
        "/api/v1/organizations/batches/",
        headers=student_auth_headers,
        json={"name": "Hacked Batch", "code": "HACK1"},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN"


@pytest.mark.tier2
@pytest.mark.e2e
def test_invalid_phone_otp_request(client):
    """B1.5: Sending a malformed phone number (<10 digits) returns 400 INVALID_PHONE."""
    resp = client.post(
        "/api/v1/auth/otp/send/",
        json={"phone": "123"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_PHONE"
