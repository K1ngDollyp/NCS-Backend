from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.models import (
    UserRole, EncounterPriority, VisitType, EncounterStatus,
    OrderDepartment, OrderStatus, ReferralStatus, TransferStatus, InsightReviewStatus
)

# ----------------- Auth & Users -----------------
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    full_name: str
    facility_id: Optional[str] = None
    department: Optional[str] = None

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

class UserRegister(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str = Field(..., min_length=6)
    full_name: str
    role: UserRole = UserRole.PATIENT

class UserLogin(BaseModel):
    identifier: str  # email or phone
    password: str

class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Facilities & Services -----------------
class ServiceCreate(BaseModel):
    service_code: str
    service_name: str
    description: Optional[str] = None

class FacilityCreate(BaseModel):
    name: str
    facility_code: str
    facility_type: str = "General Hospital"
    address: str
    city: str = "Abeokuta"
    state: str = "Ogun State"
    latitude: float
    longitude: float
    contact_phone: Optional[str] = None
    emergency_available: bool = True

class FacilityResponse(BaseModel):
    id: str
    name: str
    facility_code: str
    facility_type: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    contact_phone: Optional[str]
    emergency_available: bool
    verification_status: str

    class Config:
        from_attributes = True

class FacilitySuitabilityResult(BaseModel):
    facility: FacilityResponse
    suitability_score: float
    distance_km: float
    service_compatible: bool
    reported_availability: str
    last_confirmed_at: Optional[datetime] = None
    score_breakdown: Dict[str, float]
    recommendation_rationale: str

# ----------------- Patients -----------------
class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    gender: str
    dob: str  # YYYY-MM-DD
    phone: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergies: List[str] = []
    chronic_conditions: List[str] = []
    current_medications: List[str] = []
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

class PatientResponse(BaseModel):
    id: str
    patient_number: str
    user_id: Optional[str] = None
    first_name: str
    last_name: str
    gender: str
    dob: str
    phone: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergies: List[str] = []
    chronic_conditions: List[str] = []
    current_medications: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Family History -----------------
class FamilyHistoryCreate(BaseModel):
    relationship_type: str
    condition: str
    age_of_onset: Optional[int] = None
    is_deceased: bool = False
    notes: Optional[str] = None

class FamilyHistoryResponse(BaseModel):
    id: str
    relationship_type: str
    condition: str
    age_of_onset: Optional[int] = None
    is_deceased: bool
    notes: Optional[str] = None
    verification_status: str
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Encounters & Hospital Workflow -----------------
class EncounterCreate(BaseModel):
    patient_id: str
    facility_id: str
    visit_type: VisitType = VisitType.WALK_IN
    priority: EncounterPriority = EncounterPriority.ROUTINE
    # Reception intake fields
    presenting_complaint: str
    arrival_mode: str = "walk_in"
    referral_source: Optional[str] = None
    is_emergency_flag: bool = False
    administrative_notes: Optional[str] = None

class ReceptionIntakeResponse(BaseModel):
    id: str
    presenting_complaint: str
    arrival_mode: str
    referral_source: Optional[str]
    is_emergency_flag: bool
    administrative_notes: Optional[str]
    captured_by: str
    created_at: datetime

    class Config:
        from_attributes = True

class ObservationItem(BaseModel):
    observation_type: str  # systolic_bp, diastolic_bp, pulse_rate, respiratory_rate, temperature, spo2, weight, height, pain_score
    value: float
    unit: str
    nurse_note: Optional[str] = None

class NursingObservationsCreate(BaseModel):
    observations: List[ObservationItem]
    general_nurse_note: Optional[str] = None
    handover_to_doctor: bool = True  # Transitions status to AWAITING_DOCTOR

class NursingObservationResponse(BaseModel):
    id: str
    observation_type: str
    value: float
    unit: str
    is_warning: bool
    warning_message: Optional[str] = None
    nurse_note: Optional[str] = None
    measured_at: datetime
    measured_by: str

    class Config:
        from_attributes = True

class ClinicalNoteCreate(BaseModel):
    note_type: str = "consultation"
    history_of_complaint: Optional[str] = None
    examination_findings: Optional[str] = None
    assessment: Optional[str] = None
    differential_considerations: List[str] = []
    clinical_plan: Optional[str] = None
    disposition: str = "outpatient"
    is_draft: bool = False
    is_ai_assisted: bool = False
    ai_raw_draft: Optional[str] = None

class ClinicalNoteResponse(BaseModel):
    id: str
    author_id: str
    note_type: str
    history_of_complaint: Optional[str]
    examination_findings: Optional[str]
    assessment: Optional[str]
    differential_considerations: List[str]
    clinical_plan: Optional[str]
    disposition: str
    is_draft: bool
    is_ai_assisted: bool
    signed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Investigation Orders & Results -----------------
class InvestigationOrderCreate(BaseModel):
    department: OrderDepartment
    test_or_modality: str
    clinical_indication: Optional[str] = None
    priority: str = "routine"  # routine, stat, urgent

class LabResultCreate(BaseModel):
    specimen_type: Optional[str] = None
    result_payload: Dict[str, Any]
    comments: Optional[str] = None

class RadiologyReportCreate(BaseModel):
    modality: str
    body_region: str
    findings: str
    impression: str
    attachment_ref: Optional[str] = None

class InvestigationOrderResponse(BaseModel):
    id: str
    order_number: str
    encounter_id: str
    ordering_clinician_id: str
    department: OrderDepartment
    test_or_modality: str
    clinical_indication: Optional[str]
    priority: str
    status: OrderStatus
    ordered_at: datetime
    acknowledged_at: Optional[datetime]
    completed_at: Optional[datetime]
    lab_result: Optional[Dict[str, Any]] = None
    radiology_report: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class ConsolidatedEncounterResponse(BaseModel):
    id: str
    encounter_number: str
    patient_id: str
    patient_name: str
    patient_number: str
    facility_id: str
    facility_name: str
    visit_type: VisitType
    priority: EncounterPriority
    status: EncounterStatus
    opened_at: datetime
    closed_at: Optional[datetime]
    reception_intake: Optional[ReceptionIntakeResponse] = None
    nursing_observations: List[NursingObservationResponse] = []
    clinical_notes: List[ClinicalNoteResponse] = []
    investigation_orders: List[InvestigationOrderResponse] = []

    class Config:
        from_attributes = True

# ----------------- Triage -----------------
class SymptomInput(BaseModel):
    symptom: str
    duration_days: Optional[int] = 1
    severity: str = "mild"  # mild, moderate, severe
    details: Optional[str] = None

class TriageSessionCreate(BaseModel):
    patient_id: str
    symptoms: List[SymptomInput]

class TriageSessionResponse(BaseModel):
    id: str
    patient_id: str
    symptoms_structured: List[Dict[str, Any]]
    urgency_level: str
    matched_red_flags: List[str]
    protocol_version: str
    recommended_service: Optional[str]
    recommendation_summary: str
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Referrals -----------------
class ReferralCreate(BaseModel):
    patient_id: str
    destination_facility_id: str
    encounter_id: Optional[str] = None
    urgency: str = "routine"
    clinical_reason: str
    service_needed: str

class ReferralStatusUpdate(BaseModel):
    status: ReferralStatus
    facility_response_reason: Optional[str] = None

class ReferralResponse(BaseModel):
    id: str
    referral_number: str
    patient_id: str
    source_facility_id: str
    destination_facility_id: str
    encounter_id: Optional[str]
    urgency: str
    clinical_reason: str
    service_needed: str
    status: ReferralStatus
    facility_response_reason: Optional[str]
    created_at: datetime
    responded_at: Optional[datetime]

    class Config:
        from_attributes = True

# ----------------- Consent & QR Grants -----------------
class ConsentCreate(BaseModel):
    patient_id: str
    grantee_facility_id: Optional[str] = None
    scope: List[str] = ["vitals", "allergies", "medications", "lab_results", "notes"]
    purpose: str = "Clinical Consultation & Care Continuity"
    duration_minutes: int = 10  # 5-10 minutes prototype grant

class QRGrantResponse(BaseModel):
    grant_id: str
    consent_id: str
    qr_token: str  # The raw high-entropy token provided ONCE to display in QR code
    qr_code_base64: str  # Base64 data URI of QR image
    expires_at: datetime
    scope: List[str]

class QRRedeemRequest(BaseModel):
    token: str  # Raw token read from QR
    facility_id: str

# ----------------- Inter-Hospital Transfer -----------------
class TransferCreate(BaseModel):
    patient_id: str
    recipient_facility_id: str
    purpose: str
    urgency: str = "routine"
    scope: List[str] = ["summary", "vitals", "allergies", "medications", "diagnostics"]

class TransferResponse(BaseModel):
    id: str
    transfer_number: str
    patient_id: str
    sender_facility_id: str
    recipient_facility_id: str
    purpose: str
    urgency: str
    scope: List[str]
    status: TransferStatus
    patient_consented: bool
    created_at: datetime
    acknowledged_at: Optional[datetime]
    accessed_at: Optional[datetime]

    class Config:
        from_attributes = True

class TransferRedeemRequest(BaseModel):
    transfer_token: str

# ----------------- Intelligence & Clinical Decision Support -----------------
class MedicationSafetyCheckRequest(BaseModel):
    patient_id: str
    proposed_medications: List[str]

class MedicationSafetyCheckResponse(BaseModel):
    patient_id: str
    proposed_medications: List[str]
    allergy_conflicts: List[Dict[str, Any]]
    drug_interactions: List[Dict[str, Any]]
    contraindications_and_warnings: List[Dict[str, Any]]
    is_safe_to_proceed: bool
    reference_source: str
    disclaimer: str

class DifferentialRequest(BaseModel):
    encounter_id: str

class DifferentialResponse(BaseModel):
    encounter_id: str
    patient_id: str
    summary_of_findings: str
    red_flags_detected: List[str]
    possible_differentials: List[Dict[str, Any]]
    supporting_evidence: List[str]
    conflicting_evidence: List[str]
    missing_data_recommendations: List[str]
    model_version: str
    safety_disclaimer: str

class InsightReviewRequest(BaseModel):
    action: InsightReviewStatus  # ACCEPTED, EDITED, REJECTED
    rationale: Optional[str] = None
    edited_content: Optional[str] = None

