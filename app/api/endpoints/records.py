"""
VITALIS NETWORK RECORD — one patient, one record, across every connected facility.

Flow for a facility seeing a patient for the first time:
  1. GET  /records/lookup?q=VIT-2026-0002            -> minimal identity + "records exist at N facilities"
  2. POST /records/access-requests                   -> 6-digit one-time code sent to the patient
  3. POST /records/access-requests/{id}/verify       -> patient-approved, time-limited consent for this facility
  4. GET  /records/patients/{patient_id}             -> unified longitudinal record
"""
import secrets
from datetime import timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_token
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    AuditEvent, ClinicalInsight, Consent, Facility, Patient, RecordAccessRequest,
    User, UserRole, get_utc_now
)
from app.services.audit import log_audit_event
from app.services.record_access import (
    NETWORK_ACCESS_PURPOSE, get_active_network_consent, get_staff_facility_id,
    resolve_access, visible_encounters, _aware
)
from app.services.record_serializer import (
    _iso, lab_series, mask_phone, patient_age, serialize_encounter,
    serialize_patient, vitals_series
)

router = APIRouter(prefix="/records", tags=["VITALIS NETWORK - Unified Patient Record"])

STAFF_ROLES = [
    UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR, UserRole.LAB_TECH,
    UserRole.RADIOLOGIST, UserRole.FACILITY_ADMIN, UserRole.NETWORK_ADMIN
]


class AccessRequestCreate(BaseModel):
    patient_id: str
    purpose: str = "Clinical consultation & continuity of care"


