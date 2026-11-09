import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    Referral, Patient, Facility, User, UserRole, ReferralStatus, get_utc_now
)
from app.schemas.schemas import (
    ReferralCreate, ReferralResponse, ReferralStatusUpdate
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/referrals", tags=["VITALIS REFERRAL - External Care Coordination"])

@router.post("", response_model=ReferralResponse)
def create_referral(
    referral_in: ReferralCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == referral_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    dest_facility = db.query(Facility).filter(Facility.id == referral_in.destination_facility_id).first()
    if not dest_facility:
        raise HTTPException(status_code=404, detail="Destination facility not found")

    # If current user is staff, source facility is their facility; otherwise default or first facility
    source_facility_id = referral_in.destination_facility_id
    if current_user.staff_profile:
        source_facility_id = current_user.staff_profile.facility_id

    ref_num = f"REF-2026-{random.randint(10000, 99999)}"

    referral = Referral(
        referral_number=ref_num,
        patient_id=patient.id,
        source_facility_id=source_facility_id,
        destination_facility_id=dest_facility.id,
        encounter_id=referral_in.encounter_id,
        urgency=referral_in.urgency,
        clinical_reason=referral_in.clinical_reason,
        service_needed=referral_in.service_needed,
        status=ReferralStatus.PENDING,
        created_by_id=current_user.id
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    log_audit_event(
        db,
        action="REFERRAL_CREATED",
        resource_type="referral",
        resource_id=referral.id,
        actor_id=current_user.id,
        patient_id=patient.id
    )

    return referral

@router.get("/me", response_model=List[ReferralResponse])
def get_my_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        return []
    return db.query(Referral).filter(Referral.patient_id == patient.id).order_by(Referral.created_at.desc()).all()

@router.get("/facility/{facility_id}", response_model=List[ReferralResponse])
def get_facility_referrals_queue(
    facility_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    """Destination facility referral work queue (Section 6 & 14)"""
    return db.query(Referral).filter(
        Referral.destination_facility_id == facility_id
    ).order_by(Referral.created_at.desc()).all()

@router.patch("/{id}/status", response_model=ReferralResponse)
def update_referral_status(
    id: str,
    status_update: ReferralStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    """Accept, reject or request more info for an incoming referral (Section 14)"""
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
        action=f"REFERRAL_{status_update.status.value.upper()}",
        resource_type="referral",
        resource_id=referral.id,
        actor_id=current_user.id,
        patient_id=referral.patient_id,
        metadata={"response_reason": status_update.facility_response_reason}
    )

    return referral

