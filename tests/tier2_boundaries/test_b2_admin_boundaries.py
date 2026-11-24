"""
Tier 2: Boundary & Corner Cases - Feature 2: Admin Master Data & Batches.
Tests zero capacity, duplicate codes, duplicate roll numbers, malformed CSV, and pagination boundaries.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.e2e
def test_zero_or_negative_center_capacity_rejected(client, org_admin_auth_headers):
    """B2.1: Examination center creation with capacity <= 0 is rejected with 400 INVALID_CAPACITY."""
    resp = client.post(
        "/api/v1/organizations/centers/",
        headers=org_admin_auth_headers,
        json={"name": "Zero Seat Center", "code": "ZSC01", "capacity": 0},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_CAPACITY"

    neg_resp = client.post(
        "/api/v1/organizations/centers/",
        headers=org_admin_auth_headers,
        json={"name": "Negative Center", "code": "NCNEG", "capacity": -10},
    )
    assert neg_resp.status_code == 400
    assert neg_resp.json()["code"] == "INVALID_CAPACITY"


@pytest.mark.tier2
@pytest.mark.e2e
def test_duplicate_batch_code_rejected(client, org_admin_auth_headers):
    """B2.2: Re-using an existing batch code within the same organization returns 409 Conflict."""
    payload = {"name": "Batch Alpha", "code": "ALPHA_01"}
    client.post("/api/v1/organizations/batches/", headers=org_admin_auth_headers, json=payload)

    dup_resp = client.post("/api/v1/organizations/batches/", headers=org_admin_auth_headers, json=payload)
    assert dup_resp.status_code == 409
    assert dup_resp.json()["code"] == "DUPLICATE_CODE"


@pytest.mark.tier2
@pytest.mark.e2e
def test_duplicate_student_roll_number_rejected(client, org_admin_auth_headers):
    """B2.3: Registering a student with an already assigned roll number returns 409 DUPLICATE_ROLL."""
    payload = {"roll_number": "2026888", "name": "First Student"}
    r1 = client.post("/api/v1/users/students/", headers=org_admin_auth_headers, json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/users/students/", headers=org_admin_auth_headers, json={"roll_number": "2026888", "name": "Second Student"})
    assert r2.status_code == 409
    assert r2.json()["code"] == "DUPLICATE_ROLL"


@pytest.mark.tier2
@pytest.mark.e2e
def test_empty_or_malformed_csv_bulk_import_rejected(client, org_admin_auth_headers):
    """B2.4: Uploading an empty file or CSV missing mandatory headers returns 400 Bad Request."""
    empty_res = client.post(
        "/api/v1/users/students/bulk-upload/",
        headers={"Authorization": org_admin_auth_headers["Authorization"], "Content-Type": "text/csv"},
        content=b"",
    )
    assert empty_res.status_code == 400

    malformed_csv = "RandomHeader1,RandomHeader2\nValue1,Value2\n"
    bad_res = client.post(
        "/api/v1/users/students/bulk-upload/",
        headers={"Authorization": org_admin_auth_headers["Authorization"], "Content-Type": "text/csv"},
        content=malformed_csv.encode("utf-8"),
    )
    assert bad_res.status_code == 400
    assert bad_res.json()["code"] == "MALFORMED_HEADER"


@pytest.mark.tier2
@pytest.mark.e2e
def test_large_roster_pagination_boundary(client, org_admin_auth_headers):
    """B2.5: Pagination boundaries: page_size <= 0 rejected; querying beyond total count returns empty array."""
    # page_size <= 0
    inv_res = client.get(
        "/api/v1/users/students/?page=1&page_size=0",
        headers=org_admin_auth_headers,
    )
    assert inv_res.status_code == 400
    assert inv_res.json()["code"] == "INVALID_PAGE_SIZE"

    # Query far page (e.g. page 999)
    far_res = client.get(
        "/api/v1/users/students/?page=999&page_size=20",
        headers=org_admin_auth_headers,
    )
    assert far_res.status_code == 200
    assert far_res.json()["students"] == []
