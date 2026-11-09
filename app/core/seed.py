from datetime import datetime, timezone
import random
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

    print("Seeding initial synthetic competition demo dataset...")

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

    # 5. Synthetic Patient: Olumide Adeleke (With realistic Nigerian clinical context)
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

    print("Synthetic competition dataset seeded successfully!")

if __name__ == "__main__":
    db = SessionLocal()
    init_db_and_seed(db)
    db.close()

