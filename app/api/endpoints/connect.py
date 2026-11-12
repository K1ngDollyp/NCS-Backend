from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_random_token, hash_token
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    Consent, QRAccessGrant, Patient, User, UserRole, Facility,
    HealthRecord, NursingObservation, LabResult, RadiologyReport,
    get_utc_now
)
from app.schemas.schemas import (
    ConsentCreate, QRGrantResponse, QRRedeemRequest
)
from app.services.qr_service import generate_qr_code_data_uri
from app.services.audit import log_audit_event

router = APIRouter(prefix="/connect", tags=["VITALIS CONNECT - Consent & Secure QR Access"])

# ----------------- Create Scoped Consent & Generate QR Grant -----------------
@router.post("/qr-grants", response_model=QRGrantResponse)
def create_qr_access_grant(
    consent_in: ConsentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == consent_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    # Authorize: Patient himself or authorized staff
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

    # Secure token generation: store only SHA-256 hash server-side
    raw_token = generate_random_token(32)
    token_hashed = hash_token(raw_token)

    grant = QRAccessGrant(
        consent_id=consent.id,
        token_hash=token_hashed,
        expires_at=exp_time
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)

    # Content URL encoded in QR
    qr_payload = f"https://vitalis.health/redeem?token={raw_token}&cid={consent.id}"
    qr_base64 = generate_qr_code_data_uri(qr_payload)

    log_audit_event(
        db,
        action="QR_ACCESS_GRANT_ISSUED",
        resource_type="qr_grant",
        resource_id=grant.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"scope": consent_in.scope, "duration_minutes": consent_in.duration_minutes}
    )

    return QRGrantResponse(
        grant_id=grant.id,
        consent_id=consent.id,
        qr_token=raw_token,
        qr_code_base64=qr_base64,
        expires_at=exp_time,
        scope=consent_in.scope
    )

# ----------------- Redeem QR Grant (Hospital Staff) -----------------
@router.post("/redeem")
def redeem_qr_grant(
    redeem_in: QRRedeemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR,
        UserRole.LAB_TECH, UserRole.RADIOLOGIST, UserRole.FACILITY_ADMIN
    ]))
):
    """
    Hospital staff redeems QR token:
    1. Checks token hash server-side
    2. Validates expiry, revocation, single-use
    3. Returns ONLY authorized scoped records
    4. Marks token redeemed and records immutable audit event
    """
    token_hashed = hash_token(redeem_in.token)
    grant = db.query(QRAccessGrant).filter(QRAccessGrant.token_hash == token_hashed).first()

    if not grant:
        raise HTTPException(status_code=404, detail="Invalid or unrecognized QR access token")

    now = get_utc_now()
    if grant.revoked_at:
        raise HTTPException(status_code=403, detail="This QR access grant was revoked by the patient")

    if grant.redeemed_at:
        raise HTTPException(status_code=403, detail="Single-use QR token has already been redeemed")

    # Expiry check
    grant_exp = grant.expires_at
    if grant_exp.tzinfo is None:
        grant_exp = grant_exp.replace(tzinfo=timezone.utc)
    if grant_exp < now:
        raise HTTPException(status_code=403, detail="QR access grant has expired")

    consent = grant.consent
    patient = consent.patient

    # Scoped records extraction
    scope = consent.scope or []
    scoped_data: Dict[str, Any] = {
        "patient_id": patient.id,
        "patient_number": patient.patient_number,
        "demographics": {
            "name": f"{patient.first_name} {patient.last_name}",
            "gender": patient.gender,
            "dob": patient.dob,
            "blood_group": patient.blood_group,
            "genotype": patient.genotype
        }
    }

    if "allergies" in scope:
        scoped_data["allergies"] = patient.allergies
    if "medications" in scope:
        scoped_data["current_medications"] = patient.current_medications
    if "conditions" in scope or "summary" in scope:
        scoped_data["chronic_conditions"] = patient.chronic_conditions

    # Resolve facility by ID or facility_code for PostgreSQL foreign-key integrity
    resolved_facility_id = None
    if redeem_in.facility_id:
        fac = db.query(Facility).filter(
            (Facility.id == redeem_in.facility_id) | (Facility.facility_code == redeem_in.facility_id)
        ).first()
        if fac:
            resolved_facility_id = fac.id
    if not resolved_facility_id and current_user.staff_profile:
        resolved_facility_id = current_user.staff_profile.facility_id

    # Mark grant redeemed
    grant.redeemed_at = now
    grant.redeemed_by_id = current_user.id
    grant.redeemed_facility_id = resolved_facility_id
    db.commit()

    log_audit_event(
        db,
        action="QR_ACCESS_GRANT_REDEEMED",
        resource_type="qr_grant",
        resource_id=grant.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"redeemed_facility": redeem_in.facility_id, "scope": scope}
    )

    return {
        "status": "success",
        "message": "QR grant redeemed successfully within authorized scope",
        "redeemed_at": now,
        "scope": scope,
        "data": scoped_data
    }

# ----------------- Revoke Consent -----------------
@router.delete("/consents/{consent_id}")
def revoke_consent(
    consent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    consent = db.query(Consent).filter(Consent.id == consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail="Consent record not found")

    if current_user.role == UserRole.PATIENT and consent.patient.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to revoke this consent")

    now = get_utc_now()
    consent.revoked_at = now
    for g in consent.qr_grants:
        g.revoked_at = now

    db.commit()

    log_audit_event(
        db,
        action="CONSENT_REVOKED",
        resource_type="consent",
        resource_id=consent.id,
        actor_id=current_user.id,
        patient_id=consent.patient_id
    )

    return {"status": "success", "message": "Consent and all associated grants revoked"}

