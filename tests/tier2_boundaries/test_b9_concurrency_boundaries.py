"""
Tier 2: Boundary & Corner Cases - Feature 9: Multi-Candidate Concurrency & High Volume.
Tests burst attempt launches, concurrent autosave serialization, cross-org master data leakage prevention, evaluation safety, and unauth hijack.
"""

import pytest
import concurrent.futures


@pytest.mark.tier2
@pytest.mark.e2e
def test_burst_attempt_launches_isolation(client, published_exam_fixture, student_auth_headers):
    """B9.1: Burst of concurrent attempt recovery calls for same candidate returns identical attempt ID."""
    eid = published_exam_fixture["exam_id"]

    def launch():
        return client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(launch) for _ in range(5)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    attempt_ids = {r.json()["attempt_id"] for r in results}
    # All 5 calls must map to the same single attempt session for this student!
    assert len(attempt_ids) == 1


@pytest.mark.tier2
@pytest.mark.e2e
def test_simultaneous_autosaves_same_candidate_serialized(client, published_exam_fixture, student_auth_headers):
    """B9.2: Parallel autosave requests to different questions are serialized cleanly without data corruption."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]

    def save_one(qid, option):
        return client.post(
            f"/api/v1/student/attempts/{att_id}/responses/",
            headers=student_auth_headers,
            json={"question_id": qid, "selected_options": [option]},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f1 = executor.submit(save_one, 101, "C")
        f2 = executor.submit(save_one, 102, "A")
        assert f1.result().status_code == 200
        assert f2.result().status_code == 200

    rec = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    resps = rec.json()["existing_responses"]
    assert str(101) in resps or 101 in resps
    assert str(102) in resps or 102 in resps


@pytest.mark.tier2
@pytest.mark.e2e
def test_multi_tenant_cross_org_batch_leak_prevention(client, org_admin_auth_headers):
    """B9.3: Org admin querying batch list cannot see batches belonging to another organization."""
    # Seed an Org 2 batch
    from tests.mock_server.contract_app import state
    with state.lock:
        state.batches["org2-batch"] = {
            "id": "org2-batch",
            "organization_id": "9c62e224-22fa-53e5-cccc-037f493e6b1d",
            "name": "Zenith Secret Batch",
            "code": "ZSB01",
            "is_active": True,
        }

    # Org 1 Admin calls batches list
    resp = client.get("/api/v1/organizations/batches/", headers=org_admin_auth_headers)
    assert resp.status_code == 200
    batch_names = [b["name"] for b in resp.json()["batches"]]
    assert "Zenith Secret Batch" not in batch_names


@pytest.mark.tier2
@pytest.mark.e2e
def test_concurrent_evaluation_requests_safe(client, published_exam_fixture, student_auth_headers, org_admin_auth_headers):
    """B9.4: Multiple simultaneous evaluation trigger requests resolve deterministically without deadlock."""
    eid = published_exam_fixture["exam_id"]
    s = client.post("/api/v1/student/attempts/start/", headers=student_auth_headers, json={"exam_id": eid})
    att_id = s.json()["attempt_id"]
    client.post(f"/api/v1/student/attempts/{att_id}/submit/", headers=student_auth_headers, json={"submission_reason": "MANUAL_SUBMIT"})

    def evaluate():
        return client.post(f"/api/v1/examinations/{eid}/evaluate/", headers=org_admin_auth_headers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(evaluate) for _ in range(3)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    rankings_lens = [len(r.json()["summary"]["rankings"]) for r in results]
    assert all(length == 1 for length in rankings_lens)


@pytest.mark.tier2
@pytest.mark.e2e
def test_candidate_attempt_token_hijack_prevention(client, published_exam_fixture):
    """B9.5: Unauthorized user (no valid Bearer token) attempting to submit candidate response receives 401."""
    eid = published_exam_fixture["exam_id"]
    resp = client.post(
        "/api/v1/student/attempts/att-any/responses/",
        headers={"Authorization": "Bearer invalid-or-stolen-token"},
        json={"question_id": 101, "selected_options": ["A"]},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"
