import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, 
    Text, Float, Integer, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ----------------- Enums -----------------
class UserRole(str, enum.Enum):
    PATIENT = "patient"
    RECEPTION = "reception"
    NURSE = "nurse"
    DOCTOR = "doctor"
    LAB_TECH = "lab_tech"
    RADIOLOGIST = "radiologist"
    FACILITY_ADMIN = "facility_admin"
    NETWORK_ADMIN = "network_admin"

class EncounterPriority(str, enum.Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"

class VisitType(str, enum.Enum):
    WALK_IN = "walk_in"
    REFERRED = "referred"
    SCHEDULED = "scheduled"
    EMERGENCY_ARRIVAL = "emergency_arrival"

class EncounterStatus(str, enum.Enum):
    REGISTERED = "registered"
    AWAITING_NURSING = "awaiting_nursing"
    AWAITING_DOCTOR = "awaiting_doctor"
    AWAITING_INVESTIGATION = "awaiting_investigation"
    RESULTS_READY = "results_ready"
    AWAITING_DISPOSITION = "awaiting_disposition"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class OrderDepartment(str, enum.Enum):
    LABORATORY = "laboratory"
    RADIOLOGY = "radiology"

class OrderStatus(str, enum.Enum):
    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    SAMPLE_COLLECTED = "sample_collected"
    IN_PROGRESS = "in_progress"
    RESULT_ENTERED = "result_entered"
    VERIFIED = "verified"
    REVIEWED_BY_CLINICIAN = "reviewed_by_clinician"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

class ReferralStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MORE_INFORMATION = "more_information"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class TransferStatus(str, enum.Enum):
    DRAFT = "draft"
    AWAITING_CONSENT = "awaiting_consent"
    AUTHORISED = "authorised"
    PREPARING = "preparing"
    SENT = "sent"
    RECEIVED = "received"
    ACCESSED = "accessed"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REVOKED = "revoked"

class InsightReviewStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"

# ----------------- Core Entities -----------------

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone = Column(String(50), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.PATIENT)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    patient_profile = relationship("Patient", back_populates="user", uselist=False)
    staff_profile = relationship("Staff", back_populates="user", uselist=False)


class Facility(Base):
    __tablename__ = "facilities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, index=True)
    facility_code = Column(String(50), unique=True, nullable=False)
    facility_type = Column(String(100), default="General Hospital")  # Primary, Secondary, Tertiary, Clinic
    address = Column(String(255), nullable=False)
    city = Column(String(100), default="Abeokuta")
    state = Column(String(100), default="Ogun State")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    contact_phone = Column(String(50), nullable=True)
    emergency_available = Column(Boolean, default=True)
    verification_status = Column(String(50), default="verified")  # verified, pending, unverified
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    departments = relationship("FacilityDepartment", back_populates="facility")
    staff_members = relationship("Staff", back_populates="facility")
    services = relationship("FacilityService", back_populates="facility")
    encounters = relationship("Encounter", back_populates="facility")


class FacilityDepartment(Base):
    __tablename__ = "facility_departments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    department_code = Column(String(50), nullable=False)  # RECEPTION, NURSING, DOCTOR, LAB, RADIOLOGY
    name = Column(String(100), nullable=False)
    active_status = Column(Boolean, default=True)

    facility = relationship("Facility", back_populates="departments")


class Service(Base):
    __tablename__ = "services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_code = Column(String(50), unique=True, nullable=False)
    service_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)


class FacilityService(Base):
    __tablename__ = "facility_services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    service_id = Column(String(36), ForeignKey("services.id"), nullable=False)
    availability_status = Column(String(50), default="available")  # available, limited, unavailable, unknown
    last_confirmed_at = Column(DateTime(timezone=True), default=get_utc_now)
    reported_by = Column(String(255), nullable=True)

    facility = relationship("Facility", back_populates="services")
    service = relationship("Service")


