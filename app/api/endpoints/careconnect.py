import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_random_token, hash_token
from app.api.deps import get_current_user, require_roles
from app.services.qr_service import generate_qr_code_data_uri
from app.models.models import (
    User, UserRole, Patient, Facility, Referral, ReferralStatus,
    AssistantConversation, AssistantMessage,
    DoctorProfile, DoctorAvailability, Appointment,
    ConsultationSession, ConsultationMessage,
    HomeVisitRequest, VisitAssignment, HomeVisitStatus,
    HospitalCapability, HospitalAvailability,
    EmergencyRequest, EmergencyEvent, TransportAssignment, EmergencyRequestStatus,
    HealthRecord, PatientDocument, ClinicalAIAnalysis, InsightReviewStatus,
    Consent, QRAccessGrant, Encounter, EncounterStatus, get_utc_now
)
from app.schemas.schemas import (
    CareConnectDashboardResponse, CareConnectActionItem,
    AssistantConversationCreate, AssistantConversationResponse,
    AssistantMessageCreate, AssistantMessageResponse,
    DoctorProfileResponse, DoctorAvailabilitySlotResponse,
    AppointmentCreate, AppointmentResponse,
    ConsultationSessionCreate, ConsultationSessionResponse,
    ConsultationMessageCreate, ConsultationMessageResponse,
    ConsultationPrescriptionSignRequest,
    HomeVisitRequestCreate, HomeVisitRequestResponse, HomeVisitStatusUpdate,
    HospitalCapabilityUpdate, HospitalAvailabilityUpdate, HospitalCapabilitySearchResult,
    FacilityResponse,
    EmergencyRequestCreate, EmergencyRequestResponse,
    EmergencyHospitalConfirmation, EmergencyStatusUpdate,
    ClinicalAIAnalysisResponse, InsightReviewRequest,
    ConsentCreate, QRGrantResponse, QRRedeemRequest,
    ReferralResponse, ReferralStatusUpdate
)
from app.engines.triage.rules import TriageEngine
from app.engines.matching.matcher import FacilityMatcher
from app.services.audit import log_audit_event

router = APIRouter(tags=["VITALIS CareConnect - Patient Access & Emergency Navigation"])


# =================================================================================
# 0. PATIENT CARECONNECT CENTRAL DASHBOARD (5 Primary Actions)
# =================================================================================

