from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import (
    ClinicalInsight, Patient, Encounter, User, UserRole,
    InsightReviewStatus, get_utc_now
)
from app.schemas.schemas import (
    MedicationSafetyCheckRequest, MedicationSafetyCheckResponse,
    DifferentialRequest, DifferentialResponse, InsightReviewRequest,
    HeartDiseaseMLInput, DiabetesMLInput, MLPredictionResponse
)
from app.services.medication_safety import MedicationSafetyChecker
from app.services.intelligence import IntelligenceService
from app.services.ncs_model_adapter import NCSModelAdapter
from app.services.audit import log_audit_event

router = APIRouter(prefix="/intelligence", tags=["VITALIS INTELLIGENCE - Clinical Decision Support"])

# ----------------- Medication Safety Check -----------------
@router.post("/medication-safety-check", response_model=MedicationSafetyCheckResponse)
def check_medication_safety(
    check_in: MedicationSafetyCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    patient = db.query(Patient).filter(Patient.id == check_in.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found")

    result = MedicationSafetyChecker.check_medication_safety(
        proposed_meds=check_in.proposed_medications,
        patient_allergies=patient.allergies or [],
        current_medications=patient.current_medications or [],
        patient_conditions=patient.chronic_conditions or []
    )

    log_audit_event(
        db,
        action="MEDICATION_SAFETY_CHECK_RUN",
        resource_type="medication_check",
        actor_id=current_user.id,
        patient_id=patient.id,
        metadata={"proposed": check_in.proposed_medications, "is_safe": result["is_safe_to_proceed"]}
    )

    return MedicationSafetyCheckResponse(
        patient_id=patient.id,
        proposed_medications=check_in.proposed_medications,
        allergy_conflicts=result["allergy_conflicts"],
        drug_interactions=result["drug_interactions"],
        contraindications_and_warnings=result["contraindications_and_warnings"],
        is_safe_to_proceed=result["is_safe_to_proceed"],
        reference_source=result["reference_source"],
        disclaimer=result["disclaimer"]
    )

# ----------------- Differential Decision Support -----------------
@router.post("/encounters/{encounter_id}/differential", response_model=DifferentialResponse)
def generate_encounter_differential(
    encounter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    patient = encounter.patient
    vitals = encounter.nursing_observations
    family_hist = patient.family_history

    analysis = IntelligenceService.generate_encounter_differential(
        encounter=encounter,
        patient=patient,
        vitals=vitals,
        family_history=family_hist
    )

    # Persist as a ClinicalInsight for audit and clinician acceptance tracking
    insight = ClinicalInsight(
        patient_id=patient.id,
        encounter_id=encounter.id,
        insight_type="differential",
        title="AI-Assisted Differential Considerations & Findings Summary",
        content=analysis["summary_of_findings"],
        supporting_evidence=analysis["supporting_evidence"],
        conflicting_evidence=analysis["conflicting_evidence"],
        missing_data=analysis["missing_data_recommendations"],
        model_version=analysis["model_version"],
        safety_disclaimer=analysis["safety_disclaimer"],
        review_status=InsightReviewStatus.PENDING
    )
    db.add(insight)
    db.commit()

    log_audit_event(
        db,
        action="INTELLIGENCE_DIFFERENTIAL_GENERATED",
        resource_type="clinical_insight",
        resource_id=insight.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        metadata={"model_version": analysis["model_version"]}
    )

    return DifferentialResponse(
        encounter_id=encounter.id,
        patient_id=patient.id,
        summary_of_findings=analysis["summary_of_findings"],
        red_flags_detected=analysis["red_flags_detected"],
        possible_differentials=analysis["possible_differentials"],
        supporting_evidence=analysis["supporting_evidence"],
        conflicting_evidence=analysis["conflicting_evidence"],
        missing_data_recommendations=analysis["missing_data_recommendations"],
        model_version=analysis["model_version"],
        safety_disclaimer=analysis["safety_disclaimer"]
    )

# ----------------- Clinician Review & Disposition of Findings -----------------
@router.post("/insights/{id}/review")
def review_clinical_insight(
    id: str,
    review_in: InsightReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    """
    Clinician must explicitly accept, edit, or reject AI-generated drafts.
    Unaccepted AI output never automatically becomes part of signed documentation.
    """
    insight = db.query(ClinicalInsight).filter(ClinicalInsight.id == id).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Clinical insight not found")

    insight.review_status = review_in.action
    insight.reviewed_by_id = current_user.id
    insight.reviewed_at = get_utc_now()
    insight.clinician_action_rationale = review_in.rationale
    if review_in.edited_content:
        insight.content = review_in.edited_content

    db.commit()

    log_audit_event(
        db,
        action=f"AI_INSIGHT_{review_in.action.value.upper()}",
        resource_type="clinical_insight",
        resource_id=insight.id,
        actor_id=current_user.id,
        patient_id=insight.patient_id,
        encounter_id=insight.encounter_id,
        metadata={"rationale": review_in.rationale}
    )

    return {
        "status": "success",
        "message": f"Insight reviewed with action: {review_in.action.value}",
        "insight_id": insight.id,
        "review_status": insight.review_status.value
    }

# ----------------- NCS ML Model Dedicated Endpoints -----------------
@router.post("/ml/predict-heart-disease", response_model=MLPredictionResponse)
def predict_heart_disease_ml(
    input_data: HeartDiseaseMLInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.NURSE, UserRole.FACILITY_ADMIN]))
):
    """
    Executes inference via the NCS Model (heart_disease_prediction_pipeline.joblib).
    Does NOT modify the model folder; runs via NCSModelAdapter.
    """
    try:
        result = NCSModelAdapter.predict_heart_disease(input_data.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing NCS Heart Disease Pipeline: {str(e)}"
        )

    log_audit_event(
        db,
        action="NCS_ML_HEART_PREDICTION_EXECUTED",
        resource_type="ml_prediction",
        actor_id=current_user.id,
        metadata={
            "prediction": result["prediction"],
            "probability": result["probability"],
            "model_version": result["model_version"]
        }
    )

    return MLPredictionResponse(
        prediction=result["prediction"],
        probability=result["probability"],
        diagnosis=result["diagnosis"],
        model_version=result["model_version"],
        clinical_significance=result["clinical_significance"]
    )

@router.post("/ml/predict-diabetes", response_model=MLPredictionResponse)
def predict_diabetes_ml(
    input_data: DiabetesMLInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR, UserRole.NURSE, UserRole.FACILITY_ADMIN]))
):
    """
    Executes inference via the NCS Model (diabetes_prediction_pipeline.joblib).
    Does NOT modify the model folder; runs via NCSModelAdapter.
    """
    try:
        result = NCSModelAdapter.predict_diabetes(input_data.model_dump())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing NCS Diabetes Pipeline: {str(e)}"
        )

    log_audit_event(
        db,
        action="NCS_ML_DIABETES_PREDICTION_EXECUTED",
        resource_type="ml_prediction",
        actor_id=current_user.id,
        metadata={
            "prediction": result["prediction"],
            "probability": result["probability"],
            "model_version": result["model_version"]
        }
    )

    return MLPredictionResponse(
        prediction=result["prediction"],
        probability=result["probability"],
        diagnosis=result["diagnosis"],
        model_version=result["model_version"],
        clinical_significance=result["clinical_significance"]
    )




