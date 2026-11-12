"""Serializers that flatten a patient's longitudinal record for the network view and VITALIS AI."""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.models import Encounter, Patient


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def patient_age(patient: Patient) -> Optional[int]:
    try:
        dob = datetime.strptime(patient.dob, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = [c for c in phone if c.isdigit()]
    if len(digits) < 4:
        return "****"
    return f"{phone[:4]}*****{''.join(digits[-3:])}"


def serialize_patient(patient: Patient) -> Dict[str, Any]:
    return {
        "id": patient.id,
        "patient_number": patient.patient_number,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "full_name": f"{patient.first_name} {patient.last_name}",
        "gender": patient.gender,
        "dob": patient.dob,
        "age": patient_age(patient),
        "phone": patient.phone,
        "address": patient.address,
        "blood_group": patient.blood_group,
        "genotype": patient.genotype,
        "allergies": patient.allergies or [],
        "chronic_conditions": patient.chronic_conditions or [],
        "current_medications": patient.current_medications or [],
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "created_at": _iso(patient.created_at),
    }


def serialize_encounter(enc: Encounter) -> Dict[str, Any]:
    intake = enc.reception_intake
    orders = []
    for o in enc.investigation_orders:
        lab = o.lab_result
        rad = o.radiology_report
        orders.append({
            "id": o.id,
            "order_number": o.order_number,
            "department": o.department.value,
            "test_or_modality": o.test_or_modality,
            "clinical_indication": o.clinical_indication,
            "priority": o.priority,
            "status": o.status.value,
            "ordered_at": _iso(o.ordered_at),
            "ordered_by": o.ordering_clinician.full_name if o.ordering_clinician else None,
            "lab_result": {
                "specimen_type": lab.specimen_type,
                "result_payload": lab.result_payload,
                "comments": lab.comments,
                "entered_by": lab.entered_by.full_name if lab.entered_by else None,
                "verified_by": lab.verified_by.full_name if lab.verified_by else None,
                "verified_at": _iso(lab.verified_at),
                "entered_at": _iso(lab.entered_at),
            } if lab else None,
            "radiology_report": {
                "modality": rad.modality,
                "body_region": rad.body_region,
                "findings": rad.findings,
                "impression": rad.impression,
                "reported_by": rad.reported_by.full_name if rad.reported_by else None,
                "verified_by": rad.verified_by.full_name if rad.verified_by else None,
                "verified_at": _iso(rad.verified_at),
            } if rad else None,
        })

    return {
        "id": enc.id,
        "encounter_number": enc.encounter_number,
        "facility_id": enc.facility_id,
        "facility_name": enc.facility.name if enc.facility else "Unknown facility",
        "facility_code": enc.facility.facility_code if enc.facility else None,
        "visit_type": enc.visit_type.value,
        "priority": enc.priority.value,
        "status": enc.status.value,
        "opened_at": _iso(enc.opened_at),
        "closed_at": _iso(enc.closed_at),
        "presenting_complaint": intake.presenting_complaint if intake else None,
        "arrival_mode": intake.arrival_mode if intake else None,
        "is_emergency": intake.is_emergency_flag if intake else False,
        "vitals": [
            {
                "observation_type": v.observation_type,
                "value": v.value,
                "unit": v.unit,
                "is_warning": v.is_warning,
                "warning_message": v.warning_message,
                "measured_at": _iso(v.measured_at),
                "measured_by": v.nurse.full_name if v.nurse else None,
                "nurse_note": v.nurse_note,
            }
            for v in enc.nursing_observations
        ],
        "clinical_notes": [
            {
                "id": n.id,
                "author": n.author.full_name if n.author else None,
                "note_type": n.note_type,
                "history_of_complaint": n.history_of_complaint,
                "examination_findings": n.examination_findings,
                "assessment": n.assessment,
                "differential_considerations": n.differential_considerations or [],
                "clinical_plan": n.clinical_plan,
                "disposition": n.disposition,
                "is_ai_assisted": n.is_ai_assisted,
                "signed_at": _iso(n.signed_at),
                "created_at": _iso(n.created_at),
            }
            for n in sorted(enc.clinical_notes, key=lambda n: n.created_at or datetime.min.replace(tzinfo=timezone.utc))
        ],
        "investigations": orders,
    }


def vitals_series(encounters: List[Encounter]) -> List[Dict[str, Any]]:
    out = []
    for enc in encounters:
        for v in enc.nursing_observations:
            out.append({
                "observation_type": v.observation_type,
                "value": v.value,
                "unit": v.unit,
                "is_warning": v.is_warning,
                "measured_at": _iso(v.measured_at),
                "encounter_id": enc.id,
                "facility_name": enc.facility.name if enc.facility else None,
            })
    out.sort(key=lambda x: x["measured_at"] or "")
    return out


def lab_series(encounters: List[Encounter]) -> List[Dict[str, Any]]:
    """Flatten verified/entered lab results into one row per parameter."""
    out = []
    for enc in encounters:
        for o in enc.investigation_orders:
            lab = o.lab_result
            if not lab or not isinstance(lab.result_payload, dict):
                continue
            for param, res in lab.result_payload.items():
                if isinstance(res, dict):
                    value, unit = res.get("value"), res.get("unit")
                    ref, flag = res.get("reference_range"), res.get("flag")
                else:
                    value, unit, ref, flag = res, None, None, None
                out.append({
                    "test": o.test_or_modality,
                    "parameter": param,
                    "value": value,
                    "unit": unit,
                    "reference_range": ref,
                    "flag": flag,
                    "date": _iso(lab.verified_at or lab.entered_at or o.ordered_at),
                    "verified": lab.verified_at is not None,
                    "encounter_id": enc.id,
                    "facility_name": enc.facility.name if enc.facility else None,
                })
    out.sort(key=lambda x: x["date"] or "")
    return out
