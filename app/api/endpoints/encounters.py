import random
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles, get_current_staff
from app.models.models import (
    Encounter, ReceptionIntake, NursingObservation, ClinicalNote, 
    InvestigationOrder, LabResult, RadiologyReport, Patient, Facility, 
    User, UserRole, EncounterStatus, EncounterPriority, OrderStatus,
    OrderDepartment, get_utc_now
)
from app.schemas.schemas import (
    EncounterCreate, ConsolidatedEncounterResponse, 
    NursingObservationsCreate, NursingObservationResponse,
    ClinicalNoteCreate, ClinicalNoteResponse,
    InvestigationOrderCreate, InvestigationOrderResponse,
    LabResultCreate, RadiologyReportCreate
)
from app.engines.triage.rules import check_vital_warning
from app.services.audit import log_audit_event

router = APIRouter(prefix="/encounters", tags=["Centralized Hospital Encounters"])

def format_consolidated_encounter(enc: Encounter) -> ConsolidatedEncounterResponse:
    # Build consolidated response
    orders_data = []
    for o in enc.investigation_orders:
        orders_data.append(InvestigationOrderResponse(
            id=o.id,
            order_number=o.order_number,
            encounter_id=o.encounter_id,
            ordering_clinician_id=o.ordering_clinician_id,
            department=o.department,
            test_or_modality=o.test_or_modality,
            clinical_indication=o.clinical_indication,
            priority=o.priority,
            status=o.status,
            ordered_at=o.ordered_at,
            acknowledged_at=o.acknowledged_at,
            completed_at=o.completed_at,
            lab_result={
                "id": o.lab_result.id,
                "specimen_type": o.lab_result.specimen_type,
                "result_payload": o.lab_result.result_payload,
                "comments": o.lab_result.comments,
                "entered_by": o.lab_result.entered_by.full_name if o.lab_result.entered_by else None,
                "verified_by": o.lab_result.verified_by.full_name if o.lab_result.verified_by else None,
                "verified_at": o.lab_result.verified_at
            } if o.lab_result else None,
            radiology_report={
                "id": o.radiology_report.id,
                "modality": o.radiology_report.modality,
                "body_region": o.radiology_report.body_region,
                "findings": o.radiology_report.findings,
                "impression": o.radiology_report.impression,
                "reported_by": o.radiology_report.reported_by.full_name if o.radiology_report.reported_by else None,
                "verified_by": o.radiology_report.verified_by.full_name if o.radiology_report.verified_by else None,
                "verified_at": o.radiology_report.verified_at
            } if o.radiology_report else None
        ))

    return ConsolidatedEncounterResponse(
        id=enc.id,
        encounter_number=enc.encounter_number,
        patient_id=enc.patient_id,
        patient_name=f"{enc.patient.first_name} {enc.patient.last_name}",
        patient_number=enc.patient.patient_number,
        facility_id=enc.facility_id,
        facility_name=enc.facility.name if enc.facility else "Unknown Facility",
        visit_type=enc.visit_type,
        priority=enc.priority,
        status=enc.status,
        opened_at=enc.opened_at,
        closed_at=enc.closed_at,
        reception_intake=enc.reception_intake,
        nursing_observations=[
            NursingObservationResponse.model_validate(no) for no in enc.nursing_observations
        ],
        clinical_notes=[
            ClinicalNoteResponse.model_validate(cn) for cn in enc.clinical_notes
        ],
        investigation_orders=orders_data
    )