class AccessVerify(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


def _facility_summary(patient: Patient):
    by_fac = {}
    for e in patient.encounters:
        f = by_fac.setdefault(e.facility_id, {
            "facility_id": e.facility_id,
            "facility_name": e.facility.name if e.facility else "Unknown",
            "visits": 0,
            "last_visit": None,
        })
        f["visits"] += 1
        opened = _iso(e.opened_at)
        if not f["last_visit"] or opened > f["last_visit"]:
            f["last_visit"] = opened
    return sorted(by_fac.values(), key=lambda x: x["last_visit"] or "", reverse=True)


# ----------------- 1. Network lookup by VITALIS ID / phone -----------------
@router.get("/lookup")
def lookup_patient(
    q: str = Query(..., min_length=3, description="VITALIS ID (e.g. VIT-2026-0002) or phone number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    """Returns only the minimum identity needed to confirm the right patient, plus access status."""
    term = q.strip()
    matches = db.query(Patient).filter(
        or_(Patient.patient_number.ilike(term), Patient.phone == term)
    ).limit(5).all()
    if not matches:
        matches = db.query(Patient).filter(
            or_(
                Patient.patient_number.ilike(f"%{term}%"),
                Patient.first_name.ilike(f"%{term}%"),
                Patient.last_name.ilike(f"%{term}%"),
            )
        ).limit(8).all()

    facility_id = get_staff_facility_id(db, current_user)
    results = []
    for p in matches:
        facilities = _facility_summary(p)
        consent = get_active_network_consent(db, p.id, facility_id)
        external = [f for f in facilities if f["facility_id"] != facility_id]
        results.append({
            "patient_id": p.id,
            "patient_number": p.patient_number,
            "full_name": f"{p.first_name} {p.last_name}",
            "gender": p.gender,
            "age": patient_age(p),
            "dob": p.dob,
            "masked_phone": mask_phone(p.phone),
            "network_facilities": len(facilities),
            "network_encounters": sum(f["visits"] for f in facilities),
            "external_facilities": [f["facility_name"] for f in external],
            "external_encounters": sum(f["visits"] for f in external),
            "seen_at_this_facility": any(f["facility_id"] == facility_id for f in facilities),
            "has_full_access": consent is not None or current_user.role == UserRole.NETWORK_ADMIN,
            "access_expires_at": _iso(consent.expires_at) if consent else None,
        })

    log_audit_event(
        db, action="NETWORK_PATIENT_LOOKUP", resource_type="patient",
        actor_id=current_user.id, metadata={"query": term, "results": len(results)}
    )
    return results


# ----------------- 2. Request access (one-time code to patient) -----------------
@router.post("/access-requests")
def request_record_access(
    req: AccessRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    facility_id = get_staff_facility_id(db, current_user)
    if not facility_id:
        raise HTTPException(status_code=403, detail="Only facility staff can request network record access")
    facility = db.query(Facility).filter(Facility.id == facility_id).first()

    # Supersede older pending requests from this facility
    now = get_utc_now()
    for old in db.query(RecordAccessRequest).filter(
        RecordAccessRequest.patient_id == patient.id,
        RecordAccessRequest.facility_id == facility_id,
        RecordAccessRequest.status == "pending",
    ).all():
        old.status = "cancelled"

    code = f"{secrets.randbelow(1_000_000):06d}"
    access_req = RecordAccessRequest(
        patient_id=patient.id,
        facility_id=facility_id,
        requested_by_id=current_user.id,
        purpose=req.purpose,
        otp_hash=hash_token(code),
        demo_code=code if settings.DEMO_MODE else None,
        status="pending",
        expires_at=now + timedelta(minutes=settings.ACCESS_OTP_TTL_MINUTES),
    )
    db.add(access_req)
    db.commit()
    db.refresh(access_req)

    log_audit_event(
        db, action="NETWORK_ACCESS_REQUESTED", resource_type="record_access_request",
        resource_id=access_req.id, actor_id=current_user.id, patient_id=patient.id,
        metadata={"facility": facility.name if facility else facility_id, "purpose": req.purpose}
    )

    return {
        "request_id": access_req.id,
        "status": access_req.status,
        "expires_at": _iso(access_req.expires_at),
        "delivery": {
            "channel": "SMS + VITALIS app notification",
            "masked_phone": mask_phone(patient.phone),
        },
        "requesting_facility": facility.name if facility else None,
        # Exposed only in demo mode so the presenter can show the simulated SMS
        "demo_code": code if settings.DEMO_MODE else None,
    }


# ----------------- 3. Verify one-time code -> consent -----------------
@router.post("/access-requests/{request_id}/verify")
def verify_record_access(
    request_id: str,
    body: AccessVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    access_req = db.query(RecordAccessRequest).filter(RecordAccessRequest.id == request_id).first()
    if not access_req:
        raise HTTPException(status_code=404, detail="Access request not found")
    if access_req.facility_id != get_staff_facility_id(db, current_user):
        raise HTTPException(status_code=403, detail="This request belongs to another facility")

    now = get_utc_now()
    if access_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is {access_req.status}. Send a new code.")
    if _aware(access_req.expires_at) < now:
        access_req.status = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="The one-time code has expired. Send a new code.")

    if hash_token(body.code.strip()) != access_req.otp_hash:
        access_req.attempts = (access_req.attempts or 0) + 1
        if access_req.attempts >= 5:
            access_req.status = "locked"
        db.commit()
        log_audit_event(
            db, action="NETWORK_ACCESS_CODE_REJECTED", resource_type="record_access_request",
            resource_id=access_req.id, actor_id=current_user.id, patient_id=access_req.patient_id,
            metadata={"attempts": access_req.attempts}
        )
        remaining = max(0, 5 - access_req.attempts)
        raise HTTPException(status_code=400, detail=f"Incorrect code. {remaining} attempt(s) remaining.")

    consent = Consent(
        patient_id=access_req.patient_id,
        grantee_facility_id=access_req.facility_id,
        scope=["demographics", "allergies", "medications", "conditions", "vitals", "lab_results", "imaging", "notes", "family_history"],
        purpose=NETWORK_ACCESS_PURPOSE,
        expires_at=now + timedelta(hours=settings.ACCESS_CONSENT_HOURS),
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    access_req.status = "approved"
    access_req.approved_at = now
    access_req.consent_id = consent.id
    access_req.demo_code = None
    db.commit()

    log_audit_event(
        db, action="NETWORK_ACCESS_GRANTED", resource_type="consent", resource_id=consent.id,
        actor_id=current_user.id, patient_id=access_req.patient_id,
        metadata={"facility": access_req.facility.name if access_req.facility else None,
                  "method": "patient_one_time_code", "valid_hours": settings.ACCESS_CONSENT_HOURS}
    )

    return {
        "status": "approved",
        "consent_id": consent.id,
        "expires_at": _iso(consent.expires_at),
        "scope": consent.scope,
    }


# ----------------- 4. Unified longitudinal patient record -----------------
@router.get("/patients/{patient_id}")
def get_unified_record(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    access = resolve_access(db, current_user, patient)
    if access["level"] == "none":
        raise HTTPException(status_code=403, detail="Not authorised to view this record")

    encounters = visible_encounters(patient, access)
    all_facilities = _facility_summary(patient)
    hidden = [f for f in all_facilities if access["level"] == "facility_only" and f["facility_id"] != access["facility_id"]]

    insights = db.query(ClinicalInsight).filter(
        ClinicalInsight.patient_id == patient.id
    ).order_by(ClinicalInsight.created_at.desc()).limit(5).all()
    visible_ids = {e.id for e in encounters}

    log_audit_event(
        db, action="NETWORK_RECORD_VIEWED", resource_type="patient", resource_id=patient.id,
        actor_id=current_user.id, patient_id=patient.id,
        metadata={"access_level": access["level"], "encounters_disclosed": len(encounters)}
    )

    full = access["level"] in ("self", "full")
    return {
        # Without patient consent only demographics are disclosed; clinical lists stay locked
        "patient": serialize_patient(patient) if full else {
            **serialize_patient(patient),
            "allergies": [], "chronic_conditions": [], "current_medications": [],
            "restricted": True,
        },
        "access": {
            "level": access["level"],
            "expires_at": _iso(access["consent"].expires_at) if access.get("consent") else None,
            "consent_id": access["consent"].id if access.get("consent") else None,
            "hidden_facilities": [f["facility_name"] for f in hidden],
            "hidden_encounters": sum(f["visits"] for f in hidden),
        },
        "facilities": [f for f in all_facilities if f not in hidden],
        "family_history": [
            {
                "relationship_type": fh.relationship_type,
                "condition": fh.condition,
                "age_of_onset": fh.age_of_onset,
                "is_deceased": fh.is_deceased,
                "verification_status": fh.verification_status,
            } for fh in patient.family_history
        ] if full else [],
        "encounters": [serialize_encounter(e) for e in encounters],
        "vitals_series": vitals_series(encounters),
        "lab_series": lab_series(encounters),
        "insights": [
            {
                "id": i.id,
                "title": i.title,
                "content": i.content,
                "review_status": i.review_status.value if i.review_status else None,
                "model_version": i.model_version,
                "created_at": _iso(i.created_at),
            } for i in insights if not i.encounter_id or i.encounter_id in visible_ids
        ],
    }


# ----------------- Patient-side: pending codes, consents, access log -----------------
def _my_patient(db: Session, user: User) -> Patient:
    patient = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient profile linked to this account")
    return patient


@router.get("/me/access-requests")
def my_pending_access_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PATIENT])),
):
    patient = _my_patient(db, current_user)
    now = get_utc_now()
    out = []
    for r in db.query(RecordAccessRequest).filter(
        RecordAccessRequest.patient_id == patient.id,
        RecordAccessRequest.status == "pending",
    ).order_by(RecordAccessRequest.created_at.desc()).all():
        if _aware(r.expires_at) < now:
            continue
        out.append({
            "request_id": r.id,
            "facility_name": r.facility.name if r.facility else None,
            "requested_by": r.requested_by.full_name if r.requested_by else None,
            "purpose": r.purpose,
            "code": r.demo_code,  # The code the patient reads out to the staff member
            "expires_at": _iso(r.expires_at),
            "created_at": _iso(r.created_at),
        })
    return out


@router.get("/me/access-log")
def my_access_log(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.PATIENT])),
):
    patient = _my_patient(db, current_user)
    now = get_utc_now()
    consents = db.query(Consent).filter(Consent.patient_id == patient.id).order_by(Consent.created_at.desc()).all()
    facility_names = {f.id: f.name for f in db.query(Facility).all()}

    events = db.query(AuditEvent).filter(
        AuditEvent.patient_id == patient.id,
        AuditEvent.action.in_([
            "NETWORK_RECORD_VIEWED", "NETWORK_ACCESS_GRANTED", "NETWORK_ACCESS_REQUESTED",
            "ENCOUNTER_OPENED", "VITALS_RECORDED", "CLINICAL_NOTE_SIGNED",
            "INTELLIGENCE_ASSESSMENT_GENERATED", "CONSENT_REVOKED",
        ]),
    ).order_by(AuditEvent.timestamp.desc()).limit(40).all()

    actor_ids = {e.actor_id for e in events if e.actor_id}
    actors = {u.id: u for u in db.query(User).filter(User.id.in_(actor_ids)).all()} if actor_ids else {}
    from app.models.models import Staff
    staff = {s.user_id: s for s in db.query(Staff).filter(Staff.user_id.in_(actor_ids)).all()} if actor_ids else {}

    return {
        "consents": [
            {
                "id": c.id,
                "facility_name": facility_names.get(c.grantee_facility_id, "Any network facility"),
                "purpose": c.purpose,
                "scope": c.scope,
                "created_at": _iso(c.created_at),
                "expires_at": _iso(c.expires_at),
                "revoked_at": _iso(c.revoked_at),
                "active": c.revoked_at is None and _aware(c.expires_at) > now,
            } for c in consents
        ],
        "events": [
            {
                "id": e.id,
                "action": e.action,
                "timestamp": _iso(e.timestamp),
                "actor": actors[e.actor_id].full_name if e.actor_id in actors else None,
                "actor_role": actors[e.actor_id].role.value if e.actor_id in actors else None,
                "facility_name": facility_names.get(staff[e.actor_id].facility_id) if e.actor_id in staff else None,
            } for e in events if e.actor_id != current_user.id
        ],
    }
