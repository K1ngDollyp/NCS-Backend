from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    InvestigationOrder, LabResult, RadiologyReport, Encounter,
    User, UserRole, OrderStatus, OrderDepartment, EncounterStatus,
    get_utc_now
)
from app.schemas.schemas import (
    InvestigationOrderResponse, LabResultCreate, RadiologyReportCreate
)
from app.services.audit import log_audit_event

router = APIRouter(prefix="/diagnostics", tags=["Laboratory & Radiology Diagnostics"])

def format_order(o: InvestigationOrder) -> InvestigationOrderResponse:
    return InvestigationOrderResponse(
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
    )

# Diagnostic Work Queue
@router.get("/work-queue", response_model=List[InvestigationOrderResponse])
def get_diagnostics_work_queue(
    department: Optional[OrderDepartment] = None,
    facility_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.LAB_TECH, UserRole.RADIOLOGIST, UserRole.DOCTOR, UserRole.FACILITY_ADMIN
    ]))
):
    query = db.query(InvestigationOrder)
    if department:
        query = query.filter(InvestigationOrder.department == department)
    if facility_id:
        query = query.join(Encounter).filter(Encounter.facility_id == facility_id)

    # Exclude completed/reviewed orders from immediate action queue
    orders = query.filter(
        InvestigationOrder.status.in_([
            OrderStatus.REQUESTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.SAMPLE_COLLECTED,
            OrderStatus.IN_PROGRESS,
            OrderStatus.RESULT_ENTERED
        ])
    ).order_by(InvestigationOrder.ordered_at.asc()).all()

    return [format_order(o) for o in orders]

# Status Transitions
@router.patch("/orders/{id}/status", response_model=InvestigationOrderResponse)
def update_order_status(
    id: str,
    new_status: OrderStatus,
    rejection_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.LAB_TECH, UserRole.RADIOLOGIST, UserRole.DOCTOR
    ]))
):
    order = db.query(InvestigationOrder).filter(InvestigationOrder.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Investigation order not found")

    order.status = new_status
    if new_status == OrderStatus.ACKNOWLEDGED:
        order.acknowledged_at = get_utc_now()
    elif new_status == OrderStatus.REJECTED:
        order.rejection_reason = rejection_reason or "Rejected by diagnostic department"

    db.commit()
    db.refresh(order)

    log_audit_event(
        db,
        action="ORDER_STATUS_UPDATED",
        resource_type="investigation_order",
        resource_id=order.id,
        actor_id=current_user.id,
        encounter_id=order.encounter_id,
        metadata={"new_status": new_status.value}
    )

    return format_order(order)

# Enter Lab Result
@router.post("/orders/{id}/lab-results", response_model=InvestigationOrderResponse)
def enter_lab_result(
    id: str,
    result_in: LabResultCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.LAB_TECH, UserRole.DOCTOR]))
):
    order = db.query(InvestigationOrder).filter(InvestigationOrder.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Investigation order not found")

    if order.department != OrderDepartment.LABORATORY:
        raise HTTPException(status_code=400, detail="This order is not a laboratory order")

    existing_result = db.query(LabResult).filter(LabResult.order_id == id).first()
    if existing_result:
        # Update existing
        existing_result.result_payload = result_in.result_payload
        existing_result.comments = result_in.comments
        existing_result.specimen_type = result_in.specimen_type
    else:
        new_result = LabResult(
            order_id=order.id,
            specimen_type=result_in.specimen_type,
            result_payload=result_in.result_payload,
            comments=result_in.comments,
            entered_by_id=current_user.id,
            entered_at=get_utc_now()
        )
        db.add(new_result)

    order.status = OrderStatus.RESULT_ENTERED
    db.commit()
    db.refresh(order)

    log_audit_event(
        db,
        action="LAB_RESULT_ENTERED",
        resource_type="lab_result",
        resource_id=order.id,
        actor_id=current_user.id,
        encounter_id=order.encounter_id
    )

    return format_order(order)

# Enter Radiology Report
@router.post("/orders/{id}/radiology-reports", response_model=InvestigationOrderResponse)
def enter_radiology_report(
    id: str,
    report_in: RadiologyReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.RADIOLOGIST, UserRole.DOCTOR]))
):
    order = db.query(InvestigationOrder).filter(InvestigationOrder.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Investigation order not found")

    if order.department != OrderDepartment.RADIOLOGY:
        raise HTTPException(status_code=400, detail="This order is not a radiology order")

    existing_report = db.query(RadiologyReport).filter(RadiologyReport.order_id == id).first()
    if existing_report:
        existing_report.modality = report_in.modality
        existing_report.body_region = report_in.body_region
        existing_report.findings = report_in.findings
        existing_report.impression = report_in.impression
        existing_report.attachment_ref = report_in.attachment_ref
    else:
        new_report = RadiologyReport(
            order_id=order.id,
            modality=report_in.modality,
            body_region=report_in.body_region,
            findings=report_in.findings,
            impression=report_in.impression,
            attachment_ref=report_in.attachment_ref,
            reported_by_id=current_user.id,
            reported_at=get_utc_now()
        )
        db.add(new_report)

    order.status = OrderStatus.RESULT_ENTERED
    db.commit()
    db.refresh(order)

    log_audit_event(
        db,
        action="RADIOLOGY_REPORT_ENTERED",
        resource_type="radiology_report",
        resource_id=order.id,
        actor_id=current_user.id,
        encounter_id=order.encounter_id
    )

    return format_order(order)

# Verify Result (Authorized Role)
@router.post("/orders/{id}/verify", response_model=InvestigationOrderResponse)
def verify_diagnostic_result(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.DOCTOR, UserRole.LAB_TECH, UserRole.RADIOLOGIST
    ]))
):
    order = db.query(InvestigationOrder).filter(InvestigationOrder.id == id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    now = get_utc_now()
    if order.department == OrderDepartment.LABORATORY and order.lab_result:
        order.lab_result.verified_by_id = current_user.id
        order.lab_result.verified_at = now
    elif order.department == OrderDepartment.RADIOLOGY and order.radiology_report:
        order.radiology_report.verified_by_id = current_user.id
        order.radiology_report.verified_at = now

    order.status = OrderStatus.VERIFIED
    order.completed_at = now

    # Move encounter to RESULTS_READY so attending doctor sees it immediately
    encounter = order.encounter
    if encounter:
        encounter.status = EncounterStatus.RESULTS_READY

    db.commit()
    db.refresh(order)

    log_audit_event(
        db,
        action="DIAGNOSTIC_RESULT_VERIFIED",
        resource_type="investigation_order",
        resource_id=order.id,
        actor_id=current_user.id,
        encounter_id=order.encounter_id
    )

    return format_order(order)

