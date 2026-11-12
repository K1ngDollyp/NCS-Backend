from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import TriageSession, Patient, User
from app.schemas.schemas import TriageSessionCreate, TriageSessionResponse
from app.engines.triage.rules import TriageEngine
from app.services.audit import log_audit_event

router = APIRouter(prefix="/triage", tags=["VITALIS AI Triage & Intake"])

@router.post("/sessions", response_model=TriageSessionResponse)
def start_triage_session(
    triage_in: TriageSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == triage_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    symptoms_data = [s.model_dump() for s in triage_in.symptoms]
    urgency, red_flags, service, summary = TriageEngine.evaluate_symptoms(symptoms_data)

    session = TriageSession(
        patient_id=patient.id,
        symptoms_structured=symptoms_data,
        urgency_level=urgency,
        matched_red_flags=red_flags,
        recommended_service=service,
        recommendation_summary=summary
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    log_audit_event(
        db,
        action="TRIAGE_SESSION_EVALUATED",
        resource_type="triage_session",
        resource_id=session.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"urgency_level": urgency, "red_flags_count": len(red_flags)}
    )

    return session

@router.post("/sessions/{id}/responses", response_model=TriageSessionResponse)
def submit_triage_session_responses(
    id: str,
    triage_in: TriageSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Append follow-up symptom responses and re-evaluate deterministic red-flag triage rules."""
    session = db.query(TriageSession).filter(TriageSession.id == id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Triage session not found")

    existing = list(session.symptoms_structured or [])
    new_symptoms = [s.model_dump() for s in triage_in.symptoms]
    combined = existing + new_symptoms

    urgency, red_flags, service, summary = TriageEngine.evaluate_symptoms(combined)
    session.symptoms_structured = combined
    session.urgency_level = urgency
    session.matched_red_flags = red_flags
    session.recommended_service = service
    session.recommendation_summary = summary

    db.commit()
    db.refresh(session)

    log_audit_event(
        db,
        action="TRIAGE_SESSION_UPDATED",
        resource_type="triage_session",
        resource_id=session.id,
        actor_id=current_user.id,
        patient_id=session.patient_id,
        metadata={"urgency_level": urgency}
    )

    return session

@router.get("/patient/{patient_id}", response_model=List[TriageSessionResponse])
def get_patient_triage_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(TriageSession).filter(
        TriageSession.patient_id == patient_id
    ).order_by(TriageSession.created_at.desc()).all()

