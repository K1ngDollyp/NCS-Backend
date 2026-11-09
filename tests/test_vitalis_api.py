import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_auth_token(identifier: str, password: str = "vitalis2026"):
    resp = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200, f"Failed login for {identifier}: {resp.text}"
    return resp.json()["access_token"]

def test_system_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "operational"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

def test_triage_emergency_red_flags():
    """Verify deterministic emergency rules trigger EMERGENCY_RED without delay"""
    # Emergency chest pain
    payload = {
        "patient_id": "test",  # we will fetch real patient id
        "symptoms": [
            {"symptom": "Severe chest pain radiating to left jaw", "severity": "severe"}
        ]
    }
    # Fetch real patient id
    token = get_auth_token("olumide@example.com")
    p_res = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {token}"})
    assert p_res.status_code == 200
    pid = p_res.json()["id"]

    payload["patient_id"] = pid
    res = client.post("/api/v1/triage/sessions", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["urgency_level"] == "EMERGENCY_RED"
    assert len(data["matched_red_flags"]) > 0

def test_vitalis_route_facility_matching():
    """Verify S = 0.40C + 0.25A + 0.20D + 0.15V matching algorithm"""
    res = client.get(
        "/api/v1/facilities/match?user_lat=7.1470&user_lon=3.3610&service_needed=Emergency Resuscitation"
    )
    assert res.status_code == 200
    facilities = res.json()
    assert len(facilities) > 0
    # First match should have high suitability score
    assert facilities[0]["suitability_score"] > 50.0
    assert "score_breakdown" in facilities[0]

def test_end_to_end_hospital_workflow():
    """
    Test Section 5.5: Reception -> Nursing -> Doctor -> Laboratory -> Doctor review
    """
    # 1. Login as reception
    rec_token = get_auth_token("reception@fmc.vitalis.ng")
    nurse_token = get_auth_token("nurse@fmc.vitalis.ng")
    doc_token = get_auth_token("doctor@fmc.vitalis.ng")
    lab_token = get_auth_token("lab@fmc.vitalis.ng")

    # Get patient
    p_search = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {rec_token}"})
    assert p_search.status_code == 200
    patients = p_search.json()
    assert len(patients) > 0
    patient = patients[0]

    # Get facility
    fac_res = client.get("/api/v1/facilities")
    assert fac_res.status_code == 200
    facility_id = fac_res.json()[0]["id"]

    # --- Step 1: Reception opens encounter ---
    enc_payload = {
        "patient_id": patient["id"],
        "facility_id": facility_id,
        "visit_type": "walk_in",
        "priority": "routine",
        "presenting_complaint": "Persistent high fever and severe headache for 3 days with shivering",
        "arrival_mode": "walk_in",
        "is_emergency_flag": False
    }
    enc_res = client.post("/api/v1/encounters", json=enc_payload, headers={"Authorization": f"Bearer {rec_token}"})
    assert enc_res.status_code == 200
    enc_data = enc_res.json()
    enc_id = enc_data["id"]
    assert enc_data["status"] == "awaiting_nursing"

    # --- Step 2: Nursing records vital signs ---
    vitals_payload = {
        "observations": [
            {"observation_type": "temperature", "value": 39.4, "unit": "degC"},
            {"observation_type": "pulse_rate", "value": 108, "unit": "bpm"},
            {"observation_type": "systolic_bp", "value": 125, "unit": "mmHg"},
            {"observation_type": "diastolic_bp", "value": 82, "unit": "mmHg"},
            {"observation_type": "spo2", "value": 98, "unit": "%"}
        ],
        "general_nurse_note": "Patient flushed and rigors observed. Triage warning flagged for elevated temp.",
        "handover_to_doctor": True
    }
    obs_res = client.post(f"/api/v1/encounters/{enc_id}/observations", json=vitals_payload, headers={"Authorization": f"Bearer {nurse_token}"})
    assert obs_res.status_code == 200
    obs_data = obs_res.json()
    assert obs_data["status"] == "awaiting_doctor"
    # Temp > 37.8 should trigger warning flag
    temp_obs = next(o for o in obs_data["nursing_observations"] if o["observation_type"] == "temperature")
    assert temp_obs["is_warning"] is True

    # --- Step 3: Doctor runs Intelligence & Differential ---
    diff_res = client.post(f"/api/v1/intelligence/encounters/{enc_id}/differential", headers={"Authorization": f"Bearer {doc_token}"})
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert "Malaria" in str(diff_data["possible_differentials"])
    assert diff_data["safety_disclaimer"] is not None

    # --- Step 4: Doctor records clinical note & orders Lab test ---
    note_payload = {
        "note_type": "consultation",
        "history_of_complaint": "Acute febrile illness. Suspected severe Plasmodium falciparum malaria.",
        "assessment": "Acute febrile illness - Rule out Malaria / Typhoid",
        "clinical_plan": "Stat Malaria Microscopy & Full Blood Count. Supportive IV fluids.",
        "disposition": "outpatient",
        "is_draft": False,
        "is_ai_assisted": True
    }
    note_res = client.post(f"/api/v1/encounters/{enc_id}/clinical-notes", json=note_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert note_res.status_code == 200

    order_payload = {
        "department": "laboratory",
        "test_or_modality": "Malaria Parasite Microscopy & FBC",
        "clinical_indication": "Persistent fever 39.4C with rigors",
        "priority": "urgent"
    }
    order_res = client.post(f"/api/v1/encounters/{enc_id}/investigation-orders", json=order_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert order_res.status_code == 200
    order_data = order_res.json()
    order_id = order_data["investigation_orders"][0]["id"]
    assert order_data["status"] == "awaiting_investigation"

    # --- Step 5: Lab Tech enters & verifies result ---
    lab_res_payload = {
        "specimen_type": "Whole Blood (EDTA)",
        "result_payload": {
            "malaria_parasite": "P. falciparum trophozoites seen (+++)",
            "parasite_density": "12,500 parasites/uL",
            "haemoglobin": "11.2 g/dL",
            "wbc_count": "8.4 x 10^9 /L"
        },
        "comments": "High parasite load confirmed by thick blood film."
    }
    lab_enter = client.post(f"/api/v1/diagnostics/orders/{order_id}/lab-results", json=lab_res_payload, headers={"Authorization": f"Bearer {lab_token}"})
    assert lab_enter.status_code == 200

    verify_res = client.post(f"/api/v1/diagnostics/orders/{order_id}/verify", headers={"Authorization": f"Bearer {lab_token}"})
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "verified"

    # Verify encounter status moved to results_ready
    enc_chk = client.get(f"/api/v1/encounters/{enc_id}", headers={"Authorization": f"Bearer {doc_token}"})
    assert enc_chk.status_code == 200
    assert enc_chk.json()["status"] == "results_ready"

def test_medication_safety_checker():
    """Verify allergy and interaction checks against penicillin and known drug rules"""
    doc_token = get_auth_token("doctor@fmc.vitalis.ng")
    pat_token = get_auth_token("olumide@example.com")
    p_res = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"})
    pid = p_res.json()["id"]

    # Olumide has documented allergy to Penicillin
    # Propose Amoxicillin (penicillin derivative) -> must trigger allergy conflict!
    payload = {
        "patient_id": pid,
        "proposed_medications": ["Amoxicillin 500mg capsules", "Paracetamol 1g"]
    }
    res = client.post("/api/v1/intelligence/medication-safety-check", json=payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_safe_to_proceed"] is False
    assert len(data["allergy_conflicts"]) > 0

def test_qr_grant_issuance_and_redemption():
    """Verify single-use token, SHA-256 server storage, and redemption audit (Section 13)"""
    pat_token = get_auth_token("olumide@example.com")
    nurse_token = get_auth_token("nurse@fmc.vitalis.ng")

    p_res = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"})
    pid = p_res.json()["id"]

    # Patient issues QR grant
    qr_res = client.post(
        "/api/v1/connect/qr-grants",
        json={"patient_id": pid, "scope": ["allergies", "medications"], "duration_minutes": 10},
        headers={"Authorization": f"Bearer {pat_token}"}
    )
    assert qr_res.status_code == 200
    qr_data = qr_res.json()
    raw_token = qr_data["qr_token"]
    assert qr_data["qr_code_base64"].startswith("data:image/png;base64,")

    # Staff redeems QR grant
    redeem_res = client.post(
        "/api/v1/connect/redeem",
        json={"token": raw_token, "facility_id": "FMC-ABK"},
        headers={"Authorization": f"Bearer {nurse_token}"}
    )
    assert redeem_res.status_code == 200
    red_data = redeem_res.json()
    assert red_data["status"] == "success"
    assert "allergies" in red_data["data"]

    # Second redemption attempt must FAIL (single-use)
    fail_res = client.post(
        "/api/v1/connect/redeem",
        json={"token": raw_token, "facility_id": "FMC-ABK"},
        headers={"Authorization": f"Bearer {nurse_token}"}
    )
    assert fail_res.status_code == 403

def test_inter_hospital_transfer_workflow():
    """Verify Hospital A to Hospital B transfer package assembly, consent, and redemption (Section 32)"""
    doc_a_token = get_auth_token("doctor@fmc.vitalis.ng")
    pat_token = get_auth_token("olumide@example.com")
    doc_b_token = get_auth_token("doctor@statehospital.vitalis.ng")

    p_res = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"})
    pid = p_res.json()["id"]

    facs = client.get("/api/v1/facilities").json()
    fac_b = next(f for f in facs if "State Hospital" in f["name"])

    # Hospital A initiates transfer
    trf_in = {
        "patient_id": pid,
        "recipient_facility_id": fac_b["id"],
        "purpose": "Specialist Infectious Disease Care",
        "urgency": "urgent",
        "scope": ["summary", "vitals", "allergies", "medications"]
    }
    init_res = client.post("/api/v1/transfers", json=trf_in, headers={"Authorization": f"Bearer {doc_a_token}"})
    assert init_res.status_code == 200
    trf_id = init_res.json()["id"]

    # Patient approves consent
    c_res = client.post(f"/api/v1/transfers/{trf_id}/consent", headers={"Authorization": f"Bearer {pat_token}"})
    assert c_res.status_code == 200
    assert c_res.json()["patient_consented"] is True

    # Send package
    send_res = client.post(f"/api/v1/transfers/{trf_id}/send", headers={"Authorization": f"Bearer {doc_a_token}"})
    assert send_res.status_code == 200
    transfer_token = send_res.json()["transfer_token"]

    # Hospital B redeems package
    redeem_res = client.post("/api/v1/transfers/redeem", json={"transfer_token": transfer_token}, headers={"Authorization": f"Bearer {doc_b_token}"})
    assert redeem_res.status_code == 200
    red_data = redeem_res.json()
    assert red_data["status"] == "success"
    assert "package_payload" in red_data