@router.get("/careconnect/dashboard", response_model=CareConnectDashboardResponse)
def get_careconnect_patient_dashboard(
    patient_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Central CareConnect patient dashboard providing the 5 primary actions:
    1. Talk to AI
    2. Find a doctor
    3. Home visit
    4. Find a hospital
    5. Emergency assistance
    """
    patient = None
    if patient_id:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
    elif current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()

    if not patient:
        patient = db.query(Patient).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    active_em = db.query(EmergencyRequest).filter(
        EmergencyRequest.patient_id == patient.id,
        EmergencyRequest.status.notin_([EmergencyRequestStatus.HANDED_OVER, EmergencyRequestStatus.CANCELLED])
    ).order_by(EmergencyRequest.created_at.desc()).first()

    upcoming_appts = db.query(Appointment).filter(
        Appointment.patient_id == patient.id,
        Appointment.status.in_(["requested", "confirmed", "in_progress"])
    ).count()

    active_visit = db.query(HomeVisitRequest).filter(
        HomeVisitRequest.patient_id == patient.id,
        HomeVisitRequest.status.in_([
            HomeVisitStatus.REQUESTED, HomeVisitStatus.MATCHED,
            HomeVisitStatus.CONFIRMED, HomeVisitStatus.EN_ROUTE,
            HomeVisitStatus.ARRIVED, HomeVisitStatus.IN_PROGRESS
        ])
    ).order_by(HomeVisitRequest.created_at.desc()).first()

    actions = [
        CareConnectActionItem(
            action_key="talk_to_ai",
            title="Talk to AI",
            description="Describe symptoms and get preliminary guidance.",
            endpoint="/api/v1/careconnect/assistant/conversations",
            is_emergency=False
        ),
        CareConnectActionItem(
            action_key="find_a_doctor",
            title="Find a doctor",
            description="Connect with a licensed medical professional.",
            endpoint="/api/v1/doctors",
            is_emergency=False
        ),
        CareConnectActionItem(
            action_key="home_visit",
            title="Home visit",
            description="Request a medical professional at home.",
            endpoint="/api/v1/home-visits",
            is_emergency=False
        ),
        CareConnectActionItem(
            action_key="find_a_hospital",
            title="Find a hospital",
            description="Find facilities capable of treating your condition.",
            endpoint="/api/v1/hospitals/search",
            is_emergency=False
        ),
        CareConnectActionItem(
            action_key="emergency_assistance",
            title="Emergency assistance",
            description="For urgent medical situations, connect to emergency coordination and appropriate medical facilities immediately.",
            endpoint="/api/v1/emergency/requests",
            is_emergency=True
        )
    ]

    return CareConnectDashboardResponse(
        patient_id=patient.id,
        patient_name=f"{patient.first_name} {patient.last_name}",
        primary_actions=actions,
        active_emergency_request_id=active_em.id if active_em else None,
        upcoming_appointments_count=upcoming_appts,
        active_home_visit_id=active_visit.id if active_visit else None
    )


# =================================================================================
# 1. TALK TO AI: CareConnect Assistant (Text/Voice + Deterministic Safety Rules)
# =================================================================================

def _evaluate_assistant_turn(
    user_text: str,
    patient: Patient,
    history_access_permitted: bool,
    db: Session
) -> Dict[str, Any]:
    """
    Runs deterministic red-flag rules ahead of any conversational guidance.
    Never claims a confirmed diagnosis or replaces emergency care.
    """
    urgency, red_flags, recommended_service, triage_guidance = TriageEngine.evaluate_symptoms(
        [{"symptom": user_text, "details": ""}]
    )

    text_low = user_text.lower()
    structured = []
    for kw in [
        "chest pain", "shortness of breath", "difficulty breathing", "bleeding",
        "active labour", "fever", "headache", "abdominal pain", "dizziness",
        "cough", "vomiting", "weakness", "joint pain"
    ]:
        if kw in text_low:
            structured.append(kw)
    if not structured:
        structured.append("reported symptom intake")

    # Determine recommended professional type & next action
    if urgency == "EMERGENCY_RED":
        prof_type = "Emergency Physician / Specialist Resuscitation Team"
        next_action = "emergency_assistance"
    elif "pregnant" in text_low or "labour" in text_low or "obstetric" in text_low:
        prof_type = "Obstetrician & Gynaecologist"
        next_action = "find_a_hospital"
    elif "heart" in text_low or "chest" in text_low or "palpitation" in text_low or "blood pressure" in text_low:
        prof_type = "Cardiologist / Internal Medicine Physician"
        next_action = "find_a_doctor"
    elif "child" in text_low or "baby" in text_low or "infant" in text_low:
        prof_type = "Pediatrician"
        next_action = "find_a_doctor"
    elif urgency == "URGENT_YELLOW":
        prof_type = "Medical Officer / Internal Medicine Specialist"
        next_action = "find_a_hospital"
    else:
        prof_type = "Licensed General Practitioner / Family Physician"
        next_action = "find_a_doctor"

    context_note = ""
    if history_access_permitted:
        conds = ", ".join(patient.chronic_conditions or []) or "None recorded"
        allergies = ", ".join(patient.allergies or []) or "None recorded"
        docs_count = db.query(PatientDocument).filter(PatientDocument.patient_id == patient.id).count()
        context_note = (
            f" Based on your permitted medical profile (Conditions: {conds}; Allergies: {allergies}; "
            f"Uploaded documents reviewed: {docs_count}), "
        )

    if urgency == "EMERGENCY_RED":
        reply = (
            f"EMERGENCY WARNING DETECTED: {', '.join(red_flags)}. "
            f"{triage_guidance}{context_note}"
            f"I am a non-physician AI assistant and cannot diagnose or replace emergency care. "
            f"Please trigger 'Emergency assistance' immediately so VITALIS can coordinate a confirmed receiving hospital and transport."
        )
    elif urgency == "URGENT_YELLOW":
        reply = (
            f"Preliminary Guidance (Non-Physician): Your symptoms ({', '.join(structured)}) warrant prompt clinical evaluation today. "
            f"{triage_guidance}{context_note}"
            f"Recommended professional: {prof_type}. Would you like to search for a capable hospital or book an urgent consultation with a verified doctor?"
        )
    else:
        reply = (
            f"Preliminary Guidance (Non-Physician): Thank you for sharing your symptoms ({', '.join(structured)}). "
            f"No immediate emergency red flags were detected by our deterministic safety protocol.{context_note}"
            f"Possible considerations should be evaluated by a {prof_type}. "
            f"You can book an online video/audio consultation, request a home visit, or search for a nearby hospital."
        )

    return {
        "urgency": urgency,
        "red_flags": red_flags,
        "structured_symptoms": structured,
        "recommended_professional": prof_type,
        "recommended_next_action": next_action,
        "reply": reply
    }


@router.post("/careconnect/assistant/conversations", response_model=AssistantConversationResponse)
def start_assistant_conversation(
    conv_in: AssistantConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == conv_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    conv = AssistantConversation(
        patient_id=patient.id,
        title=conv_in.title or "CareConnect Symptom Guidance",
        modality=conv_in.modality,
        history_access_permitted=conv_in.history_access_permitted,
        urgency_level="ROUTINE_GREEN",
        status="active"
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    if conv_in.initial_message:
        user_msg = AssistantMessage(
            conversation_id=conv.id,
            sender_role="patient",
            content=conv_in.initial_message
        )
        db.add(user_msg)

        eval_res = _evaluate_assistant_turn(
            conv_in.initial_message, patient, conv.history_access_permitted, db
        )
        conv.urgency_level = eval_res["urgency"]
        conv.recommended_professional_type = eval_res["recommended_professional"]
        conv.recommended_next_action = eval_res["recommended_next_action"]

        ai_msg = AssistantMessage(
            conversation_id=conv.id,
            sender_role="assistant",
            content=eval_res["reply"],
            red_flags_triggered=eval_res["red_flags"],
            structured_symptoms=eval_res["structured_symptoms"],
            recommended_professional=eval_res["recommended_professional"]
        )
        db.add(ai_msg)
        db.commit()
        db.refresh(conv)

    log_audit_event(
        db,
        action="CARECONNECT_ASSISTANT_STARTED",
        resource_type="assistant_conversation",
        resource_id=conv.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"history_access_permitted": conv.history_access_permitted, "urgency": conv.urgency_level}
    )

    return conv


@router.post("/careconnect/assistant/conversations/{id}/messages", response_model=AssistantConversationResponse)
def post_assistant_message(
    id: str,
    msg_in: AssistantMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(AssistantConversation).filter(AssistantConversation.id == id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    patient = conv.patient

    user_msg = AssistantMessage(
        conversation_id=conv.id,
        sender_role="patient",
        content=msg_in.content
    )
    db.add(user_msg)

    eval_res = _evaluate_assistant_turn(
        msg_in.content, patient, conv.history_access_permitted, db
    )
    if eval_res["urgency"] == "EMERGENCY_RED" or conv.urgency_level != "EMERGENCY_RED":
        conv.urgency_level = eval_res["urgency"]
    conv.recommended_professional_type = eval_res["recommended_professional"]
    conv.recommended_next_action = eval_res["recommended_next_action"]

    ai_msg = AssistantMessage(
        conversation_id=conv.id,
        sender_role="assistant",
        content=eval_res["reply"],
        red_flags_triggered=eval_res["red_flags"],
        structured_symptoms=eval_res["structured_symptoms"],
        recommended_professional=eval_res["recommended_professional"]
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(conv)

    log_audit_event(
        db,
        action="CARECONNECT_ASSISTANT_MESSAGE",
        resource_type="assistant_conversation",
        resource_id=conv.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"urgency": conv.urgency_level, "red_flags": eval_res["red_flags"]}
    )

    return conv


# =================================================================================
# 2. FIND A DOCTOR: Discovery, Availability, Appointments & Telemedicine
# =================================================================================

@router.get("/doctors", response_model=List[DoctorProfileResponse])
def search_verified_doctors(
    specialization: Optional[str] = None,
    offers_telemedicine: Optional[bool] = None,
    offers_home_visits: Optional[bool] = None,
    available_now: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists only verified medical professionals.
    Supports filtering by specialization, online telemedicine, and home visit availability.
    """
    query = db.query(DoctorProfile).filter(DoctorProfile.verification_status == "verified")
    if specialization:
        query = query.filter(DoctorProfile.specialization.ilike(f"%{specialization}%"))
    if offers_telemedicine is not None:
        query = query.filter(DoctorProfile.offers_telemedicine == offers_telemedicine)
    if offers_home_visits is not None:
        query = query.filter(DoctorProfile.offers_home_visits == offers_home_visits)
    if available_now is not None:
        query = query.filter(DoctorProfile.is_available_now == available_now)

    return query.order_by(DoctorProfile.rating.desc()).all()


@router.get("/doctors/{id}/availability", response_model=List[DoctorAvailabilitySlotResponse])
def get_doctor_availability(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(DoctorProfile).filter(DoctorProfile.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return doc.availability_slots


@router.post("/appointments", response_model=AppointmentResponse)
def book_doctor_appointment(
    appt_in: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == appt_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    doc = db.query(DoctorProfile).filter(
        DoctorProfile.id == appt_in.doctor_id,
        DoctorProfile.verification_status == "verified"
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Verified doctor profile not found")

    appt_num = f"APT-2026-{random.randint(10000, 99999)}"
    appt = Appointment(
        appointment_number=appt_num,
        patient_id=patient.id,
        doctor_id=doc.id,
        scheduled_time=appt_in.scheduled_time,
        consultation_mode=appt_in.consultation_mode,
        reason_for_visit=appt_in.reason_for_visit,
        shared_record_ids=appt_in.shared_record_ids,
        status="confirmed"
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    log_audit_event(
        db,
        action="APPOINTMENT_BOOKED",
        resource_type="appointment",
        resource_id=appt.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"doctor_id": doc.id, "mode": appt.consultation_mode}
    )

    return appt


@router.post("/consultations/{id}/session", response_model=ConsultationSessionResponse)
def start_or_get_consultation_session(
    id: str,
    session_in: Optional[ConsultationSessionCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Opens or retrieves a telemedicine consultation session for an appointment (id can be appointment_id or session_id).
    Consultations are not recorded by default per privacy rules.
    """
    session = db.query(ConsultationSession).filter(
        (ConsultationSession.id == id) | (ConsultationSession.appointment_id == id)
    ).first()

    if not session:
        appt = db.query(Appointment).filter(Appointment.id == id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment or consultation session not found")

        channel = session_in.channel_mode if session_in else appt.consultation_mode
        token = generate_random_token(16)
        session = ConsultationSession(
            appointment_id=appt.id,
            patient_id=appt.patient_id,
            doctor_id=appt.doctor_id,
            channel_mode=channel,
            room_token=token,
            session_url=f"https://telemed.vitalis.health/room/{appt.appointment_number}?token={token}",
            is_recorded=False,
            status="active"
        )
        appt.status = "in_progress"
        db.add(session)
        db.commit()
        db.refresh(session)

    log_audit_event(
        db,
        action="TELEMEDICINE_SESSION_OPENED",
        resource_type="consultation_session",
        resource_id=session.id,
        actor_id=current_user.id,
        patient_id=session.patient_id,
        metadata={"channel_mode": session.channel_mode, "is_recorded": session.is_recorded}
    )

    return session


@router.post("/consultations/{id}/messages", response_model=ConsultationMessageResponse)
def post_consultation_message(
    id: str,
    msg_in: ConsultationMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(ConsultationSession).filter(
        (ConsultationSession.id == id) | (ConsultationSession.appointment_id == id)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Consultation session not found")

    sender_role = "doctor" if current_user.role == UserRole.DOCTOR else "patient"
    msg = ConsultationMessage(
        session_id=session.id,
        sender_id=current_user.id,
        sender_role=sender_role,
        content=msg_in.content,
        attachment_ref=msg_in.attachment_ref
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return msg


@router.post("/consultations/{id}/prescriptions", response_model=ConsultationSessionResponse)
def sign_consultation_prescription(
    id: str,
    sign_in: ConsultationPrescriptionSignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    """
    Architectural rule: Prescriptions come ONLY from a licensed doctor's explicit signed action.
    Consultation records stay in VITALIS.
    """
    session = db.query(ConsultationSession).filter(
        (ConsultationSession.id == id) | (ConsultationSession.appointment_id == id)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Consultation session not found")

    now = get_utc_now()
    session.doctor_recommendations = sign_in.doctor_recommendations
    session.signed_prescription = {
        "medications": sign_in.medications,
        "signed_by": current_user.full_name,
        "signed_at": now.isoformat()
    }
    session.signed_by_doctor_id = current_user.id
    session.signed_at = now
    session.status = "completed"
    session.ended_at = now

    # Store in centralized VITALIS health records
    hr = HealthRecord(
        patient_id=session.patient_id,
        record_type="prescription",
        title=f"Signed Telemedicine Prescription & Plan ({current_user.full_name})",
        summary=sign_in.doctor_recommendations,
        details=session.signed_prescription
    )
    db.add(hr)
    db.commit()
    db.refresh(session)

    log_audit_event(
        db,
        action="TELEMEDICINE_PRESCRIPTION_SIGNED",
        resource_type="consultation_session",
        resource_id=session.id,
        actor_id=current_user.id,
        patient_id=session.patient_id
    )

    return session


# =================================================================================
# 3. HOME VISIT: Request, Emergency Guardrail, Dispatch & Tracking
# =================================================================================

@router.post("/home-visits", response_model=HomeVisitRequestResponse)
def create_home_visit_request(
    visit_in: HomeVisitRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Architectural rule: Emergencies such as active labour, severe bleeding or suspected stroke
    are redirected to emergency transport and an equipped facility, NEVER to a routine home visit.
    """
    patient = db.query(Patient).filter(Patient.id == visit_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    urgency, red_flags, _, guidance = TriageEngine.evaluate_symptoms(
        [{"symptom": visit_in.symptoms_or_reason, "details": ""}]
    )

    req_num = f"HVR-2026-{random.randint(10000, 99999)}"
    is_emergency = urgency == "EMERGENCY_RED"

    if is_emergency:
        visit_req = HomeVisitRequest(
            request_number=req_num,
            patient_id=patient.id,
            professional_type_needed=visit_in.professional_type_needed,
            symptoms_or_reason=visit_in.symptoms_or_reason,
            address=visit_in.address,
            latitude=visit_in.latitude,
            longitude=visit_in.longitude,
            urgency_flag=True,
            redirected_emergency_reason=(
                f"SAFETY REDIRECT: Critical emergency symptoms detected ({', '.join(red_flags)}). "
                f"Home visits are not safe for emergencies. Redirected to Emergency Coordination and Transport."
            ),
            status=HomeVisitStatus.REDIRECTED_TO_EMERGENCY
        )
        db.add(visit_req)
        db.commit()
        db.refresh(visit_req)

        log_audit_event(
            db,
            action="HOME_VISIT_REDIRECTED_TO_EMERGENCY",
            resource_type="home_visit_request",
            resource_id=visit_req.id,
            actor_id=current_user.id,
            patient_id=patient.id,
            metadata={"red_flags": red_flags}
        )
        return visit_req

    # Normal flow: match an available verified home-visit professional
    visit_req = HomeVisitRequest(
        request_number=req_num,
        patient_id=patient.id,
        professional_type_needed=visit_in.professional_type_needed,
        symptoms_or_reason=visit_in.symptoms_or_reason,
        address=visit_in.address,
        latitude=visit_in.latitude,
        longitude=visit_in.longitude,
        urgency_flag=False,
        status=HomeVisitStatus.CONFIRMED
    )
    db.add(visit_req)
    db.commit()
    db.refresh(visit_req)

    provider_doc = db.query(DoctorProfile).filter(
        DoctorProfile.verification_status == "verified",
        DoctorProfile.offers_home_visits == True
    ).first()

    provider_user_id = provider_doc.user_id if provider_doc else current_user.id
    provider_name = provider_doc.full_name if provider_doc else "Dr. Tunde Bakare (Verified Home-Visit Physician)"
    provider_license = provider_doc.license_number if provider_doc else "MDCN-HV-2026-441"

    assignment = VisitAssignment(
        visit_request_id=visit_req.id,
        provider_user_id=provider_user_id,
        provider_name=provider_name,
        provider_role=visit_in.professional_type_needed,
        provider_license=provider_license,
        estimated_arrival_minutes=25,
        service_fee_ngn=15000.0,
        tracking_status="provider_confirmed"
    )
    db.add(assignment)
    db.commit()
    db.refresh(visit_req)

    log_audit_event(
        db,
        action="HOME_VISIT_REQUESTED_AND_CONFIRMED",
        resource_type="home_visit_request",
        resource_id=visit_req.id,
        actor_id=current_user.id,
        patient_id=patient.id
    )

    return visit_req


@router.get("/home-visits/{id}", response_model=HomeVisitRequestResponse)
def get_home_visit_request(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit_req = db.query(HomeVisitRequest).filter(HomeVisitRequest.id == id).first()
    if not visit_req:
        raise HTTPException(status_code=404, detail="Home visit request not found")
    return visit_req


@router.patch("/home-visits/{id}/status", response_model=HomeVisitRequestResponse)
def update_home_visit_status(
    id: str,
    status_in: HomeVisitStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    visit_req = db.query(HomeVisitRequest).filter(HomeVisitRequest.id == id).first()
    if not visit_req:
        raise HTTPException(status_code=404, detail="Home visit request not found")

    visit_req.status = status_in.status
    if visit_req.assignment:
        if status_in.tracking_status:
            visit_req.assignment.tracking_status = status_in.tracking_status
        if status_in.estimated_arrival_minutes is not None:
            visit_req.assignment.estimated_arrival_minutes = status_in.estimated_arrival_minutes
        if status_in.visit_notes:
            visit_req.assignment.visit_notes = status_in.visit_notes
        if status_in.status == HomeVisitStatus.COMPLETED:
            visit_req.assignment.completed_at = get_utc_now()
            visit_req.assignment.tracking_status = "completed"
            # Keep record in VITALIS
            db.add(HealthRecord(
                patient_id=visit_req.patient_id,
                record_type="home_visit_note",
                title=f"Home Visit Consultation ({visit_req.assignment.provider_name})",
                summary=status_in.visit_notes or "Home visit completed.",
                details={"request_number": visit_req.request_number}
            ))

    db.commit()
    db.refresh(visit_req)

    log_audit_event(
        db,
        action=f"HOME_VISIT_STATUS_{status_in.status.value.upper()}",
        resource_type="home_visit_request",
        resource_id=visit_req.id,
        actor_id=current_user.id,
        patient_id=visit_req.patient_id
    )

    return visit_req


# =================================================================================
# 4. FIND A HOSPITAL: Capability Registry, Availability & Intelligent Search
# =================================================================================

CONDITION_CAPABILITY_MAP = {
    "obstetric": ["Emergency Obstetrics", "Obstetrician/Gynaecologist", "Operating Theatre", "Blood Transfusion"],
    "pregnancy": ["Emergency Obstetrics", "Obstetrician/Gynaecologist", "Operating Theatre"],
    "labour": ["Emergency Obstetrics", "Obstetrician/Gynaecologist", "Operating Theatre", "Blood Transfusion"],
    "c-section": ["Emergency Obstetrics", "Operating Theatre", "Blood Transfusion"],
    "cardiac": ["Cardiology", "Cardiologist", "Defibrillator", "ECG"],
    "heart": ["Cardiology", "Cardiologist", "ECG"],
    "chest pain": ["Cardiology", "Emergency Resuscitation", "ECG"],
    "stroke": ["Neurology", "CT Scanner", "ICU"],
    "trauma": ["Trauma Resuscitation", "Operating Theatre", "Blood Transfusion"],
    "bleeding": ["Emergency Resuscitation", "Blood Transfusion", "Operating Theatre"],
    "pediatric": ["Pediatrics", "Pediatrician"],
    "neonatal": ["NICU", "Pediatrician"],
}


def _resolve_required_capabilities(
    condition: Optional[str],
    specialization: Optional[str],
    equipment: Optional[str],
    service: Optional[str],
    explicit_caps: Optional[List[str]] = None
) -> List[str]:
    caps: List[str] = list(explicit_caps or [])
    if condition:
        cond_low = condition.lower()
        matched_preset = False
        for key, preset_caps in CONDITION_CAPABILITY_MAP.items():
            if key in cond_low:
                for c in preset_caps:
                    if c not in caps:
                        caps.append(c)
                matched_preset = True
        if not matched_preset:
            caps.append(condition)
    if specialization and specialization not in caps:
        caps.append(specialization)
    if equipment and equipment not in caps:
        caps.append(equipment)
    if service and service not in caps:
        caps.append(service)
    return caps


@router.get("/hospitals/search", response_model=List[HospitalCapabilitySearchResult])
def search_hospitals_by_capability(
    condition: Optional[str] = Query(None, description="Condition, symptom or emergency type (e.g., Obstetric Emergency)"),
    specialization: Optional[str] = Query(None, description="Required specialist (e.g., Obstetrician/Gynaecologist)"),
    equipment: Optional[str] = Query(None, description="Required equipment/facility (e.g., Operating Theatre, Blood Transfusion, NICU)"),
    service: Optional[str] = Query(None, description="Required clinical service"),
    latitude: float = Query(7.1500, description="Patient latitude"),
    longitude: float = Query(3.3500, description="Patient longitude"),
    is_emergency: bool = Query(False, description="Apply strict emergency acceptance and freshness filters"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Intelligent Hospital Search (VITALIS CareConnect & ROUTE):
    Applies hard capability filters BEFORE distance ranking.
    Unknown or stale availability is never treated as accepting in emergencies.
    """
    required_caps = _resolve_required_capabilities(condition, specialization, equipment, service)
    facilities = db.query(Facility).all()

    results: List[HospitalCapabilitySearchResult] = []
    for fac in facilities:
        cap_rec = db.query(HospitalCapability).filter(HospitalCapability.facility_id == fac.id).first()
        avail_rec = db.query(HospitalAvailability).filter(HospitalAvailability.facility_id == fac.id).first()

        cap_dict = {
            "services": cap_rec.services if cap_rec else [],
            "specialists": cap_rec.specialists if cap_rec else [],
            "equipment": cap_rec.equipment if cap_rec else [],
            "has_operating_theatre": cap_rec.has_operating_theatre if cap_rec else False,
            "has_blood_bank": cap_rec.has_blood_bank if cap_rec else False,
            "has_icu": cap_rec.has_icu if cap_rec else False,
            "has_nicu": cap_rec.has_nicu if cap_rec else False,
            "last_confirmed_at": cap_rec.last_confirmed_at if cap_rec else None,
            "reported_by": cap_rec.reported_by if cap_rec else "Unreported"
        } if cap_rec else None

        avail_dict = {
            "emergency_acceptance_status": avail_rec.emergency_acceptance_status if avail_rec else "unknown",
            "expected_wait_minutes": avail_rec.expected_wait_minutes if avail_rec else None,
            "last_confirmed_at": avail_rec.last_confirmed_at if avail_rec else None,
            "reported_by": avail_rec.reported_by if avail_rec else None
        } if avail_rec else None

        fac_info = {
            "id": fac.id,
            "latitude": fac.latitude,
            "longitude": fac.longitude,
            "emergency_available": fac.emergency_available,
            "verification_status": fac.verification_status
        }

        match = FacilityMatcher.compute_capability_suitability(
            facility_info=fac_info,
            required_capabilities=required_caps,
            capability_record=cap_dict,
            availability_record=avail_dict,
            user_lat=latitude,
            user_lon=longitude,
            is_emergency=is_emergency
        )
        if match:
            results.append(HospitalCapabilitySearchResult(
                facility=FacilityResponse.model_validate(fac),
                suitability_score=match["suitability_score"],
                distance_km=match["distance_km"],
                matched_capabilities=match["matched_capabilities"],
                acceptance_status=match["acceptance_status"],
                freshness_label=match["freshness_label"],
                last_confirmed_at=match["last_confirmed_at"],
                reported_by=match["reported_by"],
                expected_wait_minutes=match["expected_wait_minutes"],
                score_breakdown=match["score_breakdown"],
                why_this_facility=match["why_this_facility"]
            ))

    results.sort(key=lambda r: r.suitability_score, reverse=True)
    return results


@router.put("/hospitals/{id}/capabilities")
def update_hospital_capabilities(
    id: str,
    cap_in: HospitalCapabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN, UserRole.DOCTOR]))
):
    facility = db.query(Facility).filter(Facility.id == id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    now = get_utc_now()
    reporter = cap_in.reported_by or current_user.full_name

    cap = db.query(HospitalCapability).filter(HospitalCapability.facility_id == id).first()
    if not cap:
        cap = HospitalCapability(
            facility_id=id,
            services=cap_in.services,
            specialists=cap_in.specialists,
            equipment=cap_in.equipment,
            has_operating_theatre=cap_in.has_operating_theatre,
            has_blood_bank=cap_in.has_blood_bank,
            has_icu=cap_in.has_icu,
            has_nicu=cap_in.has_nicu,
            last_confirmed_at=now,
            reported_by=reporter
        )
        db.add(cap)
    else:
        cap.services = cap_in.services
        cap.specialists = cap_in.specialists
        cap.equipment = cap_in.equipment
        cap.has_operating_theatre = cap_in.has_operating_theatre
        cap.has_blood_bank = cap_in.has_blood_bank
        cap.has_icu = cap_in.has_icu
        cap.has_nicu = cap_in.has_nicu
        cap.last_confirmed_at = now
        cap.reported_by = reporter

    db.commit()
    db.refresh(cap)

    log_audit_event(
        db,
        action="HOSPITAL_CAPABILITIES_UPDATED",
        resource_type="hospital_capability",
        resource_id=cap.id,
        actor_id=current_user.id,
        metadata={"facility_id": id, "reported_by": reporter}
    )

    return {
        "status": "success",
        "facility_id": id,
        "last_confirmed_at": cap.last_confirmed_at,
        "reported_by": cap.reported_by,
        "capabilities": {
            "services": cap.services,
            "specialists": cap.specialists,
            "equipment": cap.equipment,
            "has_operating_theatre": cap.has_operating_theatre,
            "has_blood_bank": cap.has_blood_bank,
            "has_icu": cap.has_icu,
            "has_nicu": cap.has_nicu
        }
    }


@router.put("/hospitals/{id}/availability")
def update_hospital_availability(
    id: str,
    avail_in: HospitalAvailabilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN, UserRole.DOCTOR]))
):
    facility = db.query(Facility).filter(Facility.id == id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    now = get_utc_now()
    reporter = avail_in.reported_by or current_user.full_name

    avail = db.query(HospitalAvailability).filter(HospitalAvailability.facility_id == id).first()
    if not avail:
        avail = HospitalAvailability(
            facility_id=id,
            emergency_acceptance_status=avail_in.emergency_acceptance_status,
            available_general_beds=avail_in.available_general_beds,
            available_icu_beds=avail_in.available_icu_beds,
            available_maternity_beds=avail_in.available_maternity_beds,
            specialists_on_duty=avail_in.specialists_on_duty,
            expected_wait_minutes=avail_in.expected_wait_minutes,
            notes=avail_in.notes,
            last_confirmed_at=now,
            reported_by=reporter
        )
        db.add(avail)
    else:
        avail.emergency_acceptance_status = avail_in.emergency_acceptance_status
        avail.available_general_beds = avail_in.available_general_beds
        avail.available_icu_beds = avail_in.available_icu_beds
        avail.available_maternity_beds = avail_in.available_maternity_beds
        avail.specialists_on_duty = avail_in.specialists_on_duty
        avail.expected_wait_minutes = avail_in.expected_wait_minutes
        avail.notes = avail_in.notes
        avail.last_confirmed_at = now
        avail.reported_by = reporter

    db.commit()
    db.refresh(avail)

    log_audit_event(
        db,
        action="HOSPITAL_AVAILABILITY_UPDATED",
        resource_type="hospital_availability",
        resource_id=avail.id,
        actor_id=current_user.id,
        metadata={"facility_id": id, "emergency_acceptance_status": avail.emergency_acceptance_status}
    )

    return {
        "status": "success",
        "facility_id": id,
        "emergency_acceptance_status": avail.emergency_acceptance_status,
        "available_general_beds": avail.available_general_beds,
        "available_icu_beds": avail.available_icu_beds,
        "available_maternity_beds": avail.available_maternity_beds,
        "last_confirmed_at": avail.last_confirmed_at,
        "reported_by": avail.reported_by
    }


# =================================================================================
# 5. EMERGENCY ASSISTANCE: Assessment, Capability Matching, Confirmation & Transport
# =================================================================================

@router.post("/emergency/requests", response_model=EmergencyRequestResponse)
def initiate_emergency_request(
    em_in: EmergencyRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Emergency Coordination Workflow:
    1. Deterministic red-flag rules run first and never wait on AI.
    2. Matches against verified hospital capabilities and live emergency acceptance status.
    3. Selects the top capable candidate hospital and transitions to awaiting_hospital_confirmation.
    """
    patient = db.query(Patient).filter(Patient.id == em_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    _, red_flags, _, _ = TriageEngine.evaluate_symptoms([
        {"symptom": f"{em_in.emergency_type} {em_in.presenting_complaint}", "details": ""}
    ])
    if not red_flags:
        red_flags = [f"Reported Emergency: {em_in.emergency_type}"]

    required_caps = _resolve_required_capabilities(
        condition=em_in.emergency_type,
        specialization=None,
        equipment=None,
        service=None,
        explicit_caps=em_in.required_capabilities
    )

    matched_hospitals = search_hospitals_by_capability(
        condition=em_in.emergency_type,
        specialization=None,
        equipment=None,
        service=None,
        latitude=em_in.patient_latitude,
        longitude=em_in.patient_longitude,
        is_emergency=True,
        db=db,
        current_user=current_user
    )

    candidates = [
        {
            "facility_id": m.facility.id,
            "facility_name": m.facility.name,
            "suitability_score": m.suitability_score,
            "distance_km": m.distance_km,
            "matched_capabilities": m.matched_capabilities,
            "acceptance_status": m.acceptance_status,
            "confirmation_state": "pending"
        }
        for m in matched_hospitals
    ]

    first_candidate_id = candidates[0]["facility_id"] if candidates else None
    initial_status = (
        EmergencyRequestStatus.AWAITING_HOSPITAL_CONFIRMATION
        if first_candidate_id else EmergencyRequestStatus.MATCHING
    )

    em_num = f"EMG-2026-{random.randint(10000, 99999)}"
    em_req = EmergencyRequest(
        emergency_number=em_num,
        patient_id=patient.id,
        initiated_by_role=em_in.initiated_by_role,
        emergency_type=em_in.emergency_type,
        presenting_complaint=em_in.presenting_complaint,
        required_capabilities=required_caps,
        patient_latitude=em_in.patient_latitude,
        patient_longitude=em_in.patient_longitude,
        patient_address=em_in.patient_address,
        red_flags_detected=red_flags,
        candidate_facilities=candidates,
        current_candidate_facility_id=first_candidate_id,
        status=initial_status
    )
    db.add(em_req)
    db.commit()
    db.refresh(em_req)

    db.add(EmergencyEvent(
        emergency_request_id=em_req.id,
        event_type="INITIATED_AND_ASSESSED",
        actor_id=current_user.id,
        details=f"Emergency assessed via deterministic rules ({', '.join(red_flags)}). Required capabilities: {', '.join(required_caps)}."
    ))

    if first_candidate_id:
        db.add(EmergencyEvent(
            emergency_request_id=em_req.id,
            event_type="AWAITING_HOSPITAL_CONFIRMATION",
            facility_id=first_candidate_id,
            actor_id=current_user.id,
            details=f"Contacted top-matched capable facility ({candidates[0]['facility_name']}, Score S={candidates[0]['suitability_score']}) for explicit acceptance confirmation."
        ))

    db.commit()
    db.refresh(em_req)

    log_audit_event(
        db,
        action="EMERGENCY_REQUEST_INITIATED",
        resource_type="emergency_request",
        resource_id=em_req.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"emergency_type": em_in.emergency_type, "top_candidate": first_candidate_id}
    )

    return em_req


@router.get("/emergency/requests/{id}", response_model=EmergencyRequestResponse)
def get_emergency_request(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    em_req = db.query(EmergencyRequest).filter(EmergencyRequest.id == id).first()
    if not em_req:
        raise HTTPException(status_code=404, detail="Emergency request not found")
    return em_req


@router.post("/emergency/requests/{id}/confirmations", response_model=EmergencyRequestResponse)
def respond_to_emergency_confirmation(
    id: str,
    confirm_in: EmergencyHospitalConfirmation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Explicit hospital confirmation step:
    - If accepted=True: marks request confirmed, creates the linked Referral in the receiving hospital's queue,
      and dispatches coordinated emergency transport.
    - If accepted=False (declined): records the decline and automatically routes to the next capable candidate hospital.
    """
    em_req = db.query(EmergencyRequest).filter(EmergencyRequest.id == id).first()
    if not em_req:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    facility = db.query(Facility).filter(Facility.id == confirm_in.facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    candidates = list(em_req.candidate_facilities or [])

    if confirm_in.accepted:
        for c in candidates:
            if c.get("facility_id") == facility.id:
                c["confirmation_state"] = "accepted"
        em_req.candidate_facilities = candidates
        em_req.confirmed_facility_id = facility.id
        em_req.status = EmergencyRequestStatus.TRANSPORT_COORDINATED

        # Create the linked Referral in the receiving hospital's VITALIS queue
        ref_num = f"REF-EMG-{random.randint(10000, 99999)}"
        linked_ref = Referral(
            referral_number=ref_num,
            patient_id=em_req.patient_id,
            source_facility_id=facility.id,
            destination_facility_id=facility.id,
            urgency="emergency",
            clinical_reason=f"[CARECONNECT EMERGENCY] {em_req.emergency_type}: {em_req.presenting_complaint}",
            service_needed=", ".join(em_req.required_capabilities) or "Emergency Resuscitation",
            status=ReferralStatus.ACCEPTED,
            facility_response_reason=confirm_in.reason_or_notes or "Explicitly confirmed via CareConnect Emergency Coordination",
            created_by_id=current_user.id,
            responded_at=get_utc_now()
        )
        db.add(linked_ref)
        db.commit()
        db.refresh(linked_ref)

        em_req.linked_referral_id = linked_ref.id

        db.add(EmergencyEvent(
            emergency_request_id=em_req.id,
            event_type="HOSPITAL_CONFIRMED",
            facility_id=facility.id,
            actor_id=current_user.id,
            details=f"{facility.name} explicitly CONFIRMED capacity to receive patient. Linked referral {ref_num} created."
        ))

        if not em_req.transport:
            transport = TransportAssignment(
                emergency_request_id=em_req.id,
                provider_name="Ogun State Emergency Medical Services (OGSEMS)",
                vehicle_type="Advanced Life Support (ALS) Ambulance",
                vehicle_callsign=f"AMB-ABK-0{random.randint(1, 9)}",
                dispatch_status="dispatched",
                estimated_pickup_minutes=7,
                estimated_hospital_arrival_minutes=16
            )
            db.add(transport)
            db.add(EmergencyEvent(
                emergency_request_id=em_req.id,
                event_type="TRANSPORT_COORDINATED",
                facility_id=facility.id,
                actor_id=current_user.id,
                details=f"Ambulance {transport.vehicle_callsign} dispatched; pre-arrival notice sent to {facility.name}."
            ))

    else:
        # Facility declined -> advance to next candidate
        next_candidate = None
        for c in candidates:
            if c.get("facility_id") == facility.id:
                c["confirmation_state"] = "declined"
            elif c.get("confirmation_state") == "pending" and next_candidate is None:
                next_candidate = c

        em_req.candidate_facilities = candidates
        db.add(EmergencyEvent(
            emergency_request_id=em_req.id,
            event_type="HOSPITAL_DECLINED",
            facility_id=facility.id,
            actor_id=current_user.id,
            details=f"{facility.name} declined emergency intake ({confirm_in.reason_or_notes or 'No capacity'}). Matching next capable hospital."
        ))

        if next_candidate:
            em_req.current_candidate_facility_id = next_candidate["facility_id"]
            em_req.status = EmergencyRequestStatus.AWAITING_HOSPITAL_CONFIRMATION
            db.add(EmergencyEvent(
                emergency_request_id=em_req.id,
                event_type="AWAITING_HOSPITAL_CONFIRMATION",
                facility_id=next_candidate["facility_id"],
                actor_id=current_user.id,
                details=f"Automatically routed confirmation request to next candidate: {next_candidate['facility_name']}."
            ))
        else:
            em_req.current_candidate_facility_id = None
            em_req.status = EmergencyRequestStatus.MATCHING

    db.commit()
    db.refresh(em_req)

    log_audit_event(
        db,
        action="EMERGENCY_HOSPITAL_CONFIRMATION_RESPONSE",
        resource_type="emergency_request",
        resource_id=em_req.id,
        actor_id=current_user.id,
        patient_id=em_req.patient_id,
        metadata={"facility_id": facility.id, "accepted": confirm_in.accepted}
    )

    return em_req


@router.patch("/emergency/requests/{id}/status", response_model=EmergencyRequestResponse)
def update_emergency_request_status(
    id: str,
    status_in: EmergencyStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    em_req = db.query(EmergencyRequest).filter(EmergencyRequest.id == id).first()
    if not em_req:
        raise HTTPException(status_code=404, detail="Emergency request not found")

    em_req.status = status_in.status
    if status_in.status == EmergencyRequestStatus.CANCELLED:
        em_req.cancellation_reason = status_in.details or "Cancelled by user"

    if em_req.transport:
        if status_in.status == EmergencyRequestStatus.EN_ROUTE:
            em_req.transport.dispatch_status = "en_route_to_hospital"
        elif status_in.status in [EmergencyRequestStatus.ARRIVED, EmergencyRequestStatus.HANDED_OVER]:
            em_req.transport.dispatch_status = "arrived"

    db.add(EmergencyEvent(
        emergency_request_id=em_req.id,
        event_type=f"STATUS_{status_in.status.value.upper()}",
        facility_id=em_req.confirmed_facility_id,
        actor_id=current_user.id,
        details=status_in.details or f"Emergency status transitioned to {status_in.status.value}."
    ))

    db.commit()
    db.refresh(em_req)

    log_audit_event(
        db,
        action=f"EMERGENCY_STATUS_{status_in.status.value.upper()}",
        resource_type="emergency_request",
        resource_id=em_req.id,
        actor_id=current_user.id,
        patient_id=em_req.patient_id
    )

    return em_req


# =================================================================================
# 6. ADDITIONAL ARCHITECTURE CONTRACT ROUTES (Clinical AI Review, Records, Analytics)
# =================================================================================

@router.patch("/ai/analyses/{id}/review", response_model=ClinicalAIAnalysisResponse)
def review_clinical_ai_analysis(
    id: str,
    review_in: InsightReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    """
    Doctor review action on a ClinicalAIAnalysis artifact (edit, accept, or reject).
    """
    analysis = db.query(ClinicalAIAnalysis).filter(ClinicalAIAnalysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Clinical AI analysis artifact not found")

    analysis.review_status = review_in.action
    analysis.reviewed_by_id = current_user.id
    analysis.reviewed_at = get_utc_now()
    if review_in.edited_content:
        analysis.clinician_edits = review_in.edited_content
    elif review_in.rationale:
        analysis.clinician_edits = review_in.rationale

    db.commit()
    db.refresh(analysis)

    log_audit_event(
        db,
        action=f"CLINICAL_AI_ANALYSIS_{review_in.action.value.upper()}",
        resource_type="clinical_ai_analysis",
        resource_id=analysis.id,
        actor_id=current_user.id,
        patient_id=analysis.patient_id,
        encounter_id=analysis.encounter_id
    )

    return analysis


@router.get("/users/me")
def get_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }


@router.get("/records/me")
def get_my_health_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        patient = db.query(Patient).first()
    if not patient:
        return {"patient_id": None, "records": [], "documents": []}

    records = db.query(HealthRecord).filter(HealthRecord.patient_id == patient.id).order_by(HealthRecord.created_at.desc()).all()
    docs = db.query(PatientDocument).filter(PatientDocument.patient_id == patient.id).order_by(PatientDocument.created_at.desc()).all()

    return {
        "patient_id": patient.id,
        "patient_number": patient.patient_number,
        "allergies": patient.allergies,
        "chronic_conditions": patient.chronic_conditions,
        "current_medications": patient.current_medications,
        "health_records": records,
        "uploaded_documents": docs
    }


@router.post("/consents")
def create_patient_consent(
    consent_in: ConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == consent_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    if current_user.role == UserRole.PATIENT and patient.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot create consent for another patient")

    now = get_utc_now()
    exp_time = now + timedelta(minutes=consent_in.duration_minutes)
    consent = Consent(
        patient_id=patient.id,
        grantee_facility_id=consent_in.grantee_facility_id,
        scope=consent_in.scope,
        purpose=consent_in.purpose,
        expires_at=exp_time
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    log_audit_event(
        db,
        action="CONSENT_CREATED",
        resource_type="consent",
        resource_id=consent.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"scope": consent_in.scope}
    )
    return {
        "id": consent.id,
        "patient_id": consent.patient_id,
        "grantee_facility_id": consent.grantee_facility_id,
        "scope": consent.scope,
        "purpose": consent.purpose,
        "expires_at": consent.expires_at,
        "created_at": consent.created_at
    }


@router.delete("/consents/{consent_id}")
def delete_patient_consent(
    consent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.api.endpoints.connect import revoke_consent
    return revoke_consent(consent_id=consent_id, db=db, current_user=current_user)


@router.post("/qr/grants", response_model=QRGrantResponse)
def issue_qr_grant(
    consent_in: ConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.api.endpoints.connect import create_qr_access_grant
    return create_qr_access_grant(consent_in=consent_in, db=db, current_user=current_user)


@router.post("/qr/redeem")
def redeem_qr_token(
    redeem_in: QRRedeemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR,
        UserRole.LAB_TECH, UserRole.RADIOLOGIST, UserRole.FACILITY_ADMIN
    ]))
):
    from app.api.endpoints.connect import redeem_qr_grant
    return redeem_qr_grant(redeem_in=redeem_in, db=db, current_user=current_user)


@router.get("/hospital/referrals", response_model=List[ReferralResponse])
def get_hospital_referrals(
    facility_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Referral)
    if facility_id:
        query = query.filter(Referral.destination_facility_id == facility_id)
    elif current_user.staff_profile:
        query = query.filter(Referral.destination_facility_id == current_user.staff_profile.facility_id)
    return query.order_by(Referral.created_at.desc()).all()


@router.patch("/hospital/referrals/{id}", response_model=ReferralResponse)
def update_hospital_referral(
    id: str,
    status_update: ReferralStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    referral = db.query(Referral).filter(Referral.id == id).first()
    if not referral:
        raise HTTPException(status_code=404, detail="Referral not found")

    referral.status = status_update.status
    referral.facility_response_reason = status_update.facility_response_reason
    referral.responded_at = get_utc_now()
    db.commit()
    db.refresh(referral)

    log_audit_event(
        db,
        action=f"HOSPITAL_REFERRAL_{status_update.status.value.upper()}",
        resource_type="referral",
        resource_id=referral.id,
        actor_id=current_user.id,
        patient_id=referral.patient_id
    )
    return referral


@router.get("/analytics/overview")
def get_root_analytics_overview(
    facility_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    enc_q = db.query(Encounter)
    if facility_id:
        enc_q = enc_q.filter(Encounter.facility_id == facility_id)

    return {
        "total_patients": db.query(Patient).count(),
        "total_facilities": db.query(Facility).count(),
        "total_verified_doctors": db.query(DoctorProfile).filter(DoctorProfile.verification_status == "verified").count(),
        "total_emergency_requests": db.query(EmergencyRequest).count(),
        "total_home_visits": db.query(HomeVisitRequest).count(),
        "encounters_overview": {
            "total": enc_q.count(),
            "awaiting_nursing": enc_q.filter(Encounter.status == EncounterStatus.AWAITING_NURSING).count(),
            "awaiting_doctor": enc_q.filter(Encounter.status == EncounterStatus.AWAITING_DOCTOR).count(),
            "awaiting_investigation": enc_q.filter(Encounter.status == EncounterStatus.AWAITING_INVESTIGATION).count(),
            "results_ready": enc_q.filter(Encounter.status == EncounterStatus.RESULTS_READY).count(),
            "completed": enc_q.filter(Encounter.status == EncounterStatus.COMPLETED).count()
        }
    }

