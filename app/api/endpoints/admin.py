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

    from app.models.models import Staff
    actor_ids = {e.actor_id for e in events if e.actor_id}
    patient_ids = {e.patient_id for e in events if e.patient_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    staff = {s.user_id: s for s in db.query(Staff).filter(Staff.user_id.in_(actor_ids)).all()} if actor_ids else {}
    facilities = {f.id: f.name for f in db.query(Facility).all()}
    patients = {p.id: p for p in db.query(Patient).filter(Patient.id.in_(patient_ids)).all()} if patient_ids else {}

    return [
        {
            "id": e.id,
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "actor_id": e.actor_id,
            "patient_id": e.patient_id,
            "encounter_id": e.encounter_id,
            "timestamp": e.timestamp,
            "event_metadata": e.event_metadata,
            "actor_name": users[e.actor_id].full_name if e.actor_id in users else None,
            "actor_role": users[e.actor_id].role.value if e.actor_id in users else None,
            "facility_name": facilities.get(staff[e.actor_id].facility_id) if e.actor_id in staff else None,
            "patient_name": f"{patients[e.patient_id].first_name} {patients[e.patient_id].last_name}" if e.patient_id in patients else None,
            "patient_number": patients[e.patient_id].patient_number if e.patient_id in patients else None,
        }
        for e in events
    ]

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



@router.post("/demo/reset")
def reset_demo_data(
    current_user: User = Depends(require_roles([UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN]))
):
    """Wipe and re-seed the synthetic demo dataset (demo mode only). Used between rehearsals on hosted builds."""
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.seed import init_db_and_seed, reset_database
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo reset is disabled outside demo mode")
    reset_database()
    db = SessionLocal()
    try:
        init_db_and_seed(db)
    finally:
        db.close()
    return {"status": "success", "message": "Demo data reset. Please sign in again."}