# ----------------- VITALIS AI: Longitudinal Clinical Assessment -----------------
@router.post("/encounters/{encounter_id}/assessment")
def generate_clinical_assessment(
    encounter_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.DOCTOR]))
):
    """
    Full VITALIS AI assessment for the current encounter: combines today's vitals and complaint
    with the patient's authorised network history, runs the trained NCS ML models and screens
    treatment options against documented allergies/medications. Persisted as a ClinicalInsight
    that the clinician must accept, edit or reject.
    """
    from app.services.clinical_ai import VitalisClinicalAI
    from app.services.record_access import resolve_access, visible_encounters

    encounter = db.query(Encounter).filter(Encounter.id == encounter_id).first()
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")
    patient = encounter.patient

    access = resolve_access(db, current_user, patient)
    visible = visible_encounters(patient, access)
    if encounter not in visible:
        visible = visible + [encounter]

    result = VitalisClinicalAI(patient, encounter, visible).assess()

    top = result["conditions"][0]["condition"] if result["conditions"] else "No specific pattern"
    insight = ClinicalInsight(
        patient_id=patient.id,
        encounter_id=encounter.id,
        insight_type="longitudinal_assessment",
        title=f"VITALIS AI assessment — {top}",
        content=result["summary"],
        supporting_evidence=[e["text"] for c in result["conditions"] for e in c.get("evidence", [])][:30],
        conflicting_evidence=[e["text"] for c in result["conditions"] for e in c.get("against", [])][:15],
        missing_data=result["missing_data"],
        model_version=result["model_version"][:50],
        safety_disclaimer=result["safety_disclaimer"][:255],
        review_status=InsightReviewStatus.PENDING
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)

    log_audit_event(
        db,
        action="INTELLIGENCE_ASSESSMENT_GENERATED",
        resource_type="clinical_insight",
        resource_id=insight.id,
        actor_id=current_user.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        metadata={
            "model_version": result["model_version"],
            "access_level": access["level"],
            "prior_encounters": result["data_coverage"]["prior_encounters"],
            "conditions": [c["condition"] for c in result["conditions"]],
        }
    )

    return {"insight_id": insight.id, "encounter_id": encounter.id, "patient_id": patient.id, **result}
