import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    Patient, User, UserRole, FamilyHistoryEntry, HealthRecord
)
from app.schemas.schemas import (
    PatientCreate, PatientResponse, FamilyHistoryCreate, 
    FamilyHistoryResponse
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post("", response_model=PatientResponse)
def create_patient_profile(
    patient_in: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Register a patient (authorized patient self-profile or reception/staff intake)
    """
    # If the user is a patient, link to self if not already linked
    user_id = None
    if current_user.role == UserRole.PATIENT:
        existing = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if existing:
            # Update existing profile
            for field, val in patient_in.model_dump().items():
                setattr(existing, field, val)
            db.commit()
            db.refresh(existing)
            return existing
        user_id = current_user.id

    p_num = f"VIT-2026-{random.randint(10000, 99999)}"
    patient = Patient(
        user_id=user_id,
        patient_number=p_num,
        first_name=patient_in.first_name,
        last_name=patient_in.last_name,
        gender=patient_in.gender,
        dob=patient_in.dob,
        phone=patient_in.phone,
        address=patient_in.address,
        blood_group=patient_in.blood_group,
        genotype=patient_in.genotype,
        allergies=patient_in.allergies,
        chronic_conditions=patient_in.chronic_conditions,
        current_medications=patient_in.current_medications,
        emergency_contact_name=patient_in.emergency_contact_name,
        emergency_contact_phone=patient_in.emergency_contact_phone
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    log_audit_event(
        db,
        action="PATIENT_PROFILE_CREATED",
        resource_type="patient",
        resource_id=patient.id,
        actor_id=current_user.id,
        patient_id=patient.id
    )

    return patient

@router.get("/me", response_model=PatientResponse)
def get_my_patient_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found for current user"
        )
    return patient

@router.get("/search", response_model=List[PatientResponse])
def search_patients(
    query: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR,
        UserRole.LAB_TECH, UserRole.RADIOLOGIST, UserRole.FACILITY_ADMIN,
        UserRole.NETWORK_ADMIN
    ]))
):
    """
    Search patients by patient number, name, or phone number.
    Role-scoped to clinical/hospital staff.
    """
    q_str = f"%{query}%"
    patients = db.query(Patient).filter(
        (Patient.patient_number.ilike(q_str)) |
        (Patient.first_name.ilike(q_str)) |
        (Patient.last_name.ilike(q_str)) |
        (Patient.phone.ilike(q_str))
    ).limit(20).all()
    return patients

@router.get("/{id}", response_model=PatientResponse)
def get_patient_by_id(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    # Check permissions: patient himself or staff
    if current_user.role == UserRole.PATIENT and patient.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to view another patient's data")
        
    return patient

# Family History Endpoints (Section 31.4 & 33.2)
@router.post("/{patient_id}/family-history", response_model=FamilyHistoryResponse)
def add_family_history(
    patient_id: str,
    entry: FamilyHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    fh = FamilyHistoryEntry(
        patient_id=patient_id,
        relationship_type=entry.relationship_type,
        condition=entry.condition,
        age_of_onset=entry.age_of_onset,
        is_deceased=entry.is_deceased,
        notes=entry.notes,
        verification_status="clinician_confirmed" if current_user.role == UserRole.DOCTOR else "patient_reported"
    )
    db.add(fh)
    db.commit()
    db.refresh(fh)

    log_audit_event(
        db,
        action="FAMILY_HISTORY_ADDED",
        resource_type="family_history",
        resource_id=fh.id,
        actor_id=current_user.id,
        patient_id=patient_id
    )

    return fh

@router.get("/{patient_id}/family-history", response_model=List[FamilyHistoryResponse])
def get_patient_family_history(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(FamilyHistoryEntry).filter(FamilyHistoryEntry.patient_id == patient_id).all()

