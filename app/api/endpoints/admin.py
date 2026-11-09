from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    AuditEvent, Encounter, Patient, Facility, User, UserRole,
    EncounterStatus, OrderStatus
)

router = APIRouter(prefix="/admin", tags=["VITALIS ADMIN - System Governance & Audit"])

@router.get("/audit-events")
def list_audit_events(
    patient_id: Optional[str] = None,
    encounter_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN]))
):
    query = db.query(AuditEvent)
    if patient_id:
        query = query.filter(AuditEvent.patient_id == patient_id)
    if encounter_id:
        query = query.filter(AuditEvent.encounter_id == encounter_id)

    events = query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()
    return events

@router.get("/analytics/overview")
def get_analytics_overview(
    facility_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN]))
):
    enc_q = db.query(Encounter)
    if facility_id:
        enc_q = enc_q.filter(Encounter.facility_id == facility_id)

    total_encounters = enc_q.count()
    awaiting_nursing = enc_q.filter(Encounter.status == EncounterStatus.AWAITING_NURSING).count()
    awaiting_doctor = enc_q.filter(Encounter.status == EncounterStatus.AWAITING_DOCTOR).count()
    awaiting_investigation = enc_q.filter(Encounter.status == EncounterStatus.AWAITING_INVESTIGATION).count()
    results_ready = enc_q.filter(Encounter.status == EncounterStatus.RESULTS_READY).count()
    completed = enc_q.filter(Encounter.status == EncounterStatus.COMPLETED).count()

    total_patients = db.query(Patient).count()
    total_facilities = db.query(Facility).count()

    return {
        "total_patients": total_patients,
        "total_facilities": total_facilities,
        "encounters_overview": {
            "total": total_encounters,
            "awaiting_nursing": awaiting_nursing,
            "awaiting_doctor": awaiting_doctor,
            "awaiting_investigation": awaiting_investigation,
            "results_ready": results_ready,
            "completed": completed
        }
    }

