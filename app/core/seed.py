from datetime import datetime, timezone, timedelta
import random
import sys
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models.models import (
    User, UserRole, Facility, FacilityDepartment, Service, FacilityService,
    Staff, Patient, Encounter, ReceptionIntake, NursingObservation,
    ClinicalNote, InvestigationOrder, LabResult, RadiologyReport,
    OrderDepartment, OrderStatus, EncounterStatus, EncounterPriority,
    VisitType, FamilyHistoryEntry, Referral, ReferralStatus
)

def init_db_and_seed(db: Session):
    Base.metadata.create_all(bind=engine)

    # Check if already seeded
    if db.query(Facility).first():
        print("Database already contains data, skipping seed.")
        return

    print("Seeding initial demo dataset...")

    # 1. Facilities in Abeokuta, Ogun State
    fac1 = Facility(
        name="Federal Medical Centre (FMC), Abeokuta",
        facility_code="FMC-ABK",
        facility_type="Tertiary Hospital",
        address="Bisi Onabanjo Way, Idi-Aba, Abeokuta",
        city="Abeokuta",
        state="Ogun State",
        latitude=7.1475,
        longitude=3.3619,
        contact_phone="+234-803-000-0101",
        emergency_available=True,
        verification_status="verified"
    )
    fac2 = Facility(
        name="State Hospital, Sokenu, Abeokuta",
        facility_code="SH-ABK",
        facility_type="Secondary Hospital",
        address="Sokenu Road, Ijaiye, Abeokuta",
        city="Abeokuta",
        state="Ogun State",
        latitude=7.1557,
        longitude=3.3450,
        contact_phone="+234-803-000-0202",
        emergency_available=True,
        verification_status="verified"
    )
    fac3 = Facility(
        name="Chrisland University Health Services",
        facility_code="CU-HS",
        facility_type="University Medical Clinic",
        address="Ajebo Road, Abeokuta",
        city="Abeokuta",
        state="Ogun State",
        latitude=7.1120,
        longitude=3.4150,
        contact_phone="+234-803-000-0303",
        emergency_available=False,
        verification_status="verified"
    )
    db.add_all([fac1, fac2, fac3])
    db.commit()

    # 2. Departments
    for fac in [fac1, fac2, fac3]:
        for code, name in [
            ("RECEPTION", "Front Desk Reception"),
            ("NURSING", "Nursing & Triage Station"),
            ("DOCTOR", "General Consultation & Clinics"),
            ("LAB", "Clinical Pathology & Diagnostic Lab"),
            ("RADIOLOGY", "Diagnostic Imaging & Radiology")
        ]:
            db.add(FacilityDepartment(
                facility_id=fac.id,
                department_code=code,
                name=name
            ))
    db.commit()

    # 3. Clinical Services
    srv_emergency = Service(service_code="EMERGENCY_CARE", service_name="Emergency Resuscitation & Trauma Care")
    srv_cardio = Service(service_code="CARDIOLOGY", service_name="Cardiology & ECG Evaluation")
    srv_lab = Service(service_code="DIAGNOSTIC_LAB", service_name="Clinical Pathology (FBC, Malaria RDT, Microscopy)")
    srv_rad = Service(service_code="IMAGING_RAD", service_name="Radiology (Digital X-Ray, Ultrasound)")
    srv_gen = Service(service_code="GENERAL_OUTPATIENT", service_name="General Outpatient & Family Medicine")
    db.add_all([srv_emergency, srv_cardio, srv_lab, srv_rad, srv_gen])
    db.commit()

    # Link services to facilities with verified availability status
    now = datetime.now(timezone.utc)
    db.add(FacilityService(facility_id=fac1.id, service_id=srv_emergency.id, availability_status="available", last_confirmed_at=now, reported_by="Dr. Balogun (Head of A&E)"))
    db.add(FacilityService(facility_id=fac1.id, service_id=srv_cardio.id, availability_status="available", last_confirmed_at=now, reported_by="Dr. Balogun (Head of A&E)"))
    db.add(FacilityService(facility_id=fac1.id, service_id=srv_lab.id, availability_status="available", last_confirmed_at=now, reported_by="Chief MLS Okon"))
    db.add(FacilityService(facility_id=fac1.id, service_id=srv_rad.id, availability_status="available", last_confirmed_at=now, reported_by="Dr. Radiologist"))
    db.add(FacilityService(facility_id=fac1.id, service_id=srv_gen.id, availability_status="available", last_confirmed_at=now, reported_by="Admin Desk"))

    db.add(FacilityService(facility_id=fac2.id, service_id=srv_emergency.id, availability_status="available", last_confirmed_at=now, reported_by="State A&E Officer"))
    db.add(FacilityService(facility_id=fac2.id, service_id=srv_lab.id, availability_status="available", last_confirmed_at=now, reported_by="Lab Unit"))
    db.add(FacilityService(facility_id=fac2.id, service_id=srv_gen.id, availability_status="available", last_confirmed_at=now, reported_by="Desk"))
    db.add(FacilityService(facility_id=fac2.id, service_id=srv_rad.id, availability_status="limited", last_confirmed_at=now, reported_by="Desk"))

    db.add(FacilityService(facility_id=fac3.id, service_id=srv_gen.id, availability_status="available", last_confirmed_at=now, reported_by="Nurse Supervisor"))
    db.add(FacilityService(facility_id=fac3.id, service_id=srv_lab.id, availability_status="limited", last_confirmed_at=now, reported_by="Nurse Supervisor"))
    db.commit()

    # 4. Hospital Staff Profiles (for FMC Abeokuta)
    # Password for all demo accounts: "vitalis2026"
    pw_hash = get_password_hash("vitalis2026")

    # Reception Officer
    u_rec = User(email="reception@fmc.vitalis.ng", phone="+234-800-000-0001", password_hash=pw_hash, role=UserRole.RECEPTION, full_name="Amina Bello (Reception Officer)")
    db.add(u_rec)
    db.commit()
    db.add(Staff(user_id=u_rec.id, facility_id=fac1.id, department="reception", professional_role="Intake Officer"))

    # Nurse
    u_nurse = User(email="nurse@fmc.vitalis.ng", phone="+234-800-000-0002", password_hash=pw_hash, role=UserRole.NURSE, full_name="Nurse Kehinde Adeyemi, RN")
    db.add(u_nurse)
    db.commit()
    db.add(Staff(user_id=u_nurse.id, facility_id=fac1.id, department="nursing", professional_role="Triage Nursing Officer"))

    # Doctor
    u_doc = User(email="doctor@fmc.vitalis.ng", phone="+234-800-000-0003", password_hash=pw_hash, role=UserRole.DOCTOR, full_name="Dr. Babatunde Ogundimu, FWACS")
    db.add(u_doc)
    db.commit()
    db.add(Staff(user_id=u_doc.id, facility_id=fac1.id, department="doctor", professional_role="Senior Medical Officer", license_number="MDCN-2015-8849"))

    # Lab Tech
    u_lab = User(email="lab@fmc.vitalis.ng", phone="+234-800-000-0004", password_hash=pw_hash, role=UserRole.LAB_TECH, full_name="Chukwudi Okon, AMLSCN")
    db.add(u_lab)
    db.commit()
    db.add(Staff(user_id=u_lab.id, facility_id=fac1.id, department="lab", professional_role="Medical Laboratory Scientist"))

    # Radiologist
    u_rad = User(email="rad@fmc.vitalis.ng", phone="+234-800-000-0005", password_hash=pw_hash, role=UserRole.RADIOLOGIST, full_name="Dr. Folashade Adeleke, FMCR")
    db.add(u_rad)
    db.commit()
    db.add(Staff(user_id=u_rad.id, facility_id=fac1.id, department="radiology", professional_role="Consultant Radiologist"))

    # Facility Admin
    u_admin = User(email="admin@fmc.vitalis.ng", phone="+234-800-000-0006", password_hash=pw_hash, role=UserRole.FACILITY_ADMIN, full_name="Director of Clinical Services FMC")
    db.add(u_admin)
    db.commit()
    db.add(Staff(user_id=u_admin.id, facility_id=fac1.id, department="admin", professional_role="Medical Director"))

    # Staff for Hospital B (State Hospital Sokenu)
    u_doc_sh = User(email="doctor@statehospital.vitalis.ng", phone="+234-800-000-0010", password_hash=pw_hash, role=UserRole.DOCTOR, full_name="Dr. Funke Soyinka, MBChB")
    db.add(u_doc_sh)
    db.commit()
    db.add(Staff(user_id=u_doc_sh.id, facility_id=fac2.id, department="doctor", professional_role="Attending Physician"))

    db.commit()

    # 5. Patient profile
    u_pat = User(email="olumide@example.com", phone="+234-803-123-4567", password_hash=pw_hash, role=UserRole.PATIENT, full_name="Olumide Adeleke")
    db.add(u_pat)
    db.commit()

    pat = Patient(
        user_id=u_pat.id,
        patient_number="VIT-2026-0001",
        first_name="Olumide",
        last_name="Adeleke",
        gender="Male",
        dob="1992-04-15",
        phone="+234-803-123-4567",
        address="14 Obantoko Road, Abeokuta",
        blood_group="O+",
        genotype="AS",
        allergies=["Penicillin", "Co-trimoxazole"],
        chronic_conditions=["Mild Bronchial Asthma"],
        current_medications=["Salbutamol Inhaler (PRN)", "Multivitamins"],
        emergency_contact_name="Bolanle Adeleke (Spouse)",
        emergency_contact_phone="+234-803-987-6543"
    )
    db.add(pat)
    db.commit()

    # Patient Family History
    fh1 = FamilyHistoryEntry(
        patient_id=pat.id,
        relationship_type="Father",
        condition="Essential Hypertension",
        age_of_onset=52,
        is_deceased=False,
        verification_status="clinician_confirmed"
    )
    fh2 = FamilyHistoryEntry(
        patient_id=pat.id,
        relationship_type="Mother",
        condition="Type 2 Diabetes Mellitus",
        age_of_onset=58,
        is_deceased=False,
        verification_status="patient_reported"
    )
    db.add_all([fh1, fh2])
    db.commit()

    seed_network_demo(db, fac1, fac2, fac3, pw_hash, u_rec, u_nurse, u_doc, u_lab)

    print("Demo dataset seeded successfully!")