# ----------------- 5.1 Reception: Open Encounter & Intake -----------------
@router.post("", response_model=ConsolidatedEncounterResponse)
def open_encounter(
    encounter_in: EncounterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.RECEPTION, UserRole.NURSE, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    patient = db.query(Patient).filter(Patient.id == encounter_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient record not found")

    facility = db.query(Facility).filter(Facility.id == encounter_in.facility_id).first()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    enc_num = f"ENC-{facility.facility_code}-{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"
    
    # Emergency bypass support (Section 5.1 & 5.5)
    # If flagged emergency, route directly to urgent priority
    priority = encounter_in.priority
    if encounter_in.is_emergency_flag:
        priority = EncounterPriority.EMERGENCY

    new_encounter = Encounter(
        encounter_number=enc_num,
        patient_id=patient.id,
        facility_id=facility.id,
        visit_type=encounter_in.visit_type,
        priority=priority,
        status=EncounterStatus.AWAITING_NURSING,
        created_by_id=current_user.id
    )
    db.add(new_encounter)
    db.commit()
    db.refresh(new_encounter)

    # Save reception intake
    intake = ReceptionIntake(
        encounter_id=new_encounter.id,
        presenting_complaint=encounter_in.presenting_complaint,
        arrival_mode=encounter_in.arrival_mode,
        referral_source=encounter_in.referral_source,
        is_emergency_flag=encounter_in.is_emergency_flag,
        administrative_notes=encounter_in.administrative_notes,
        captured_by=current_user.id
    )
    db.add(intake)
    db.commit()
    db.refresh(new_encounter)

    log_audit_event(
        db,
        action="ENCOUNTER_OPENED",
        resource_type="encounter",
        resource_id=new_encounter.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        encounter_id=new_encounter.id
    )

    return format_consolidated_encounter(new_encounter)

# ----------------- Consolidated Encounter Lookup -----------------
@router.get("/{id}", response_model=ConsolidatedEncounterResponse)
def get_encounter_by_id(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    encounter = db.query(Encounter).filter(Encounter.id == id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    # If patient, verify it belongs to them
    if current_user.role == UserRole.PATIENT:
        if encounter.patient.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized access to encounter")

    log_audit_event(
        db,
        action="ENCOUNTER_VIEWED",
        resource_type="encounter",
        resource_id=encounter.id,
        actor_id=current_user.id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id
    )

    return format_consolidated_encounter(encounter)

# ----------------- 5.2 Nursing: Vital Signs & Warning Flags -----------------
@router.post("/{id}/observations", response_model=ConsolidatedEncounterResponse)
def record_nursing_observations(
    id: str,
    obs_in: NursingObservationsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.NURSE, UserRole.DOCTOR]))
):
    encounter = db.query(Encounter).filter(Encounter.id == id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    has_urgent_vitals = False
    for item in obs_in.observations:
        is_warn, warn_msg = check_vital_warning(item.observation_type, item.value)
        if is_warn:
            has_urgent_vitals = True

        obs = NursingObservation(
            encounter_id=encounter.id,
            observation_type=item.observation_type,
            value=item.value,
            unit=item.unit,
            is_warning=is_warn,
            warning_message=warn_msg,
            nurse_note=item.nurse_note or obs_in.general_nurse_note,
            measured_by=current_user.id
        )
        db.add(obs)

    if has_urgent_vitals:
        encounter.priority = EncounterPriority.URGENT

    # Move encounter to doctor queue if requested
    if obs_in.handover_to_doctor:
        encounter.status = EncounterStatus.AWAITING_DOCTOR

    db.commit()
    db.refresh(encounter)

    log_audit_event(
        db,
        action="VITALS_RECORDED",
        resource_type="encounter",
        resource_id=encounter.id,
        actor_id=current_user.id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        metadata={"urgent_flag": has_urgent_vitals}
    )

    return format_consolidated_encounter(encounter)

# ----------------- 5.3 Doctor: Consultation Notes & AI-Assisted Review -----------------
@router.post("/{id}/clinical-notes", response_model=ConsolidatedEncounterResponse)
def record_clinical_note(
    id: str,
    note_in: ClinicalNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    encounter = db.query(Encounter).filter(Encounter.id == id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    signed_time = get_utc_now() if not note_in.is_draft else None

    note = ClinicalNote(
        encounter_id=encounter.id,
        author_id=current_user.id,
        note_type=note_in.note_type,
        history_of_complaint=note_in.history_of_complaint,
        examination_findings=note_in.examination_findings,
        assessment=note_in.assessment,
        differential_considerations=note_in.differential_considerations,
        clinical_plan=note_in.clinical_plan,
        disposition=note_in.disposition,
        is_draft=note_in.is_draft,
        is_ai_assisted=note_in.is_ai_assisted,
        ai_raw_draft=note_in.ai_raw_draft,
        signed_at=signed_time
    )
    db.add(note)

    # If disposition closed / discharged
    if note_in.disposition in ["discharged", "completed"]:
        encounter.status = EncounterStatus.COMPLETED
        encounter.closed_at = get_utc_now()
    elif encounter.status == EncounterStatus.AWAITING_DOCTOR:
        encounter.status = EncounterStatus.AWAITING_DISPOSITION

    db.commit()
    db.refresh(encounter)

    log_audit_event(
        db,
        action="CLINICAL_NOTE_SIGNED" if not note_in.is_draft else "CLINICAL_NOTE_DRAFTED",
        resource_type="clinical_note",
        resource_id=note.id,
        actor_id=current_user.id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        metadata={"is_ai_assisted": note_in.is_ai_assisted}
    )

    return format_consolidated_encounter(encounter)

# ----------------- 5.3 Doctor: Order Investigations -----------------
@router.post("/{id}/investigation-orders", response_model=ConsolidatedEncounterResponse)
def place_investigation_order(
    id: str,
    order_in: InvestigationOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    encounter = db.query(Encounter).filter(Encounter.id == id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    facility = encounter.facility
    prefix = "LAB" if order_in.department == OrderDepartment.LABORATORY else "RAD"
    order_num = f"{prefix}-{facility.facility_code if facility else 'GEN'}-{random.randint(1000, 9999)}"

    new_order = InvestigationOrder(
        order_number=order_num,
        encounter_id=encounter.id,
        ordering_clinician_id=current_user.id,
        department=order_in.department,
        test_or_modality=order_in.test_or_modality,
        clinical_indication=order_in.clinical_indication,
        priority=order_in.priority,
        status=OrderStatus.REQUESTED
    )
    db.add(new_order)
    
    # Transition encounter status to awaiting investigation
    encounter.status = EncounterStatus.AWAITING_INVESTIGATION
    db.commit()
    db.refresh(encounter)

    log_audit_event(
        db,
        action="INVESTIGATION_ORDER_PLACED",
        resource_type="investigation_order",
        resource_id=new_order.id,
        actor_id=current_user.id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        metadata={"order_number": order_num, "test": order_in.test_or_modality}
    )

    return format_consolidated_encounter(encounter)

# ----------------- Departmental Work Queues -----------------
@router.get("/queue/{department}", response_model=List[ConsolidatedEncounterResponse])
def get_department_work_queue(
    department: str,
    facility_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get active queue for a specific hospital department:
    - reception: registered / walk-in
    - nursing: awaiting_nursing
    - doctor: awaiting_doctor / results_ready / awaiting_disposition
    - lab / radiology: orders handled via diagnostics endpoint
    """
    query = db.query(Encounter)
    if facility_id:
        query = query.filter(Encounter.facility_id == facility_id)

    dept = department.lower()
    if dept == "reception":
        encounters = query.filter(
            Encounter.status.in_([EncounterStatus.REGISTERED, EncounterStatus.AWAITING_NURSING])
        ).order_by(Encounter.opened_at.desc()).all()
    elif dept == "nursing":
        encounters = query.filter(
            Encounter.status == EncounterStatus.AWAITING_NURSING
        ).order_by(Encounter.opened_at.asc()).all()
    elif dept == "doctor":
        encounters = query.filter(
            Encounter.status.in_([
                EncounterStatus.AWAITING_DOCTOR,
                EncounterStatus.RESULTS_READY,
                EncounterStatus.AWAITING_DISPOSITION
            ])
        ).order_by(Encounter.priority.desc(), Encounter.opened_at.asc()).all()
    else:
        encounters = query.filter(
            Encounter.status != EncounterStatus.COMPLETED
        ).order_by(Encounter.opened_at.desc()).limit(50).all()

    return [format_consolidated_encounter(e) for e in encounters]

