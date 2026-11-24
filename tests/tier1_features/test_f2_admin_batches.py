"""
Tier 1: Feature 2 - Admin Master Data & Batches.
Verifies academic batch CRUD, examination center capacity, faculty roster, student creation, and bulk CSV import.
"""

import pytest


@pytest.mark.tier1
@pytest.mark.e2e
def test_batch_crud(client, org_admin_auth_headers):
    """F2.1: Org admin creates an academic batch and verifies it appears in organization batch listing."""
    payload = {
        "name": "Class 12 Physics Elite",
        "code": "C12PE",
        "stream": "JEE_ADVANCED",
        "description": "2026 JEE Advanced Target Batch",
    }
    create_resp = client.post(
        "/api/v1/organizations/batches/",
        headers=org_admin_auth_headers,
        json=payload,
    )
    assert create_resp.status_code == 201
    batch_id = create_resp.json()["id"]

    list_resp = client.get(
        "/api/v1/organizations/batches/",
        headers=org_admin_auth_headers,
    )
    assert list_resp.status_code == 200
    batches = list_resp.json()["batches"]
    created_batch = next((b for b in batches if b["id"] == batch_id), None)
    assert created_batch is not None
    assert created_batch["name"] == "Class 12 Physics Elite"
    assert created_batch["code"] == "C12PE"


@pytest.mark.tier1
@pytest.mark.e2e
def test_center_capacity_creation(client, org_admin_auth_headers):
    """F2.2: Org admin creates an examination center with seat capacity and verifies record."""
    payload = {
        "name": "City Center Lab 3",
        "code": "CCL03",
        "capacity": 150,
        "is_active": True,
    }
    resp = client.post(
        "/api/v1/organizations/centers/",
        headers=org_admin_auth_headers,
        json=payload,
    )
    assert resp.status_code == 201
    center_id = resp.json()["id"]

    list_resp = client.get(
        "/api/v1/organizations/centers/",
        headers=org_admin_auth_headers,
    )
    assert list_resp.status_code == 200
    centers = list_resp.json()["centers"]
    match = next((c for c in centers if c["id"] == center_id), None)
    assert match is not None
    assert match["capacity"] == 150
    assert match["code"] == "CCL03"


@pytest.mark.tier1
@pytest.mark.e2e
def test_faculty_roster_assignment(client, org_admin_auth_headers):
    """F2.3: Org admin provisions a new faculty member with subject and center assignments."""
    payload = {
        "name": "Dr. Marie Curie",
        "email": "curie@apex.edu",
        "subject_ids": ["Radioactivity", "Inorganic Chemistry"],
        "is_active": True,
    }
    create_resp = client.post(
        "/api/v1/users/faculty/",
        headers=org_admin_auth_headers,
        json=payload,
    )
    assert create_resp.status_code == 201
    fac_id = create_resp.json()["id"]

    list_resp = client.get(
        "/api/v1/users/faculty/",
        headers=org_admin_auth_headers,
    )
    assert list_resp.status_code == 200
    faculties = list_resp.json()["faculties"]
    match = next((f for f in faculties if f["id"] == fac_id), None)
    assert match is not None
    assert match["name"] == "Dr. Marie Curie"
    assert "Radioactivity" in match["subjects"]


@pytest.mark.tier1
@pytest.mark.e2e
def test_student_creation(client, org_admin_auth_headers):
    """F2.4: Org admin creates a single candidate student record with unique roll number."""
    payload = {
        "roll_number": "2026101",
        "name": "Srinivasa Ramanujan",
        "email": "ramanujan@student.org",
        "batch_id": "11111111-1111-1111-1111-111111111111",
        "centre_id": "55555555-5555-5555-5555-555555555555",
    }
    resp = client.post(
        "/api/v1/users/students/",
        headers=org_admin_auth_headers,
        json=payload,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["student"]["roll_number"] == "2026101"
    assert data["student"]["name"] == "Srinivasa Ramanujan"


@pytest.mark.tier1
@pytest.mark.e2e
def test_bulk_student_csv_import(client, org_admin_auth_headers):
    """F2.5: Bulk student roster ingestion via CSV upload with header validation."""
    csv_content = (
        "RollNumber,Name,Phone,Email,BatchCode,CentreCode\n"
        "2026501,Ada Lovelace,+919999900001,ada@lovelace.org,C12B,NC01\n"
        "2026502,Charles Babbage,+919999900002,charles@babbage.org,C12B,NC01\n"
        "2026503,Claude Shannon,+919999900003,claude@shannon.org,C12B,NC01\n"
    )
    resp = client.post(
        "/api/v1/users/students/bulk-upload/",
        headers={"Authorization": org_admin_auth_headers["Authorization"], "Content-Type": "text/csv"},
        content=csv_content.encode("utf-8"),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["total_processed"] == 3
    assert data["created_count"] == 3
    assert len(data["errors"]) == 0