# ---------------------------------------------------------------------------
# VITALIS network demo story
# ---------------------------------------------------------------------------
def _visit(db, *, patient, facility, days_ago, complaint, creator, nurse, doctor, vitals,
           note, labs=None, lab_user=None, status=EncounterStatus.COMPLETED,
           priority=EncounterPriority.ROUTINE, hour=10):
    """Create a fully documented (historical or current) encounter."""
    from app.engines.triage.rules import check_vital_warning
    now = datetime.now(timezone.utc)
    t0 = (now - timedelta(days=days_ago)).replace(hour=hour, minute=random.randint(5, 40), second=0, microsecond=0)
    if days_ago == 0:
        t0 = now - timedelta(minutes=random.randint(20, 70))
    enc = Encounter(
        encounter_number=f"ENC-{facility.facility_code}-{t0.strftime('%y%m%d')}-{random.randint(100, 999)}",
        patient_id=patient.id, facility_id=facility.id, visit_type=VisitType.WALK_IN,
        priority=priority, status=status, opened_at=t0,
        closed_at=t0 + timedelta(hours=3) if status == EncounterStatus.COMPLETED else None,
        created_by_id=creator.id,
    )
    db.add(enc)
    db.flush()
    db.add(ReceptionIntake(encounter_id=enc.id, presenting_complaint=complaint, arrival_mode="walk_in",
                           captured_by=creator.id, created_at=t0))
    has_warning = False
    for obs_type, value, unit in vitals or []:
        warn, msg = check_vital_warning(obs_type, value)
        has_warning = has_warning or warn
        db.add(NursingObservation(encounter_id=enc.id, observation_type=obs_type, value=value, unit=unit,
                                  is_warning=warn, warning_message=msg, measured_by=nurse.id,
                                  measured_at=t0 + timedelta(minutes=25)))
    if has_warning and status != EncounterStatus.COMPLETED:
        enc.priority = EncounterPriority.URGENT
    for test, specimen, payload, comment in labs or []:
        order = InvestigationOrder(
            order_number=f"LAB-{facility.facility_code}-{random.randint(1000, 9999)}", encounter_id=enc.id,
            ordering_clinician_id=doctor.id, department=OrderDepartment.LABORATORY, test_or_modality=test,
            clinical_indication=complaint[:120], priority="routine", status=OrderStatus.VERIFIED,
            ordered_at=t0 + timedelta(minutes=50), acknowledged_at=t0 + timedelta(minutes=60),
            completed_at=t0 + timedelta(hours=2),
        )
        db.add(order)
        db.flush()
        db.add(LabResult(order_id=order.id, specimen_type=specimen, result_payload=payload, comments=comment,
                         entered_by_id=(lab_user or doctor).id, entered_at=t0 + timedelta(hours=2),
                         verified_by_id=(lab_user or doctor).id, verified_at=t0 + timedelta(hours=2, minutes=10)))
    if note:
        db.add(ClinicalNote(encounter_id=enc.id, author_id=doctor.id, note_type="consultation",
                            history_of_complaint=note.get("history"), examination_findings=note.get("exam"),
                            assessment=note.get("assessment"), differential_considerations=note.get("differentials", []),
                            clinical_plan=note.get("plan"), disposition=note.get("disposition", "discharged"),
                            signed_at=t0 + timedelta(hours=2, minutes=30), created_at=t0 + timedelta(hours=2, minutes=30)))
    db.commit()
    return enc


