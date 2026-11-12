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
    VisitType, FamilyHistoryEntry, Referral, ReferralStatus,
    DoctorProfile, DoctorAvailability, HospitalCapability, HospitalAvailability
)

def init_db_and_seed(db: Session):
    Base.metadata.create_all(bind=engine)

    # Check if already seeded
    if db.query(Facility).first():
        print("Base facilities already exist; checking CareConnect seed data...")
        seed_careconnect_data(db)
        return

    print("Seeding initial demo dataset...")

    # Facilities in Abeokuta, Ogun State
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

    # Departments
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

    # Clinical Services
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

    # Hospital Staff Profiles (for FMC Abeokuta)
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

    # Patient profile
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

    seed_careconnect_data(db)

    print("Demo dataset seeded successfully!")


def seed_careconnect_data(db: Session):
    """Seeds CareConnect hospital capabilities, availability, and verified doctor profiles if missing."""
    if db.query(HospitalCapability).first():
        print("CareConnect dataset already seeded.")
        return

    print("Seeding CareConnect capabilities, live availability, and verified doctors...")
    now = datetime.now(timezone.utc)

    fac1 = db.query(Facility).filter(Facility.facility_code == "FMC-ABK").first()
    fac2 = db.query(Facility).filter(Facility.facility_code == "SH-ABK").first()
    fac3 = db.query(Facility).filter(Facility.facility_code == "CU-HS").first()

    if fac1:
        db.add(HospitalCapability(
            facility_id=fac1.id,
            services=[
                "Emergency Obstetrics", "Cardiology", "Trauma Resuscitation",
                "Emergency Resuscitation", "Neurology", "Pediatrics", "General Surgery"
            ],
            specialists=[
                "Obstetrician/Gynaecologist", "Cardiologist", "General Surgeon",
                "Pediatrician", "Neurologist", "Consultant Radiologist"
            ],
            equipment=[
                "Operating Theatre", "Emergency C-Section", "Blood Transfusion",
                "NICU", "ICU", "CT Scanner", "Defibrillator", "ECG", "Digital X-Ray"
            ],
            has_operating_theatre=True,
            has_blood_bank=True,
            has_icu=True,
            has_nicu=True,
            last_confirmed_at=now,
            reported_by="Dr. Balogun (Head of A&E, FMC Abeokuta)"
        ))
        db.add(HospitalAvailability(
            facility_id=fac1.id,
            emergency_acceptance_status="accepting",
            available_general_beds=24,
            available_icu_beds=4,
            available_maternity_beds=8,
            specialists_on_duty=["Obstetrician/Gynaecologist", "Cardiologist", "Emergency Physician"],
            expected_wait_minutes=5,
            notes="24/7 Tertiary Emergency & Obstetric Theatre active.",
            last_confirmed_at=now,
            reported_by="Dr. Balogun (Head of A&E, FMC Abeokuta)"
        ))

    if fac2:
        db.add(HospitalCapability(
            facility_id=fac2.id,
            services=[
                "Emergency Obstetrics", "Emergency Resuscitation",
                "General Outpatient", "Internal Medicine", "Pediatrics"
            ],
            specialists=[
                "Obstetrician/Gynaecologist", "Medical Officer", "General Surgeon"
            ],
            equipment=[
                "Operating Theatre", "Emergency C-Section", "Blood Transfusion",
                "ECG", "Ultrasound"
            ],
            has_operating_theatre=True,
            has_blood_bank=True,
            has_icu=False,
            has_nicu=False,
            last_confirmed_at=now,
            reported_by="State Hospital A&E Duty Officer"
        ))
        db.add(HospitalAvailability(
            facility_id=fac2.id,
            emergency_acceptance_status="accepting",
            available_general_beds=12,
            available_icu_beds=0,
            available_maternity_beds=5,
            specialists_on_duty=["Obstetrician/Gynaecologist", "Medical Officer"],
            expected_wait_minutes=12,
            notes="Secondary emergency unit accepting general and obstetric cases.",
            last_confirmed_at=now,
            reported_by="State Hospital A&E Duty Officer"
        ))

    if fac3:
        db.add(HospitalCapability(
            facility_id=fac3.id,
            services=["General Outpatient", "Primary Care", "First Aid Stabilization"],
            specialists=["General Practitioner", "Registered Nurse"],
            equipment=["ECG", "Point-of-Care Malaria RDT"],
            has_operating_theatre=False,
            has_blood_bank=False,
            has_icu=False,
            has_nicu=False,
            last_confirmed_at=now,
            reported_by="Nurse Supervisor CU-HS"
        ))
        db.add(HospitalAvailability(
            facility_id=fac3.id,
            emergency_acceptance_status="not_accepting",
            available_general_beds=4,
            available_icu_beds=0,
            available_maternity_beds=0,
            specialists_on_duty=["General Practitioner"],
            expected_wait_minutes=10,
            notes="University clinic for primary outpatient care only.",
            last_confirmed_at=now,
            reported_by="Nurse Supervisor CU-HS"
        ))

    db.commit()

    # Verified Doctor Profiles for CareConnect ("Find a doctor" & "Home visit")
    u_doc1 = db.query(User).filter(User.email == "doctor@fmc.vitalis.ng").first()
    u_doc2 = db.query(User).filter(User.email == "doctor@statehospital.vitalis.ng").first()

    if u_doc1 and not db.query(DoctorProfile).filter(DoctorProfile.user_id == u_doc1.id).first():
        dp1 = DoctorProfile(
            user_id=u_doc1.id,
            facility_id=fac1.id if fac1 else None,
            full_name=u_doc1.full_name,
            specialization="Cardiology & Internal Medicine",
            qualifications="MBBS, FWACP, FMCP (Cardiology)",
            license_number="MDCN-2015-8849",
            verification_status="verified",
            years_of_experience=11,
            bio="Consultant Physician & Cardiologist at FMC Abeokuta specializing in hypertension, heart failure, and acute coronary care.",
            offers_telemedicine=True,
            offers_home_visits=False,
            consultation_fee_ngn=7500.0,
            languages=["English", "Yoruba"],
            rating=4.9,
            is_available_now=True
        )
        db.add(dp1)
        db.commit()
        db.refresh(dp1)
        db.add_all([
            DoctorAvailability(doctor_id=dp1.id, day_of_week="Monday", start_time="09:00", end_time="16:00", consultation_mode="online"),
            DoctorAvailability(doctor_id=dp1.id, day_of_week="Wednesday", start_time="10:00", end_time="17:00", consultation_mode="online"),
            DoctorAvailability(doctor_id=dp1.id, day_of_week="Friday", start_time="09:00", end_time="14:00", consultation_mode="in_person")
        ])

    if u_doc2 and not db.query(DoctorProfile).filter(DoctorProfile.user_id == u_doc2.id).first():
        dp2 = DoctorProfile(
            user_id=u_doc2.id,
            facility_id=fac2.id if fac2 else None,
            full_name=u_doc2.full_name,
            specialization="General Practice & Family Medicine (Home Visits)",
            qualifications="MBChB, Dip. Family Medicine",
            license_number="MDCN-2018-4412",
            verification_status="verified",
            years_of_experience=8,
            bio="Verified Family Physician offering both online telemedicine consultations and scheduled home medical visits across Abeokuta.",
            offers_telemedicine=True,
            offers_home_visits=True,
            consultation_fee_ngn=5000.0,
            languages=["English", "Yoruba", "Pidgin"],
            rating=4.8,
            is_available_now=True
        )
        db.add(dp2)
        db.commit()
        db.refresh(dp2)
        db.add_all([
            DoctorAvailability(doctor_id=dp2.id, day_of_week="Monday", start_time="08:00", end_time="18:00", consultation_mode="home_visit"),
            DoctorAvailability(doctor_id=dp2.id, day_of_week="Tuesday", start_time="09:00", end_time="17:00", consultation_mode="online"),
            DoctorAvailability(doctor_id=dp2.id, day_of_week="Thursday", start_time="08:00", end_time="18:00", consultation_mode="home_visit")
        ])

    db.commit()
    print("CareConnect dataset seeded successfully!")

if __name__ == "__main__":
    db = SessionLocal()
    init_db_and_seed(db)
    db.close()

