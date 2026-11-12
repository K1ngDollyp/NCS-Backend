"""
CareConnect emergency coordination as the frontend drives it:
patient raises an emergency -> the candidate hospital sees it in its inbox ->
decline routes to the next hospital -> accept creates the linked referral.
Requires the seeded demo dataset (python -m app.core.seed --reset).
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
API = "/api/v1"


def login(identifier):
    r = client.post(f"{API}/auth/login", json={"identifier": identifier, "password": "vitalis2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_emergency_request_inbox_decline_then_accept():
    pat = login("folake@example.com")
    me = client.get(f"{API}/patients/me", headers=pat).json()
    em = client.post(f"{API}/emergency/requests", headers=pat, json={
        "patient_id": me["id"], "emergency_type": "Chest pain", "presenting_complaint": "chest pain",
        "patient_latitude": 7.153, "patient_longitude": 3.348,
    })
    assert em.status_code == 200, em.text
    em = em.json()
    assert em["status"] == "awaiting_hospital_confirmation"
    assert len(em["candidate_facilities"]) >= 1
    first = em["current_candidate_facility_id"]

    # Patient sees their own request
    mine = client.get(f"{API}/emergency/requests", headers=pat).json()
    assert any(r["id"] == em["id"] for r in mine)

    # The candidate hospital's staff see it in their inbox, other hospitals don't
    fmc = login("reception@fmc.vitalis.ng")
    inbox = client.get(f"{API}/emergency/requests", headers=fmc).json()
    fmc_facility = next(f for f in client.get(f"{API}/facilities").json() if f["facility_code"] == "FMC-ABK")["id"]
    if first == fmc_facility:
        assert any(r["id"] == em["id"] and r["patient_name"] == "Folake Adewale" for r in inbox)
    else:
        assert not any(r["id"] == em["id"] for r in inbox)

    # Decline moves the request on (or back to matching if no one is left)
    declined = client.post(f"{API}/emergency/requests/{em['id']}/confirmations", headers=fmc,
                           json={"facility_id": first, "accepted": False, "reason_or_notes": "Theatre full"}).json()
    assert declined["current_candidate_facility_id"] != first
    states = {c["facility_id"]: c["confirmation_state"] for c in declined["candidate_facilities"]}
    assert states[first] == "declined"

    nxt = declined["current_candidate_facility_id"]
    if nxt:
        accepted = client.post(f"{API}/emergency/requests/{em['id']}/confirmations", headers=fmc,
                               json={"facility_id": nxt, "accepted": True}).json()
        assert accepted["confirmed_facility_id"] == nxt
        assert accepted["linked_referral_id"]
        assert accepted["transport"] is not None