def _lab(value, unit, ref, flag=""):
    return {"value": value, "unit": unit, "reference_range": ref, "flag": flag}


def seed_network_demo(db, fmc, sh, cu, pw_hash, u_rec, u_nurse, u_doc, u_lab):
    random.seed(2026)

    def staff(email, name, role, fac, dept, prof, lic=None):
        u = User(email=email, password_hash=pw_hash, role=role, full_name=name)
        db.add(u)
        db.flush()
        db.add(Staff(user_id=u.id, facility_id=fac.id, department=dept, professional_role=prof, license_number=lic))
        return u

    # Staff at the other network facilities (authors of the historical records)
    sh_doc = db.query(User).filter(User.email == "doctor@statehospital.vitalis.ng").first()
    sh_rec = staff("reception@statehospital.vitalis.ng", "Tunde Bakare (Records Officer)", UserRole.RECEPTION, sh, "reception", "Records Officer")
    sh_nurse = staff("nurse@statehospital.vitalis.ng", "Nurse Grace Oyelaran, RN", UserRole.NURSE, sh, "nursing", "Nursing Officer")
    sh_lab = staff("lab@statehospital.vitalis.ng", "Ibrahim Musa, AMLSCN", UserRole.LAB_TECH, sh, "lab", "Medical Laboratory Scientist")
    cu_doc = staff("doctor@chrisland.vitalis.ng", "Dr. Adaeze Nwankwo, MBBS", UserRole.DOCTOR, cu, "doctor", "Medical Officer", "MDCN-2018-2231")
    cu_nurse = staff("nurse@chrisland.vitalis.ng", "Nurse Bisi Alabi, RN", UserRole.NURSE, cu, "nursing", "Clinic Nurse")
    db.commit()

    # ---- Demo patient: Mrs Folake Adewale -------------------------------------------------
    u_fol = User(email="folake@example.com", phone="+234-806-555-0142", password_hash=pw_hash,
                 role=UserRole.PATIENT, full_name="Folake Adewale")
    db.add(u_fol)
    db.flush()
    fol = Patient(
        user_id=u_fol.id, patient_number="VIT-2026-0002", first_name="Folake", last_name="Adewale",
        gender="Female", dob=f"{datetime.now().year - 54}-03-08", phone="+234-806-555-0142",
        address="7 Oke-Ilewo Street, Abeokuta", blood_group="B+", genotype="AA",
        allergies=["Sulfonamides (Co-trimoxazole / Septrin)"],
        chronic_conditions=["Hypertension (Stage 2)", "Prediabetes"],
        current_medications=["Amlodipine 5 mg once daily"],
        emergency_contact_name="Kunle Adewale (Husband)", emergency_contact_phone="+234-803-220-1187",
    )
    db.add(fol)
    db.commit()
    db.add_all([
        FamilyHistoryEntry(patient_id=fol.id, relationship_type="Mother", condition="Type 2 Diabetes Mellitus",
                           age_of_onset=50, verification_status="clinician_confirmed"),
        FamilyHistoryEntry(patient_id=fol.id, relationship_type="Father", condition="Hypertension with stroke",
                           age_of_onset=55, is_deceased=True, notes="Died at 66 after a stroke",
                           verification_status="patient_reported"),
    ])
    db.commit()

    # Visit 1 - State Hospital Sokenu, ~10 months ago
    _visit(db, patient=fol, facility=sh, days_ago=300, creator=sh_rec, nurse=sh_nurse, doctor=sh_doc, lab_user=sh_lab,
           complaint="Recurrent headaches and occasional dizziness for 3 weeks",
           vitals=[("systolic_bp", 148, "mmHg"), ("diastolic_bp", 94, "mmHg"), ("pulse_rate", 84, "bpm"),
                   ("temperature", 36.7, "degC"), ("spo2", 98, "%"), ("weight", 79, "kg"), ("height", 162, "cm")],
           labs=[("Fasting Blood Glucose", "Plasma",
                  {"Fasting Blood Glucose": _lab(108, "mg/dL", "70-99", "H")}, "Mildly raised. Repeat advised.")],
           note={"history": "Frontal headaches, worse in the mornings, with occasional light-headedness. No visual symptoms.",
                 "exam": "Well-looking. BP 148/94 mmHg (repeat 146/92). No focal neurological deficit.",
                 "assessment": "Elevated blood pressure - Stage 1 hypertension (first presentation). Borderline fasting glucose.",
                 "differentials": ["Essential hypertension", "Tension-type headache"],
                 "plan": "Lifestyle modification: salt reduction, exercise, weight loss. Home BP monitoring. Review in 4 weeks.",
                 "disposition": "discharged"})

    # Visit 2 - Chrisland University Health Services, ~7 months ago (sulfonamide allergy documented here)
    _visit(db, patient=fol, facility=cu, days_ago=200, creator=cu_nurse, nurse=cu_nurse, doctor=cu_doc,
           complaint="Fever, chills, body aches and headache for 3 days",
           vitals=[("systolic_bp", 152, "mmHg"), ("diastolic_bp", 96, "mmHg"), ("pulse_rate", 104, "bpm"),
                   ("temperature", 38.9, "degC"), ("spo2", 97, "%"), ("weight", 80, "kg")],
           labs=[("Malaria RDT", "Whole blood", {"Malaria RDT (P. falciparum)": _lab("Positive", "", "Negative", "A")}, None),
                 ("Full Blood Count", "Whole blood", {"Haemoglobin": _lab(11.8, "g/dL", "12.0-15.5", "L"),
                                                      "WBC": _lab(6.4, "x10^9/L", "4.0-11.0")}, None)],
           note={"history": "3-day history of fever with chills and generalised body aches. Patient reports a previous severe "
                            "skin rash with facial swelling after taking Septrin (co-trimoxazole) in 2019.",
                 "exam": "Febrile 38.9 C, mildly pale, not jaundiced. BP 152/96 mmHg.",
                 "assessment": "Uncomplicated falciparum malaria. SULFONAMIDE ALLERGY documented (co-trimoxazole - rash and "
                               "facial swelling). BP persistently elevated.",
                 "differentials": ["Uncomplicated malaria", "Typhoid fever"],
                 "plan": "Artemether-lumefantrine 80/480 mg, 6-dose course. Paracetamol PRN. Avoid sulfonamide drugs. "
                         "Follow up BP with primary physician at State Hospital.",
                 "disposition": "discharged"})

    # Visit 3 - State Hospital Sokenu, ~2 months ago (amlodipine started, prediabetes)
    _visit(db, patient=fol, facility=sh, days_ago=60, creator=sh_rec, nurse=sh_nurse, doctor=sh_doc, lab_user=sh_lab,
           complaint="Follow-up for blood pressure; tiredness and waking at night to drink water",
           vitals=[("systolic_bp", 156, "mmHg"), ("diastolic_bp", 98, "mmHg"), ("pulse_rate", 88, "bpm"),
                   ("temperature", 36.6, "degC"), ("spo2", 98, "%"), ("weight", 82, "kg"), ("height", 162, "cm")],
           labs=[("Fasting Blood Glucose", "Plasma", {"Fasting Blood Glucose": _lab(124, "mg/dL", "70-99", "H")}, None),
                 ("HbA1c", "Whole blood", {"HbA1c": _lab(6.3, "%", "4.0-5.6", "H")}, "Prediabetes range."),
                 ("Lipid Profile", "Serum", {"Total Cholesterol": _lab(238, "mg/dL", "<200", "H"),
                                            "LDL Cholesterol": _lab(162, "mg/dL", "<130", "H"),
                                            "HDL Cholesterol": _lab(42, "mg/dL", ">50", "L"),
                                            "Triglycerides": _lab(190, "mg/dL", "<150", "H")}, None)],
           note={"history": "BP remains elevated despite lifestyle changes. Fatigue and nocturia; drinks water at night.",
                 "exam": "BMI 31.2 kg/m2. BP 156/98 mmHg. Heart sounds normal.",
                 "assessment": "Stage 2 hypertension. Prediabetes (FBG 124 mg/dL, HbA1c 6.3%). Dyslipidaemia.",
                 "differentials": ["Essential hypertension", "Prediabetes", "Dyslipidaemia"],
                 "plan": "Commenced Amlodipine 5 mg once daily. Dietary counselling for prediabetes. Repeat HbA1c in 3 months. "
                         "Consider statin at next review.",
                 "disposition": "discharged"})

    # ---- Other patients so the FMC queues look like a working day ---------------------------
    def patient(num, first, last, gender, age, phone, **kw):
        p = Patient(patient_number=num, first_name=first, last_name=last, gender=gender,
                    dob=f"{datetime.now().year - age}-0{random.randint(1, 9)}-1{random.randint(0, 9)}", phone=phone, **kw)
        db.add(p)
        db.commit()
        return p

    chinedu = patient("VIT-2026-0003", "Chinedu", "Okafor", "Male", 29, "+234-809-111-2203", blood_group="O+", genotype="AS")
    aisha = patient("VIT-2026-0004", "Aisha", "Lawal", "Female", 41, "+234-802-444-9021", blood_group="A+", genotype="AA")
    emeka = patient("VIT-2026-0005", "Emeka", "Nwosu", "Male", 36, "+234-813-777-5530", blood_group="O-", genotype="AA")
    olu = db.query(Patient).filter(Patient.patient_number == "VIT-2026-0001").first()

    # Awaiting nursing
    _visit(db, patient=chinedu, facility=fmc, days_ago=0, creator=u_rec, nurse=u_nurse, doctor=u_doc,
           complaint="Fever and body aches for 2 days", vitals=[], note=None, status=EncounterStatus.AWAITING_NURSING)
    _visit(db, patient=aisha, facility=fmc, days_ago=0, creator=u_rec, nurse=u_nurse, doctor=u_doc,
           complaint="Lower abdominal pain since yesterday", vitals=[], note=None, status=EncounterStatus.AWAITING_NURSING)
    # Awaiting doctor
    if olu:
        _visit(db, patient=olu, facility=fmc, days_ago=0, creator=u_rec, nurse=u_nurse, doctor=u_doc,
               complaint="Cough and wheeze for 3 days, worse at night",
               vitals=[("systolic_bp", 122, "mmHg"), ("diastolic_bp", 78, "mmHg"), ("pulse_rate", 96, "bpm"),
                       ("respiratory_rate", 22, "cpm"), ("temperature", 37.2, "degC"), ("spo2", 95, "%")],
               note=None, status=EncounterStatus.AWAITING_DOCTOR)
    # Lab work-queue item
    emeka_enc = _visit(db, patient=emeka, facility=fmc, days_ago=0, creator=u_rec, nurse=u_nurse, doctor=u_doc,
                       complaint="High fever with chills and vomiting",
                       vitals=[("temperature", 38.7, "degC"), ("pulse_rate", 102, "bpm"), ("systolic_bp", 118, "mmHg"),
                               ("diastolic_bp", 74, "mmHg"), ("spo2", 98, "%")],
                       note=None, status=EncounterStatus.AWAITING_INVESTIGATION)
    db.add(InvestigationOrder(order_number=f"LAB-FMC-ABK-{random.randint(1000, 9999)}", encounter_id=emeka_enc.id,
                              ordering_clinician_id=u_doc.id, department=OrderDepartment.LABORATORY,
                              test_or_modality="Malaria RDT", clinical_indication="Febrile illness, endemic area",
                              priority="urgent", status=OrderStatus.REQUESTED))
    db.commit()


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    if "--reset" in sys.argv:
        print("Resetting database...")
        reset_database()
    db = SessionLocal()
    init_db_and_seed(db)
    db.close()

