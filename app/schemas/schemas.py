from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.models.models import (
    UserRole, EncounterPriority, VisitType, EncounterStatus,
    OrderDepartment, OrderStatus, ReferralStatus, TransferStatus, InsightReviewStatus,
    EmergencyRequestStatus, HomeVisitStatus
)

# Auth & Users
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

# Facilities & Services
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

# Patients
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

# Family History
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

# Encounters & Hospital Workflow
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

# Investigation Orders & Results
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

# Triage
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

# Referrals
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

# Consent & QR Grants
class ConsentCreate(BaseModel):
    patient_id: str
    grantee_facility_id: Optional[str] = None
    scope: List[str] = ["vitals", "allergies", "medications", "lab_results", "notes"]
    purpose: str = "Clinical Consultation & Care Continuity"
    duration_minutes: int = 15

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

# Inter-Hospital Transfer
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

# Intelligence & Clinical Decision Support
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

# NCS ML Model Schemas
class HeartDiseaseMLInput(BaseModel):
    age: int = Field(..., ge=1, le=120, description="Age in years")
    sex: int = Field(..., ge=0, le=1, description="1 = Male, 0 = Female")
    cp: int = Field(..., ge=0, le=3, description="Chest pain type (0: typical angina, 1: atypical, 2: non-anginal, 3: asymptomatic)")
    trestbps: float = Field(..., ge=50, le=250, description="Resting blood pressure (mmHg)")
    chol: float = Field(..., ge=50, le=600, description="Serum cholesterol (mg/dl)")
    fbs: int = Field(..., ge=0, le=1, description="Fasting blood sugar > 120 mg/dl (1 = true, 0 = false)")
    restecg: int = Field(..., ge=0, le=2, description="Resting ECG results (0, 1, 2)")
    thalach: float = Field(..., ge=40, le=250, description="Maximum heart rate achieved")
    exang: int = Field(..., ge=0, le=1, description="Exercise induced angina (1 = yes, 0 = no)")
    oldpeak: float = Field(..., ge=0.0, le=10.0, description="ST depression induced by exercise relative to rest")
    slope: int = Field(..., ge=0, le=2, description="Slope of the peak exercise ST segment")
    ca: int = Field(..., ge=0, le=4, description="Number of major vessels colored by fluoroscopy (0-3)")
    thal: int = Field(..., ge=0, le=3, description="Thalassemia (1 = normal; 2 = fixed defect; 3 = reversable defect)")

class DiabetesMLInput(BaseModel):
    Pregnancies: int = Field(0, ge=0, description="Number of pregnancies")
    Glucose: float = Field(..., ge=0, le=500, description="Plasma glucose concentration a 2 hours in an oral glucose tolerance test")
    BloodPressure: float = Field(..., ge=0, le=250, description="Diastolic blood pressure (mm Hg)")
    SkinThickness: float = Field(0.0, ge=0, le=100, description="Triceps skin fold thickness (mm)")
    Insulin: float = Field(0.0, ge=0, le=1000, description="2-Hour serum insulin (mu U/ml)")
    BMI: float = Field(..., ge=10, le=80, description="Body mass index (weight in kg/(height in m)^2)")
    DiabetesPedigreeFunction: float = Field(0.5, ge=0.0, le=3.0, description="Diabetes pedigree function")
    Age: int = Field(..., ge=1, le=120, description="Age in years")

class MLPredictionResponse(BaseModel):
    prediction: int
    probability: float
    diagnosis: str
    model_version: str
    clinical_significance: str
    safety_disclaimer: str = (
        "Clinical decision support output only. Clinician review, independent evaluation, "
        "and diagnostic verification are required. Does not replace clinical judgment."
    )


# VITALIS CareConnect & Clinical AI Schemas
# Patient Dashboard (5 Primary Actions)
class CareConnectActionItem(BaseModel):
    action_key: str
    title: str
    description: str
    endpoint: str
    is_emergency: bool = False

class CareConnectDashboardResponse(BaseModel):
    patient_id: str
    patient_name: str
    headline: str = "How can we help you today?"
    subheadline: str = "Access medical assistance, connect with doctors and find the right healthcare facility."
    primary_actions: List[CareConnectActionItem]
    active_emergency_request_id: Optional[str] = None
    upcoming_appointments_count: int = 0
    active_home_visit_id: Optional[str] = None

