import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import OrderDepartment, OrderStatus, EncounterPriority, VisitType

client = TestClient(app)

def get_token(identifier: str, password: str = "vitalis2026") -> str:
    res = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, f"Login failed for {identifier}: {res.text}"
    return res.json()["access_token"]

# 1. System Endpoints
def test_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "operational"

    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "healthy"

# 2. Auth Endpoints
def test_auth_registration_and_login():
    import random
    unique_email = f"tester_{random.randint(10000, 99999)}@example.com"
    reg_res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "strongPassword123!",
        "full_name": "Test User",
        "role": "patient"
    })
    assert reg_res.status_code == 200
    user_data = reg_res.json()
    assert user_data["email"] == unique_email

    # Login with new account
    login_res = client.post("/api/v1/auth/login", json={
        "identifier": unique_email,
        "password": "strongPassword123!"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

# 3. Patient & Family History Endpoints
def test_patient_crud_and_family_history():
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pat_token = get_token("olumide@example.com")

    # GET /patients/me
    res_me = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"})
    assert res_me.status_code == 200
    pat = res_me.json()
    pid = pat["id"]

    # GET /patients/search
    res_search = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {doc_token}"})
    assert res_search.status_code == 200
    assert len(res_search.json()) > 0

    # GET /patients/{id}
    res_get = client.get(f"/api/v1/patients/{pid}", headers={"Authorization": f"Bearer {doc_token}"})
    assert res_get.status_code == 200
    assert res_get.json()["id"] == pid

    # POST /patients/{patient_id}/family-history
    fh_res = client.post(f"/api/v1/patients/{pid}/family-history", json={
        "relationship_type": "maternal_aunt",
        "condition": "Sickle Cell Trait",
        "is_deceased": False,
        "notes": "Diagnosed in early adulthood"
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert fh_res.status_code == 200
    assert fh_res.json()["condition"] == "Sickle Cell Trait"

# 4. Triage Endpoints
def test_triage_sessions():
    pat_token = get_token("olumide@example.com")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]

    # Routine triage
    triage_res = client.post("/api/v1/triage/sessions", json={
        "patient_id": pid,
        "symptoms": [{"symptom": "Mild runny nose and sneeze", "severity": "mild"}]
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert triage_res.status_code == 200
    assert triage_res.json()["urgency_level"] == "ROUTINE_GREEN"

    # GET /triage/patient/{patient_id}
    history = client.get(f"/api/v1/triage/patient/{pid}", headers={"Authorization": f"Bearer {pat_token}"})
    assert history.status_code == 200
    assert len(history.json()) > 0

# 5. Facilities Endpoints
def test_facilities_endpoints():
    res_all = client.get("/api/v1/facilities")
    assert res_all.status_code == 200
    facs = res_all.json()
    assert len(facs) > 0

    # Match endpoint
    res_match = client.get("/api/v1/facilities/match?user_lat=7.1475&user_lon=3.3619&service_needed=Cardiology")
    assert res_match.status_code == 200
    matches = res_match.json()
    assert len(matches) > 0
    assert matches[0]["suitability_score"] > 0

# 6. Centralized Hospital Workflow: Encounters, Observations, Notes, Orders
def test_complete_encounter_workflow_and_queues():
    rec_token = get_token("reception@fmc.vitalis.ng")
    nurse_token = get_token("nurse@fmc.vitalis.ng")
    doc_token = get_token("doctor@fmc.vitalis.ng")
    lab_token = get_token("lab@fmc.vitalis.ng")

    pat = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {rec_token}"}).json()[0]
    fac_id = client.get("/api/v1/facilities").json()[0]["id"]

    # 1. POST /encounters (Reception)
    enc = client.post("/api/v1/encounters", json={
        "patient_id": pat["id"],
        "facility_id": fac_id,
        "visit_type": "walk_in",
        "priority": "routine",
        "presenting_complaint": "Persistent dry cough and mild fever",
        "arrival_mode": "walk_in"
    }, headers={"Authorization": f"Bearer {rec_token}"}).json()
    enc_id = enc["id"]
    assert enc["status"] == "awaiting_nursing"

    # GET /encounters/{id}
    chk = client.get(f"/api/v1/encounters/{enc_id}", headers={"Authorization": f"Bearer {rec_token}"})
    assert chk.status_code == 200

    # GET /encounters/queue/nursing
    n_queue = client.get("/api/v1/encounters/queue/nursing", headers={"Authorization": f"Bearer {nurse_token}"})
    assert n_queue.status_code == 200
    assert any(e["id"] == enc_id for e in n_queue.json())

    # 2. POST /encounters/{id}/observations (Nursing)
    obs_res = client.post(f"/api/v1/encounters/{enc_id}/observations", json={
        "observations": [
            {"observation_type": "systolic_bp", "value": 120.0, "unit": "mmHg"},
            {"observation_type": "diastolic_bp", "value": 80.0, "unit": "mmHg"},
            {"observation_type": "pulse_rate", "value": 72.0, "unit": "bpm"},
            {"observation_type": "temperature", "value": 37.0, "unit": "degC"}
        ],
        "handover_to_doctor": True
    }, headers={"Authorization": f"Bearer {nurse_token}"})
    assert obs_res.status_code == 200
    assert obs_res.json()["status"] == "awaiting_doctor"

    # GET /encounters/queue/doctor
    d_queue = client.get("/api/v1/encounters/queue/doctor", headers={"Authorization": f"Bearer {doc_token}"})
    assert d_queue.status_code == 200
    assert any(e["id"] == enc_id for e in d_queue.json())

    # 3. POST /encounters/{id}/clinical-notes (Doctor)
    note_res = client.post(f"/api/v1/encounters/{enc_id}/clinical-notes", json={
        "note_type": "consultation",
        "history_of_complaint": "Dry cough for 4 days, mild fatigue",
        "assessment": "Upper respiratory tract infection",
        "clinical_plan": "Supportive therapy, check chest X-ray if persistent",
        "disposition": "outpatient"
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert note_res.status_code == 200

    # 4. POST /encounters/{id}/investigation-orders (Doctor orders Lab test)
    order_res = client.post(f"/api/v1/encounters/{enc_id}/investigation-orders", json={
        "department": "laboratory",
        "test_or_modality": "Full Blood Count (FBC)",
        "priority": "routine"
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert order_res.status_code == 200
    order_id = order_res.json()["investigation_orders"][0]["id"]

    # 5. Diagnostic workflow
    # GET /diagnostics/work-queue
    diag_queue = client.get("/api/v1/diagnostics/work-queue", headers={"Authorization": f"Bearer {lab_token}"})
    assert diag_queue.status_code == 200
    assert any(o["id"] == order_id for o in diag_queue.json())

    # PATCH /diagnostics/orders/{id}/status
    patch_res = client.patch(f"/api/v1/diagnostics/orders/{order_id}/status?new_status=in_progress", headers={"Authorization": f"Bearer {lab_token}"})
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "in_progress"

    # POST /diagnostics/orders/{id}/lab-results
    lab_enter = client.post(f"/api/v1/diagnostics/orders/{order_id}/lab-results", json={
        "specimen_type": "Whole Blood",
        "result_payload": {"WBC": "6.5 x 10^9 /L", "Hemoglobin": "13.8 g/dL"}
    }, headers={"Authorization": f"Bearer {lab_token}"})
    assert lab_enter.status_code == 200

    # POST /diagnostics/orders/{id}/verify
    verify_res = client.post(f"/api/v1/diagnostics/orders/{order_id}/verify", headers={"Authorization": f"Bearer {lab_token}"})
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "verified"

# 7. Radiology Diagnostics Endpoints
def test_radiology_workflow():
    doc_token = get_token("doctor@fmc.vitalis.ng")
    rad_token = get_token("rad@fmc.vitalis.ng")
    pat = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {doc_token}"}).json()[0]
    fac_id = client.get("/api/v1/facilities").json()[0]["id"]

    # Open encounter and order X-Ray
    enc = client.post("/api/v1/encounters", json={
        "patient_id": pat["id"], "facility_id": fac_id, "visit_type": "walk_in", "priority": "routine",
        "presenting_complaint": "Persistent cough rule out consolidation"
    }, headers={"Authorization": f"Bearer {doc_token}"}).json()

    order = client.post(f"/api/v1/encounters/{enc['id']}/investigation-orders", json={
        "department": "radiology", "test_or_modality": "Chest X-Ray PA View", "priority": "routine"
    }, headers={"Authorization": f"Bearer {doc_token}"}).json()["investigation_orders"][0]

    # Enter radiology report
    rad_res = client.post(f"/api/v1/diagnostics/orders/{order['id']}/radiology-reports", json={
        "modality": "X-Ray", "body_region": "Chest",
        "findings": "Clear lung fields, normal cardiothoracic ratio.",
        "impression": "Normal chest radiograph."
    }, headers={"Authorization": f"Bearer {rad_token}"})
    assert rad_res.status_code == 200
    assert rad_res.json()["radiology_report"]["modality"] == "X-Ray"

    # Verify report
    ver_res = client.post(f"/api/v1/diagnostics/orders/{order['id']}/verify", headers={"Authorization": f"Bearer {rad_token}"})
    assert ver_res.status_code == 200
    assert ver_res.json()["status"] == "verified"

# 8. Referrals Endpoints
def test_referrals_lifecycle():
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pat_token = get_token("olumide@example.com")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]
    facs = client.get("/api/v1/facilities").json()
    dest_id = facs[1]["id"]

    # POST /referrals
    ref = client.post("/api/v1/referrals", json={
        "patient_id": pid,
        "destination_facility_id": dest_id,
        "clinical_reason": "Cardiology consult and advanced echocardiography",
        "service_needed": "Cardiology"
    }, headers={"Authorization": f"Bearer {pat_token}"}).json()
    ref_id = ref["id"]

    # GET /referrals/me
    my_refs = client.get("/api/v1/referrals/me", headers={"Authorization": f"Bearer {pat_token}"})
    assert my_refs.status_code == 200
    assert any(r["id"] == ref_id for r in my_refs.json())

    # GET /referrals/facility/{facility_id}
    fac_refs = client.get(f"/api/v1/referrals/facility/{dest_id}", headers={"Authorization": f"Bearer {doc_token}"})
    assert fac_refs.status_code == 200

    # PATCH /referrals/{id}/status
    patch_ref = client.patch(f"/api/v1/referrals/{ref_id}/status", json={
        "status": "accepted",
        "facility_response_reason": "Appointment confirmed for next Tuesday."
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert patch_ref.status_code == 200
    assert patch_ref.json()["status"] == "accepted"

# 9. Consent & QR Access Endpoints
def test_connect_qr_and_consent_endpoints():
    pat_token = get_token("olumide@example.com")
    nurse_token = get_token("nurse@fmc.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]

    # POST /connect/qr-grants
    grant = client.post("/api/v1/connect/qr-grants", json={
        "patient_id": pid, "scope": ["vitals", "allergies"], "duration_minutes": 15
    }, headers={"Authorization": f"Bearer {pat_token}"}).json()
    raw_token = grant["qr_token"]
    cid = grant["consent_id"]

    # POST /connect/redeem
    redeem = client.post("/api/v1/connect/redeem", json={
        "token": raw_token, "facility_id": "FMC-ABK"
    }, headers={"Authorization": f"Bearer {nurse_token}"})
    assert redeem.status_code == 200
    assert redeem.json()["status"] == "success"

    # DELETE /connect/consents/{consent_id}
    rev_res = client.delete(f"/api/v1/connect/consents/{cid}", headers={"Authorization": f"Bearer {pat_token}"})
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "success"

# 10. Intelligence & ML Model Endpoints
def test_intelligence_and_ml_endpoints():
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pat = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {doc_token}"}).json()[0]
    fac_id = client.get("/api/v1/facilities").json()[0]["id"]

    # Open encounter
    enc = client.post("/api/v1/encounters", json={
        "patient_id": pat["id"], "facility_id": fac_id, "visit_type": "walk_in", "priority": "routine",
        "presenting_complaint": "Acute severe chest pain and breathlessness"
    }, headers={"Authorization": f"Bearer {doc_token}"}).json()

    # POST /intelligence/encounters/{id}/differential
    diff = client.post(f"/api/v1/intelligence/encounters/{enc['id']}/differential", headers={"Authorization": f"Bearer {doc_token}"})
    assert diff.status_code == 200
    diff_data = diff.json()
    assert len(diff_data["possible_differentials"]) > 0

    # POST /intelligence/medication-safety-check
    med_chk = client.post("/api/v1/intelligence/medication-safety-check", json={
        "patient_id": pat["id"], "proposed_medications": ["Amoxicillin 500mg"]
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert med_chk.status_code == 200

    # Dedicated ML endpoints
    # POST /intelligence/ml/predict-heart-disease
    heart_ml = client.post("/api/v1/intelligence/ml/predict-heart-disease", json={
        "age": 55, "sex": 1, "cp": 2, "trestbps": 140.0, "chol": 230.0, "fbs": 0, "restecg": 1,
        "thalach": 145.0, "exang": 1, "oldpeak": 1.4, "slope": 2, "ca": 0, "thal": 2
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert heart_ml.status_code == 200
    assert heart_ml.json()["prediction"] in [0, 1]

    # POST /intelligence/ml/predict-diabetes
    diab_ml = client.post("/api/v1/intelligence/ml/predict-diabetes", json={
        "Pregnancies": 1, "Glucose": 120.0, "BloodPressure": 80.0, "SkinThickness": 20.0,
        "Insulin": 85.0, "BMI": 26.5, "DiabetesPedigreeFunction": 0.45, "Age": 42
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert diab_ml.status_code == 200
    assert diab_ml.json()["prediction"] in [0, 1]

# 11. Transfers Endpoints
def test_transfers_endpoints():
    doc_a = get_token("doctor@fmc.vitalis.ng")
    pat_token = get_token("olumide@example.com")
    doc_b = get_token("doctor@statehospital.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]
    fac_b_id = client.get("/api/v1/facilities").json()[1]["id"]

    # POST /transfers
    trf = client.post("/api/v1/transfers", json={
        "patient_id": pid, "recipient_facility_id": fac_b_id,
        "purpose": "Cardiovascular specialist care", "urgency": "urgent"
    }, headers={"Authorization": f"Bearer {doc_a}"}).json()
    trf_id = trf["id"]

    # POST /transfers/{id}/consent
    c_res = client.post(f"/api/v1/transfers/{trf_id}/consent", headers={"Authorization": f"Bearer {pat_token}"})
    assert c_res.status_code == 200

    # POST /transfers/{id}/send
    send_res = client.post(f"/api/v1/transfers/{trf_id}/send", headers={"Authorization": f"Bearer {doc_a}"})
    assert send_res.status_code == 200
    token = send_res.json()["transfer_token"]

    # POST /transfers/redeem
    red_res = client.post("/api/v1/transfers/redeem", json={"transfer_token": token}, headers={"Authorization": f"Bearer {doc_b}"})
    assert red_res.status_code == 200
    assert red_res.json()["status"] == "success"

# 12. Admin Endpoints
def test_admin_endpoints():
    admin_token = get_token("admin@fmc.vitalis.ng")

    # GET /admin/audit-events
    events = client.get("/api/v1/admin/audit-events", headers={"Authorization": f"Bearer {admin_token}"})
    assert events.status_code == 200
    assert isinstance(events.json(), list)

    # GET /admin/analytics/overview
    analytics = client.get("/api/v1/admin/analytics/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert analytics.status_code == 200
    data = analytics.json()
    assert "total_patients" in data
    assert "encounters_overview" in data

