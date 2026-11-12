"""
Emergency coordination inbox.

The CareConnect emergency workflow (careconnect.py) asks one candidate hospital at a time
to confirm it can receive the patient. This endpoint lets each side see the requests that
concern it:
  - hospital staff: requests currently waiting for *their* facility's confirmation,
    plus ones their facility has confirmed in the last 24 hours;
  - patients: their own emergency requests.
"""
from datetime import timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.models import (
    EmergencyRequest, EmergencyRequestStatus, Patient, User, UserRole, get_utc_now
)
from app.schemas.schemas import EmergencyRequestResponse
from app.services.record_access import get_staff_facility_id

router = APIRouter(tags=["VITALIS CareConnect - Emergency Coordination"])

ACTIVE = [
    EmergencyRequestStatus.AWAITING_HOSPITAL_CONFIRMATION,
    EmergencyRequestStatus.CONFIRMED,
    EmergencyRequestStatus.TRANSPORT_COORDINATED,
    EmergencyRequestStatus.EN_ROUTE,
    EmergencyRequestStatus.ARRIVED,
]


def _with_patient(req: EmergencyRequest) -> Dict[str, Any]:
    data = EmergencyRequestResponse.model_validate(req).model_dump()
    p = req.patient
    data["patient_name"] = f"{p.first_name} {p.last_name}" if p else None
    data["patient_number"] = p.patient_number if p else None
    return data


@router.get("/emergency/requests")
def list_emergency_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    if current_user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            return []
        reqs = db.query(EmergencyRequest).filter(EmergencyRequest.patient_id == patient.id) \
            .order_by(EmergencyRequest.created_at.desc()).limit(20).all()
        return [_with_patient(r) for r in reqs]

    facility_id = get_staff_facility_id(db, current_user)
    if not facility_id:
        return []
    since = get_utc_now() - timedelta(hours=24)
    reqs = db.query(EmergencyRequest).filter(
        EmergencyRequest.status.in_(ACTIVE),
        EmergencyRequest.created_at >= since,
        or_(
            (EmergencyRequest.current_candidate_facility_id == facility_id)
            & (EmergencyRequest.status == EmergencyRequestStatus.AWAITING_HOSPITAL_CONFIRMATION),
            EmergencyRequest.confirmed_facility_id == facility_id,
        ),
    ).order_by(EmergencyRequest.created_at.desc()).all()
    return [_with_patient(r) for r in reqs]