# CareConnect Assistant ("Talk to AI")
class AssistantConversationCreate(BaseModel):
    patient_id: str
    title: Optional[str] = "CareConnect Symptom Guidance"
    modality: str = "text"  # text, voice
    history_access_permitted: bool = False
    initial_message: Optional[str] = None

class AssistantMessageCreate(BaseModel):
    content: str
    modality: str = "text"

class AssistantMessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_role: str
    content: str
    red_flags_triggered: List[str] = []
    structured_symptoms: List[str] = []
    recommended_professional: Optional[str] = None
    disclaimer: str
    created_at: datetime

    class Config:
        from_attributes = True

class AssistantConversationResponse(BaseModel):
    id: str
    patient_id: str
    title: str
    modality: str
    history_access_permitted: bool
    urgency_level: str
    recommended_professional_type: Optional[str] = None
    recommended_next_action: Optional[str] = None
    status: str
    created_at: datetime
    messages: List[AssistantMessageResponse] = []

    class Config:
        from_attributes = True

# Doctors, Availability, Appointments & Telemedicine ("Find a Doctor")
class DoctorAvailabilitySlotResponse(BaseModel):
    id: str
    day_of_week: str
    start_time: str
    end_time: str
    consultation_mode: str
    is_booked: bool

    class Config:
        from_attributes = True

class DoctorProfileResponse(BaseModel):
    id: str
    user_id: str
    facility_id: Optional[str] = None
    full_name: str
    specialization: str
    qualifications: str
    license_number: str
    verification_status: str
    years_of_experience: int
    bio: Optional[str] = None
    offers_telemedicine: bool
    offers_home_visits: bool
    consultation_fee_ngn: float
    languages: List[str] = []
    rating: float
    is_available_now: bool

    class Config:
        from_attributes = True

class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    scheduled_time: str
    consultation_mode: str = "video"  # video, audio, chat, in_person
    reason_for_visit: str
    shared_record_ids: List[str] = []

class AppointmentResponse(BaseModel):
    id: str
    appointment_number: str
    patient_id: str
    doctor_id: str
    scheduled_time: str
    consultation_mode: str
    reason_for_visit: str
    shared_record_ids: List[str] = []
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConsultationSessionCreate(BaseModel):
    channel_mode: str = "video"  # video, audio_fallback, messaging

class ConsultationMessageCreate(BaseModel):
    content: str
    attachment_ref: Optional[str] = None

class ConsultationPrescriptionSignRequest(BaseModel):
    doctor_recommendations: str
    medications: List[Dict[str, str]]  # [{"drug": "...", "dosage": "...", "duration": "..."}]

class ConsultationMessageResponse(BaseModel):
    id: str
    session_id: str
    sender_id: str
    sender_role: str
    content: str
    attachment_ref: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ConsultationSessionResponse(BaseModel):
    id: str
    appointment_id: str
    patient_id: str
    doctor_id: str
    channel_mode: str
    room_token: str
    session_url: str
    is_recorded: bool
    doctor_recommendations: Optional[str] = None
    signed_prescription: Optional[Dict[str, Any]] = None
    signed_by_doctor_id: Optional[str] = None
    signed_at: Optional[datetime] = None
    status: str
    started_at: datetime
    messages: List[ConsultationMessageResponse] = []

    class Config:
        from_attributes = True

# Home Visits ("Home visit")
class HomeVisitRequestCreate(BaseModel):
    patient_id: str
    professional_type_needed: str = "Medical Doctor"
    symptoms_or_reason: str
    address: str
    latitude: float = 7.1500
    longitude: float = 3.3500

class HomeVisitStatusUpdate(BaseModel):
    status: HomeVisitStatus
    tracking_status: Optional[str] = None
    estimated_arrival_minutes: Optional[int] = None
    visit_notes: Optional[str] = None

class VisitAssignmentResponse(BaseModel):
    id: str
    provider_user_id: str
    provider_name: str
    provider_role: str
    provider_license: str
    estimated_arrival_minutes: int
    service_fee_ngn: float
    tracking_status: str
    visit_notes: Optional[str] = None
    assigned_at: datetime

    class Config:
        from_attributes = True

class HomeVisitRequestResponse(BaseModel):
    id: str
    request_number: str
    patient_id: str
    professional_type_needed: str
    symptoms_or_reason: str
    address: str
    latitude: float
    longitude: float
    urgency_flag: bool
    redirected_emergency_reason: Optional[str] = None
    status: HomeVisitStatus
    created_at: datetime
    assignment: Optional[VisitAssignmentResponse] = None

    class Config:
        from_attributes = True