class Staff(Base):
    __tablename__ = "staff"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    department = Column(String(50), nullable=False)  # reception, nursing, doctor, diagnostics, admin
    professional_role = Column(String(100), nullable=False)  # Medical Officer, Nurse Officer, Lab Scientist, Radiologist
    license_number = Column(String(100), nullable=True)
    active_status = Column(Boolean, default=True)

    user = relationship("User", back_populates="staff_profile")
    facility = relationship("Facility", back_populates="staff_members")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=True)  # nullable for assisted walk-in
    patient_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., VIT-2026-0001
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=False)  # male, female, other
    dob = Column(String(20), nullable=False)  # YYYY-MM-DD
    phone = Column(String(50), nullable=True, index=True)
    address = Column(String(255), nullable=True)
    blood_group = Column(String(10), nullable=True)
    genotype = Column(String(10), nullable=True)
    allergies = Column(JSON, default=list)  # list of allergy strings
    chronic_conditions = Column(JSON, default=list)  # list of conditions
    current_medications = Column(JSON, default=list)  # list of active meds
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    user = relationship("User", back_populates="patient_profile")
    encounters = relationship("Encounter", back_populates="patient")
    health_records = relationship("HealthRecord", back_populates="patient")
    family_history = relationship("FamilyHistoryEntry", back_populates="patient")
    consents = relationship("Consent", back_populates="patient")
    triage_sessions = relationship("TriageSession", back_populates="patient")


class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    encounter_number = Column(String(60), unique=True, index=True, nullable=False)  # ENC-FAC-2026-001
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False, index=True)
    visit_type = Column(SQLEnum(VisitType), default=VisitType.WALK_IN, nullable=False)
    priority = Column(SQLEnum(EncounterPriority), default=EncounterPriority.ROUTINE, nullable=False)
    status = Column(SQLEnum(EncounterStatus), default=EncounterStatus.REGISTERED, nullable=False, index=True)
    opened_at = Column(DateTime(timezone=True), default=get_utc_now)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    patient = relationship("Patient", back_populates="encounters")
    facility = relationship("Facility", back_populates="encounters")
    creator = relationship("User", foreign_keys=[created_by_id])
    
    reception_intake = relationship("ReceptionIntake", back_populates="encounter", uselist=False)
    nursing_observations = relationship("NursingObservation", back_populates="encounter", cascade="all, delete-orphan")
    clinical_notes = relationship("ClinicalNote", back_populates="encounter", cascade="all, delete-orphan")
    investigation_orders = relationship("InvestigationOrder", back_populates="encounter", cascade="all, delete-orphan")


class ReceptionIntake(Base):
    __tablename__ = "reception_intakes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), unique=True, nullable=False)
    presenting_complaint = Column(Text, nullable=False)
    arrival_mode = Column(String(50), default="walk_in")
    referral_source = Column(String(255), nullable=True)
    is_emergency_flag = Column(Boolean, default=False)
    administrative_notes = Column(Text, nullable=True)
    captured_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    encounter = relationship("Encounter", back_populates="reception_intake")
    officer = relationship("User", foreign_keys=[captured_by])


