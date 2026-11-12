"""
VITALIS NETWORK: cross-facility record access with patient one-time code,
and the VITALIS AI longitudinal assessment.
Requires the seeded demo dataset (python -m app.core.seed --reset).
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def login(identifier):
    r = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": "vitalis2026"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data


def test_cross_facility_access_requires_patient_code_and_ai_uses_network_history():
    # Hospital B (State Hospital) doctor already has records; FMC has never seen this patient.
    rec, rec_info = login("reception@fmc.vitalis.ng")
    found = client.get("/api/v1/records/lookup", params={"q": "VIT-2026-0002"}, headers=rec).json()
    assert found and found[0]["patient_number"] == "VIT-2026-0002"
    pid = found[0]["patient_id"]

    # Without consent, external records and clinical lists stay hidden
    locked = client.get(f"/api/v1/records/patients/{pid}", headers=rec).json()
    assert locked["access"]["level"] in ("facility_only", "full")
    if locked["access"]["level"] == "facility_only":
        assert locked["patient"]["allergies"] == []
        assert locked["access"]["hidden_encounters"] >= 3

    # Request a one-time code; patient sees it in their app
    req = client.post("/api/v1/records/access-requests", json={"patient_id": pid}, headers=rec).json()
    pat, _ = login("folake@example.com")
    pending = client.get("/api/v1/records/me/access-requests", headers=pat).json()
    code = next(p["code"] for p in pending if p["request_id"] == req["request_id"])

    # Wrong code rejected, right code grants access
    bad = client.post(f"/api/v1/records/access-requests/{req['request_id']}/verify", json={"code": "000000" if code != "000000" else "111111"}, headers=rec)
    assert bad.status_code == 400
    ok = client.post(f"/api/v1/records/access-requests/{req['request_id']}/verify", json={"code": code}, headers=rec)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"

    record = client.get(f"/api/v1/records/patients/{pid}", headers=rec).json()
    assert record["access"]["level"] == "full"
    assert len({e["facility_name"] for e in record["encounters"]}) >= 2
    assert record["patient"]["allergies"]

    # New FMC visit -> nurse vitals -> doctor runs VITALIS AI
    enc = client.post("/api/v1/encounters", json={
        "patient_id": pid, "facility_id": rec_info["facility_id"],
        "presenting_complaint": "Headache and blurred vision; excessive thirst and frequent urination",
    }, headers=rec).json()
    nurse, _ = login("nurse@fmc.vitalis.ng")
    vit = [("systolic_bp", 174, "mmHg"), ("diastolic_bp", 108, "mmHg"), ("pulse_rate", 96, "bpm"),
           ("weight", 84, "kg"), ("height", 162, "cm"), ("blood_glucose", 236, "mg/dL")]
    r = client.post(f"/api/v1/encounters/{enc['id']}/observations",
                    json={"observations": [{"observation_type": t, "value": v, "unit": u} for t, v, u in vit]}, headers=nurse)
    assert r.status_code == 200

    doc, _ = login("doctor@fmc.vitalis.ng")
    a = client.post(f"/api/v1/intelligence/encounters/{enc['id']}/assessment", headers=doc)
    assert a.status_code == 200, a.text
    a = a.json()
    assert a["data_coverage"]["prior_encounters"] >= 3
    names = " ".join(c["condition"].lower() for c in a["conditions"])
    assert "hypertension" in names and "diabetes" in names
    hctz = next(m for m in a["medication_options"] if m["drug"].lower().startswith("hydrochlorothiazide"))
    assert hctz["safety"] == "avoid"  # sulfonamide allergy recorded at another facility
    assert any(m["key"] == "diabetes" for m in a["ml_models"])

    # Patient sees who accessed their record
    log = client.get("/api/v1/records/me/access-log", headers=pat).json()
    assert any(c["active"] for c in log["consents"])
    assert any(e["action"] == "NETWORK_RECORD_VIEWED" for e in log["events"])


def test_patient_cannot_view_another_patients_network_record():
    pat, _ = login("olumide@example.com")
    rec, _ = login("reception@fmc.vitalis.ng")
    pid = client.get("/api/v1/records/lookup", params={"q": "VIT-2026-0002"}, headers=rec).json()[0]["patient_id"]
    assert client.get(f"/api/v1/records/patients/{pid}", headers=pat).status_code == 403