# Hospital Capabilities & Intelligent Hospital Search ("Find a hospital")
class HospitalCapabilityUpdate(BaseModel):
    services: List[str]
    specialists: List[str]
    equipment: List[str]
    has_operating_theatre: bool = False
    has_blood_bank: bool = False
    has_icu: bool = False
    has_nicu: bool = False
    reported_by: Optional[str] = None

class HospitalAvailabilityUpdate(BaseModel):
    emergency_acceptance_status: str = "accepting"  # accepting, limited, not_accepting, unknown
    available_general_beds: int = 10
    available_icu_beds: int = 2
    available_maternity_beds: int = 4
    specialists_on_duty: List[str] = []
    expected_wait_minutes: int = 10
    notes: Optional[str] = None
    reported_by: Optional[str] = None

class HospitalCapabilitySearchResult(BaseModel):
    facility: FacilityResponse
    suitability_score: float
    distance_km: float
    matched_capabilities: List[str]
    acceptance_status: str
    freshness_label: str
    last_confirmed_at: Optional[datetime] = None
    reported_by: str
    expected_wait_minutes: Optional[int] = None
    score_breakdown: Dict[str, float]
    why_this_facility: str

# Emergency Referral & Coordination ("Emergency assistance")
class EmergencyRequestCreate(BaseModel):
    patient_id: str
    initiated_by_role: str = "patient"  # patient, relative, clinician
    emergency_type: str
    presenting_complaint: str
    required_capabilities: List[str] = []
    patient_latitude: float = 7.1500
    patient_longitude: float = 3.3500
    patient_address: Optional[str] = None

class EmergencyHospitalConfirmation(BaseModel):
    facility_id: str
    accepted: bool
    reason_or_notes: Optional[str] = None

class EmergencyStatusUpdate(BaseModel):
    status: EmergencyRequestStatus
    details: Optional[str] = None

class EmergencyEventResponse(BaseModel):
    id: str
    event_type: str
    facility_id: Optional[str] = None
    details: str
    timestamp: datetime

    class Config:
        from_attributes = True

class TransportAssignmentResponse(BaseModel):
    id: str
    provider_name: str
    vehicle_type: str
    vehicle_callsign: str
    dispatch_status: str
    estimated_pickup_minutes: int
    estimated_hospital_arrival_minutes: int
    contact_phone: str
    assigned_at: datetime

    class Config:
        from_attributes = True

class EmergencyRequestResponse(BaseModel):
    id: str
    emergency_number: str
    patient_id: str
    initiated_by_role: str
    emergency_type: str
    presenting_complaint: str
    required_capabilities: List[str]
    patient_latitude: float
    patient_longitude: float
    patient_address: Optional[str]
    red_flags_detected: List[str]
    candidate_facilities: List[Dict[str, Any]]
    current_candidate_facility_id: Optional[str]
    confirmed_facility_id: Optional[str]
    linked_referral_id: Optional[str]
    status: EmergencyRequestStatus
    created_at: datetime
    events: List[EmergencyEventResponse] = []
    transport: Optional[TransportAssignmentResponse] = None

    class Config:
        from_attributes = True

# Clinical AI & Patient Documents
class PatientDocumentCreate(BaseModel):
    filename: str
    document_type: str = "lab_report"
    mime_type: str = "application/pdf"
    extracted_text: Optional[str] = None
    ocr_quality: str = "high"
    provenance: str = "patient_uploaded"

class PatientDocumentResponse(BaseModel):
    id: str
    patient_id: str
    filename: str
    document_type: str
    mime_type: str
    private_object_key: str
    extracted_text: Optional[str]
    ocr_quality: str
    provenance: str
    is_outdated_flag: bool
    has_conflict_flag: bool
    malware_scan_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ClinicalAIAnalysisResponse(BaseModel):
    id: str
    encounter_id: str
    patient_id: str
    summary: str
    differential_list: List[Dict[str, Any]]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    missing_info_flags: List[str]
    medication_considerations: List[Dict[str, Any]]
    red_flags: List[str]
    source_documents: List[str]
    model_version: str
    reference_set_version: str
    review_status: InsightReviewStatus
    reviewed_by_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    clinician_edits: Optional[str] = None
    safety_label: str
    created_at: datetime

    class Config:
        from_attributes = True