class NursingObservation(Base):
    __tablename__ = "nursing_observations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False, index=True)
    observation_type = Column(String(50), nullable=False)  # systolic_bp, diastolic_bp, pulse_rate, respiratory_rate, temperature, spo2, weight, height, pain_score
    value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)  # mmHg, bpm, cpm, degC, %, kg, cm, /10
    is_warning = Column(Boolean, default=False)
    warning_message = Column(String(255), nullable=True)
    nurse_note = Column(Text, nullable=True)
    measured_at = Column(DateTime(timezone=True), default=get_utc_now)
    measured_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    is_correction = Column(Boolean, default=False)
    original_observation_id = Column(String(36), nullable=True)

    encounter = relationship("Encounter", back_populates="nursing_observations")
    nurse = relationship("User", foreign_keys=[measured_by])


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    note_type = Column(String(50), default="consultation")  # consultation, review, progress, discharge
    history_of_complaint = Column(Text, nullable=True)
    examination_findings = Column(Text, nullable=True)
    assessment = Column(Text, nullable=True)
    differential_considerations = Column(JSON, default=list)
    clinical_plan = Column(Text, nullable=True)
    disposition = Column(String(100), default="outpatient")  # outpatient, admitted, referred, discharged
    is_draft = Column(Boolean, default=False)
    is_ai_assisted = Column(Boolean, default=False)
    ai_raw_draft = Column(Text, nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    encounter = relationship("Encounter", back_populates="clinical_notes")
    author = relationship("User", foreign_keys=[author_id])


class InvestigationOrder(Base):
    __tablename__ = "investigation_orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_number = Column(String(60), unique=True, index=True, nullable=False)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=False, index=True)
    ordering_clinician_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    department = Column(SQLEnum(OrderDepartment), nullable=False)
    test_or_modality = Column(String(150), nullable=False)  # e.g., "Full Blood Count", "Chest X-Ray", "Malaria Parasite test"
    clinical_indication = Column(Text, nullable=True)
    priority = Column(String(20), default="routine")  # routine, stat, urgent
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.REQUESTED, nullable=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    ordered_at = Column(DateTime(timezone=True), default=get_utc_now)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    encounter = relationship("Encounter", back_populates="investigation_orders")
    ordering_clinician = relationship("User", foreign_keys=[ordering_clinician_id])
    lab_result = relationship("LabResult", back_populates="order", uselist=False)
    radiology_report = relationship("RadiologyReport", back_populates="order", uselist=False)


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("investigation_orders.id"), unique=True, nullable=False)
    specimen_type = Column(String(100), nullable=True)  # Whole Blood, Serum, Urine
    collection_time = Column(DateTime(timezone=True), nullable=True)
    result_payload = Column(JSON, nullable=False)  # Dict of parameter: {value, unit, reference_range, flag}
    comments = Column(Text, nullable=True)
    entered_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    entered_at = Column(DateTime(timezone=True), default=get_utc_now)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("InvestigationOrder", back_populates="lab_result")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])


class RadiologyReport(Base):
    __tablename__ = "radiology_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("investigation_orders.id"), unique=True, nullable=False)
    modality = Column(String(50), nullable=False)  # X-Ray, Ultrasound, CT, MRI
    body_region = Column(String(100), nullable=False)  # Chest, Abdomen, Brain
    findings = Column(Text, nullable=False)
    impression = Column(Text, nullable=False)
    attachment_ref = Column(String(255), nullable=True)
    reported_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reported_at = Column(DateTime(timezone=True), default=get_utc_now)
    verified_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("InvestigationOrder", back_populates="radiology_report")
    reported_by = relationship("User", foreign_keys=[reported_by_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])


class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=True)
    record_type = Column(String(50), nullable=False)  # lab_result, imaging, prescription, discharge_summary, consultation_note
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    details = Column(JSON, default=dict)
    private_object_key = Column(String(255), nullable=True)  # Encrypted object storage key reference
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient", back_populates="health_records")


class FamilyHistoryEntry(Base):
    __tablename__ = "family_history_entries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)  # father, mother, sibling, child, maternal_uncle, etc.
    condition = Column(String(150), nullable=False)  # Hypertension, Type 2 Diabetes, Sickle Cell Disease, Breast Cancer
    age_of_onset = Column(Integer, nullable=True)
    is_deceased = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    verification_status = Column(String(50), default="patient_reported")  # patient_reported, clinician_confirmed
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient", back_populates="family_history")


