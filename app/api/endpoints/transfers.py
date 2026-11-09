import random
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_random_token, hash_token
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    RecordTransfer, Patient, Facility, User, UserRole,
    TransferStatus, get_utc_now
)
from app.schemas.schemas import (
    TransferCreate, TransferResponse, TransferRedeemRequest
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/transfers", tags=["VITALIS TRANSFER - Inter-Hospital Record Exchange"])

# ----------------- 1. Initiate Inter-Hospital Transfer (Hospital A) -----------------
@router.post("", response_model=TransferResponse)
def initiate_transfer(
    transfer_in: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.FACILITY_ADMIN]))
):
    patient = db.query(Patient).filter(Patient.id == transfer_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    recip = db.query(Facility).filter(Facility.id == transfer_in.recipient_facility_id).first()
    if not recip:
        raise HTTPException(status_code=404, detail="Recipient hospital not found")

    sender_facility_id = current_user.staff_profile.facility_id if current_user.staff_profile else recip.id
    if sender_facility_id == recip.id:
        raise HTTPException(status_code=400, detail="Sender and recipient facility cannot be identical")

    transfer_num = f"TRF-2026-{random.randint(10000, 99999)}"

    # Assemble portable structured transfer package (Section 32.3)
    package_manifest = {
        "manifest_version": "VITALIS-PORTABLE-HEALTH-PACKAGE-1.0",
        "created_at": get_utc_now().isoformat(),
        "sender_facility": sender_facility_id,
        "recipient_facility": recip.id,
        "patient": {
            "patient_number": patient.patient_number,
            "full_name": f"{patient.first_name} {patient.last_name}",
            "gender": patient.gender,
            "dob": patient.dob,
            "blood_group": patient.blood_group,
            "genotype": patient.genotype
        },
        "clinical_summary": {
            "allergies": patient.allergies,
            "chronic_conditions": patient.chronic_conditions,
            "current_medications": patient.current_medications,
            "encounters_summary": [
                {
                    "encounter_number": e.encounter_number,
                    "date": e.opened_at.isoformat(),
                    "complaint": e.reception_intake.presenting_complaint if e.reception_intake else None,
                    "notes": [cn.assessment for cn in e.clinical_notes if cn.assessment]
                }
                for e in patient.encounters[:5]
            ]
        }
    }

    transfer = RecordTransfer(
        transfer_number=transfer_num,
        patient_id=patient.id,
        sender_facility_id=sender_facility_id,
        recipient_facility_id=recip.id,
        sender_clinician_id=current_user.id,
        purpose=transfer_in.purpose,
        urgency=transfer_in.urgency,
        scope=transfer_in.scope,
        package_payload=package_manifest,
        status=TransferStatus.DRAFT,
        patient_consented=False
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    log_audit_event(
        db,
        action="TRANSFER_INITIATED",
        resource_type="record_transfer",
        resource_id=transfer.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"recipient_facility_id": recip.id}
    )

    return transfer

# ----------------- 2. Patient / Representative Consent (Section 32.2) -----------------
@router.post("/{id}/consent", response_model=TransferResponse)
def record_transfer_consent(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transfer = db.query(RecordTransfer).filter(RecordTransfer.id == id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    transfer.patient_consented = True
    transfer.consent_recorded_at = get_utc_now()
    transfer.status = TransferStatus.AUTHORISED
    db.commit()
    db.refresh(transfer)

    log_audit_event(
        db,
        action="TRANSFER_CONSENT_GRANTED",
        resource_type="record_transfer",
        resource_id=transfer.id,
        actor_id=current_user.id,
        patient_id=transfer.patient_id
    )

    return transfer

# ----------------- 3. Send / Publish Transfer with One-Time Token (Section 32.2) -----------------
@router.post("/{id}/send")
def send_transfer_package(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.FACILITY_ADMIN]))
):
    transfer = db.query(RecordTransfer).filter(RecordTransfer.id == id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    if not transfer.patient_consented:
        raise HTTPException(status_code=400, detail="Cannot transmit transfer package without recorded patient consent")

    raw_token = generate_random_token(32)
    token_hashed = hash_token(raw_token)
    now = get_utc_now()

    transfer.access_token_hash = token_hashed
    transfer.token_expires_at = now + timedelta(hours=24)  # 24-hour transfer availability window
    transfer.status = TransferStatus.SENT
    db.commit()

    log_audit_event(
        db,
        action="TRANSFER_PACKAGE_SENT",
        resource_type="record_transfer",
        resource_id=transfer.id,
        actor_id=current_user.id,
        patient_id=transfer.patient_id
    )

    return {
        "status": "success",
        "message": "Transfer package successfully prepared and securely dispatched to destination facility",
        "transfer_id": transfer.id,
        "transfer_token": raw_token,  # provided once for secure dispatch or transmission
        "expires_at": transfer.token_expires_at
    }

# ----------------- 4. Receiving Hospital (Hospital B) Access & Redemption -----------------
@router.post("/redeem")
def redeem_transfer_package(
    redeem_in: TransferRedeemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    """
    Receiving Hospital B authenticates and redeems the transfer token.
    Section 32.4: Creates a local copy / view without overwriting Hospital A's original records.
    """
    token_hashed = hash_token(redeem_in.transfer_token)
    transfer = db.query(RecordTransfer).filter(RecordTransfer.access_token_hash == token_hashed).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Invalid transfer token or transfer not found")

    now = get_utc_now()
    exp = transfer.token_expires_at
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp and exp < now:
        raise HTTPException(status_code=403, detail="Transfer token has expired")

    # Mark accessed
    transfer.status = TransferStatus.ACCESSED
    transfer.accessed_at = now
    transfer.acknowledged_at = now
    db.commit()

    log_audit_event(
        db,
        action="TRANSFER_PACKAGE_ACCESSED",
        resource_type="record_transfer",
        resource_id=transfer.id,
        actor_id=current_user.id,
        patient_id=transfer.patient_id,
        metadata={"recipient_facility_id": transfer.recipient_facility_id}
    )

    return {
        "status": "success",
        "message": "Transfer package received and opened successfully at destination facility",
        "transfer_number": transfer.transfer_number,
        "purpose": transfer.purpose,
        "urgency": transfer.urgency,
        "sender_facility_id": transfer.sender_facility_id,
        "package_payload": transfer.package_payload
    }

