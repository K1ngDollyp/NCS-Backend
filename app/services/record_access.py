"""
VITALIS network record access policy.

A facility can always see the encounters it created itself. Records held at
other facilities are only disclosed while the patient has an active,
unrevoked consent for the requesting facility (granted via the one-time code flow).
"""
from datetime import timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import (
    Consent, Patient, Staff, User, UserRole, Encounter, get_utc_now
)

NETWORK_ACCESS_PURPOSE = "Cross-facility network record access"


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_staff_facility_id(db: Session, user: User) -> Optional[str]:
    staff = db.query(Staff).filter(Staff.user_id == user.id).first()
    return staff.facility_id if staff else None


def get_active_network_consent(db: Session, patient_id: str, facility_id: Optional[str]) -> Optional[Consent]:
    if not facility_id:
        return None
    now = get_utc_now()
    consents = db.query(Consent).filter(
        Consent.patient_id == patient_id,
        Consent.grantee_facility_id == facility_id,
        Consent.revoked_at.is_(None),
    ).order_by(Consent.expires_at.desc()).all()
    for c in consents:
        if _aware(c.expires_at) > now:
            return c
    return None


def resolve_access(db: Session, user: User, patient: Patient) -> Dict[str, Any]:
    """
    Returns the access context for a user viewing a patient's network record:
      level: "self" | "full" | "facility_only" | "none"
    """
    if user.role == UserRole.PATIENT:
        if patient.user_id == user.id:
            return {"level": "self", "facility_id": None, "consent": None}
        return {"level": "none", "facility_id": None, "consent": None}

    if user.role == UserRole.NETWORK_ADMIN:
        return {"level": "full", "facility_id": None, "consent": None}

    facility_id = get_staff_facility_id(db, user)
    consent = get_active_network_consent(db, patient.id, facility_id)
    if consent:
        return {"level": "full", "facility_id": facility_id, "consent": consent}
    return {"level": "facility_only", "facility_id": facility_id, "consent": None}


def visible_encounters(patient: Patient, access: Dict[str, Any]) -> List[Encounter]:
    encounters = sorted(patient.encounters, key=lambda e: _aware(e.opened_at), reverse=True)
    if access["level"] in ("self", "full"):
        return encounters
    if access["level"] == "facility_only":
        return [e for e in encounters if e.facility_id == access["facility_id"]]
    return []