class TriageSession(Base):
    __tablename__ = "triage_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    symptoms_structured = Column(JSON, nullable=False)  # List of {symptom, severity, duration, onset}
    urgency_level = Column(String(50), nullable=False)  # EMERGENCY_RED, URGENT_YELLOW, ROUTINE_GREEN
    matched_red_flags = Column(JSON, default=list)
    protocol_version = Column(String(50), default="VITALIS-TRIAGE-2026.1")
    recommended_service = Column(String(100), nullable=True)
    recommendation_summary = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient", back_populates="triage_sessions")


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    referral_number = Column(String(60), unique=True, index=True, nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    source_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    destination_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=True)
    urgency = Column(String(20), default="routine")  # routine, urgent, emergency
    clinical_reason = Column(Text, nullable=False)
    service_needed = Column(String(100), nullable=False)
    status = Column(SQLEnum(ReferralStatus), default=ReferralStatus.PENDING, nullable=False, index=True)
    facility_response_reason = Column(Text, nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient")
    source_facility = relationship("Facility", foreign_keys=[source_facility_id])
    destination_facility = relationship("Facility", foreign_keys=[destination_facility_id])


class Consent(Base):
    __tablename__ = "consents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    grantee_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)  # specific facility or any in network
    scope = Column(JSON, nullable=False)  # list of scopes e.g. ["vitals", "allergies", "medications", "lab_results", "notes"]
    purpose = Column(String(255), default="Clinical Consultation & Care Continuity")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient", back_populates="consents")
    qr_grants = relationship("QRAccessGrant", back_populates="consent")


class QRAccessGrant(Base):
    __tablename__ = "qr_access_grants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    consent_id = Column(String(36), ForeignKey("consents.id"), nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA-256 of high-entropy token
    expires_at = Column(DateTime(timezone=True), nullable=False)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    redeemed_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    consent = relationship("Consent", back_populates="qr_grants")
    redeemed_by = relationship("User", foreign_keys=[redeemed_by_id])


class RecordTransfer(Base):
    __tablename__ = "record_transfers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    transfer_number = Column(String(60), unique=True, index=True, nullable=False)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    sender_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    recipient_facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False)
    sender_clinician_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    purpose = Column(String(255), nullable=False)
    urgency = Column(String(20), default="routine")
    scope = Column(JSON, default=list)  # Categories included
    package_payload = Column(JSON, nullable=True)  # Encrypted/Structured portable medical bundle
    status = Column(SQLEnum(TransferStatus), default=TransferStatus.DRAFT, nullable=False)
    patient_consented = Column(Boolean, default=False)
    consent_recorded_at = Column(DateTime(timezone=True), nullable=True)
    access_token_hash = Column(String(64), unique=True, index=True, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    accessed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient")
    sender_facility = relationship("Facility", foreign_keys=[sender_facility_id])
    recipient_facility = relationship("Facility", foreign_keys=[recipient_facility_id])


class ClinicalInsight(Base):
    __tablename__ = "clinical_insights"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=True)
    insight_type = Column(String(50), nullable=False)  # differential, medication_safety, health_risk, trend_alert
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    supporting_evidence = Column(JSON, default=list)
    conflicting_evidence = Column(JSON, default=list)
    missing_data = Column(JSON, default=list)
    model_version = Column(String(50), default="VITALIS-INTELLIGENCE-V1-DRAFT")
    safety_disclaimer = Column(
        String(255), 
        default="Decision support draft — clinician review required. Not an autonomous diagnosis or prescription."
    )
    review_status = Column(SQLEnum(InsightReviewStatus), default=InsightReviewStatus.PENDING)
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    clinician_action_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient")
    encounter = relationship("Encounter")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    actor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True, index=True)
    encounter_id = Column(String(36), ForeignKey("encounters.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # VIEW_RECORD, OPEN_ENCOUNTER, RECORD_VITALS, SIGN_NOTE, etc.
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=get_utc_now)
    event_metadata = Column(JSON, default=dict)



class RecordAccessRequest(Base):
    """
    Patient-approved cross-facility record access (one-time code flow).
    A facility requests access to a patient's network record; the patient
    receives a 6-digit one-time code and shares it with the requesting staff.
    Only the SHA-256 hash of the code is stored.
    """
    __tablename__ = "record_access_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    facility_id = Column(String(36), ForeignKey("facilities.id"), nullable=False, index=True)
    requested_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    purpose = Column(String(255), default="Clinical consultation & continuity of care")
    otp_hash = Column(String(64), nullable=False)
    demo_code = Column(String(6), nullable=True)  # Simulated SMS / app notification delivery (demo mode only)
    status = Column(String(20), default="pending")  # pending, approved, expired, cancelled, locked
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    consent_id = Column(String(36), ForeignKey("consents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    patient = relationship("Patient")
    facility = relationship("Facility")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    consent = relationship("Consent")
