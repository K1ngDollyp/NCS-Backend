import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.models import OrderDepartment, OrderStatus, EncounterPriority, VisitType

client = TestClient(app)

def get_token(identifier: str, password: str = "vitalis2026") -> str:
    res = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, f"Login failed for {identifier}: {res.text}"
    return res.json()["access_token"]

# System Endpoints
def test_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "operational"

    res_h = client.get("/health")
    assert res_h.status_code == 200
    assert res_h.json()["status"] == "healthy"

# Auth Endpoints
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

# Patient & Family History Endpoints
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

# Triage Endpoints
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

# Facilities Endpoints
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

# Centralized Hospital Workflow: Encounters, Observations, Notes, Orders
def test_complete_encounter_workflow_and_queues():
    rec_token = get_token("reception@fmc.vitalis.ng")
    nurse_token = get_token("nurse@fmc.vitalis.ng")
    doc_token = get_token("doctor@fmc.vitalis.ng")
    lab_token = get_token("lab@fmc.vitalis.ng")

    pat = client.get("/api/v1/patients/search?query=Olumide", headers={"Authorization": f"Bearer {rec_token}"}).json()[0]
    fac_id = client.get("/api/v1/facilities").json()[0]["id"]

    # POST /encounters (Reception)
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

    # POST /encounters/{id}/observations (Nursing)
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

    # POST /encounters/{id}/clinical-notes (Doctor)
    note_res = client.post(f"/api/v1/encounters/{enc_id}/clinical-notes", json={
        "note_type": "consultation",
        "history_of_complaint": "Dry cough for 4 days, mild fatigue",
        "assessment": "Upper respiratory tract infection",
        "clinical_plan": "Supportive therapy, check chest X-ray if persistent",
        "disposition": "outpatient"
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert note_res.status_code == 200

    # POST /encounters/{id}/investigation-orders (Doctor orders Lab test)
    order_res = client.post(f"/api/v1/encounters/{enc_id}/investigation-orders", json={
        "department": "laboratory",
        "test_or_modality": "Full Blood Count (FBC)",
        "priority": "routine"
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert order_res.status_code == 200
    order_id = order_res.json()["investigation_orders"][0]["id"]

    # Diagnostic workflow
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

# Radiology Diagnostics Endpoints
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

# Referrals Endpoints
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

# Consent & QR Access Endpoints
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

# Intelligence & ML Model Endpoints
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

# Transfers Endpoints
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

# Admin Endpoints
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


# CareConnect: Central Patient Dashboard & 5 Primary Actions
def test_careconnect_dashboard_and_assistant():
    pat_token = get_token("olumide@example.com")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]

    # Central Dashboard with 5 Primary Actions
    dash = client.get("/api/v1/careconnect/dashboard", headers={"Authorization": f"Bearer {pat_token}"})
    assert dash.status_code == 200
    dash_data = dash.json()
    titles = [a["title"] for a in dash_data["primary_actions"]]
    assert titles == [
        "Talk to AI",
        "Find a doctor",
        "Home visit",
        "Find a hospital",
        "Emergency assistance"
    ]

    # Action 1: Talk to AI (CareConnect Assistant)
    conv_res = client.post("/api/v1/careconnect/assistant/conversations", json={
        "patient_id": pid,
        "modality": "text",
        "history_access_permitted": True,
        "initial_message": "I have had a mild headache and fatigue since yesterday"
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert conv_res.status_code == 200
    conv = conv_res.json()
    conv_id = conv["id"]
    assert len(conv["messages"]) == 2
    assert "non-physician" in conv["messages"][1]["disclaimer"].lower()

    # Follow-up message with deterministic emergency red-flag trigger
    msg_res = client.post(f"/api/v1/careconnect/assistant/conversations/{conv_id}/messages", json={
        "content": "Now I have severe chest pain radiating to arm and difficulty breathing"
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert msg_res.status_code == 200
    updated_conv = msg_res.json()
    assert updated_conv["urgency_level"] == "EMERGENCY_RED"
    assert updated_conv["recommended_next_action"] == "emergency_assistance"


# CareConnect Action 2: Find a Doctor, Booking & Telemedicine Consultation
def test_careconnect_doctors_appointments_and_telemedicine():
    pat_token = get_token("olumide@example.com")
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]

    # GET /doctors
    docs_res = client.get("/api/v1/doctors", headers={"Authorization": f"Bearer {pat_token}"})
    assert docs_res.status_code == 200
    docs = docs_res.json()
    assert len(docs) > 0
    doc_id = docs[0]["id"]

    # GET /doctors/{id}/availability
    avail_res = client.get(f"/api/v1/doctors/{doc_id}/availability", headers={"Authorization": f"Bearer {pat_token}"})
    assert avail_res.status_code == 200

    # POST /appointments
    appt_res = client.post("/api/v1/appointments", json={
        "patient_id": pid,
        "doctor_id": doc_id,
        "scheduled_time": "2026-11-15T10:00:00Z",
        "consultation_mode": "video",
        "reason_for_visit": "Follow-up blood pressure and chest discomfort review"
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert appt_res.status_code == 200
    appt_id = appt_res.json()["id"]

    # POST /consultations/{id}/session
    sess_res = client.post(f"/api/v1/consultations/{appt_id}/session", json={
        "channel_mode": "video"
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert sess_res.status_code == 200
    sess = sess_res.json()
    assert sess["is_recorded"] is False
    sess_id = sess["id"]

    # POST /consultations/{id}/messages
    cmsg_res = client.post(f"/api/v1/consultations/{sess_id}/messages", json={
        "content": "Good morning Doctor, I have uploaded my recent BP readings."
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert cmsg_res.status_code == 200

    # Doctor explicit signed prescription action
    rx_res = client.post(f"/api/v1/consultations/{sess_id}/prescriptions", json={
        "doctor_recommendations": "Continue low-sodium diet and monitor BP twice daily.",
        "medications": [{"drug": "Amlodipine", "dosage": "5mg OD", "duration": "30 days"}]
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert rx_res.status_code == 200
    assert rx_res.json()["signed_prescription"] is not None


# CareConnect Action 3: Home Visit & Emergency Safety Redirect
def test_careconnect_home_visits_and_emergency_redirect():
    pat_token = get_token("olumide@example.com")
    doc_token = get_token("doctor@statehospital.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]

    # Emergency symptom in home visit -> must redirect to emergency coordination, never routine home visit
    em_visit = client.post("/api/v1/home-visits", json={
        "patient_id": pid,
        "professional_type_needed": "Medical Doctor",
        "symptoms_or_reason": "Patient in active labour with severe bleeding",
        "address": "14 Obantoko Road, Abeokuta",
        "latitude": 7.1500,
        "longitude": 3.3500
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert em_visit.status_code == 200
    assert em_visit.json()["status"] == "redirected_to_emergency"
    assert em_visit.json()["urgency_flag"] is True

    # Routine home visit -> matched & confirmed with ETA
    routine_visit = client.post("/api/v1/home-visits", json={
        "patient_id": pid,
        "professional_type_needed": "Medical Doctor",
        "symptoms_or_reason": "Routine post-discharge wound dressing and vitals check",
        "address": "14 Obantoko Road, Abeokuta",
        "latitude": 7.1500,
        "longitude": 3.3500
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert routine_visit.status_code == 200
    rv_data = routine_visit.json()
    assert rv_data["status"] == "confirmed"
    assert rv_data["assignment"]["estimated_arrival_minutes"] > 0
    visit_id = rv_data["id"]

    # GET /home-visits/{id}
    get_rv = client.get(f"/api/v1/home-visits/{visit_id}", headers={"Authorization": f"Bearer {pat_token}"})
    assert get_rv.status_code == 200

    # PATCH /home-visits/{id}/status
    patch_rv = client.patch(f"/api/v1/home-visits/{visit_id}/status", json={
        "status": "en_route",
        "tracking_status": "en_route",
        "estimated_arrival_minutes": 12
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert patch_rv.status_code == 200
    assert patch_rv.json()["status"] == "en_route"


# CareConnect Action 4 & 5: Intelligent Hospital Search & Emergency Coordination
def test_careconnect_hospital_capability_search_and_emergency_coordination():
    pat_token = get_token("olumide@example.com")
    admin_token = get_token("admin@fmc.vitalis.ng")
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]
    facs = client.get("/api/v1/facilities").json()
    fmc_id = facs[0]["id"]

    # PUT /hospitals/{id}/capabilities & /availability
    cap_up = client.put(f"/api/v1/hospitals/{fmc_id}/capabilities", json={
        "services": ["Emergency Obstetrics", "Cardiology", "Trauma Resuscitation"],
        "specialists": ["Obstetrician/Gynaecologist", "Cardiologist"],
        "equipment": ["Operating Theatre", "Emergency C-Section", "Blood Transfusion", "NICU"],
        "has_operating_theatre": True,
        "has_blood_bank": True,
        "has_icu": True,
        "has_nicu": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert cap_up.status_code == 200

    avail_up = client.put(f"/api/v1/hospitals/{fmc_id}/availability", json={
        "emergency_acceptance_status": "accepting",
        "available_general_beds": 20,
        "available_icu_beds": 4,
        "available_maternity_beds": 6,
        "specialists_on_duty": ["Obstetrician/Gynaecologist", "Cardiologist"],
        "expected_wait_minutes": 5
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert avail_up.status_code == 200

    # GET /hospitals/search (Obstetric emergency capability filter)
    search_res = client.get(
        "/api/v1/hospitals/search?condition=Obstetric+Emergency&equipment=NICU&is_emergency=true",
        headers={"Authorization": f"Bearer {pat_token}"}
    )
    assert search_res.status_code == 200
    matched_hosps = search_res.json()
    assert len(matched_hosps) >= 1
    assert matched_hosps[0]["facility"]["id"] == fmc_id
    assert matched_hosps[0]["acceptance_status"] == "accepting"

    # Action 5: POST /emergency/requests
    em_res = client.post("/api/v1/emergency/requests", json={
        "patient_id": pid,
        "initiated_by_role": "relative",
        "emergency_type": "Obstetric Emergency",
        "presenting_complaint": "Pregnant patient in active labour with severe bleeding",
        "required_capabilities": ["Emergency Obstetrics", "Operating Theatre", "Blood Transfusion"],
        "patient_latitude": 7.1500,
        "patient_longitude": 3.3550,
        "patient_address": "14 Obantoko Road, Abeokuta"
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert em_res.status_code == 200
    em_data = em_res.json()
    em_id = em_data["id"]
    assert em_data["status"] == "awaiting_hospital_confirmation"
    top_candidate_id = em_data["current_candidate_facility_id"]
    assert top_candidate_id is not None

    # Hospital explicitly confirms capacity -> creates linked referral & dispatches transport
    conf_res = client.post(f"/api/v1/emergency/requests/{em_id}/confirmations", json={
        "facility_id": top_candidate_id,
        "accepted": True,
        "reason_or_notes": "Obstetric theatre and blood bank ready for immediate arrival."
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert conf_res.status_code == 200
    conf_data = conf_res.json()
    assert conf_data["status"] == "transport_coordinated"
    assert conf_data["confirmed_facility_id"] == top_candidate_id
    assert conf_data["linked_referral_id"] is not None
    assert conf_data["transport"] is not None

    # PATCH /emergency/requests/{id}/status -> en_route -> arrived -> handed_over
    st_res = client.patch(f"/api/v1/emergency/requests/{em_id}/status", json={
        "status": "arrived",
        "details": "Ambulance arrived at receiving hospital A&E bay."
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "arrived"


# Doctor Clinical AI Review & Document Upload Endpoints
def test_clinical_ai_review_and_patient_documents():
    pat_token = get_token("olumide@example.com")
    doc_token = get_token("doctor@fmc.vitalis.ng")
    pid = client.get("/api/v1/patients/me", headers={"Authorization": f"Bearer {pat_token}"}).json()["id"]
    fac_id = client.get("/api/v1/facilities").json()[0]["id"]

    # POST /patients/{id}/documents
    doc_up = client.post(f"/api/v1/patients/{pid}/documents", json={
        "filename": "prior_ecg_report.pdf",
        "document_type": "lab_report",
        "extracted_text": "Sinus tachycardia, non-specific ST changes."
    }, headers={"Authorization": f"Bearer {pat_token}"})
    assert doc_up.status_code == 200

    # Open encounter and run POST /encounters/{id}/ai/clinical-review
    enc = client.post("/api/v1/encounters", json={
        "patient_id": pid, "facility_id": fac_id, "visit_type": "walk_in", "priority": "urgent",
        "presenting_complaint": "Fever, chills and headache for 3 days"
    }, headers={"Authorization": f"Bearer {doc_token}"}).json()

    ai_rev = client.post(f"/api/v1/encounters/{enc['id']}/ai/clinical-review", headers={"Authorization": f"Bearer {doc_token}"})
    assert ai_rev.status_code == 200
    analysis_id = ai_rev.json()["id"]

    # GET /encounters/{id}/ai/analyses
    ai_list = client.get(f"/api/v1/encounters/{enc['id']}/ai/analyses", headers={"Authorization": f"Bearer {doc_token}"})
    assert ai_list.status_code == 200
    assert len(ai_list.json()) >= 1

    # PATCH /ai/analyses/{id}/review
    rev_patch = client.patch(f"/api/v1/ai/analyses/{analysis_id}/review", json={
        "action": "accepted",
        "rationale": "Reviewed and verified against clinical presentation."
    }, headers={"Authorization": f"Bearer {doc_token}"})
    assert rev_patch.status_code == 200
    assert rev_patch.json()["review_status"] == "accepted"


