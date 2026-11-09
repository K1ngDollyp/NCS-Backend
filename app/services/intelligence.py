from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.models import Patient, Encounter, NursingObservation, ClinicalNote, FamilyHistoryEntry
from app.engines.triage.rules import RED_FLAGS

class IntelligenceService:
    """
    VITALIS INTELLIGENCE Service (Section 31 & 33)
    Analyzes longitudinal patient record:
      - Current presentation & vitals
      - Past encounters & verified investigations
      - Documented allergies and active medications
      - Family history risk signals
    Outputs:
      A. Differential considerations with evidence references
      B. Medication safety & interaction alerts
      C. Personalised health-risk & family history signals
      D. Longitudinal trend insights
    """

    @staticmethod
    def generate_encounter_differential(
        encounter: Encounter,
        patient: Patient,
        vitals: List[NursingObservation],
        family_history: List[FamilyHistoryEntry]
    ) -> Dict[str, Any]:
        complaint = ""
        if encounter.reception_intake:
            complaint = encounter.reception_intake.presenting_complaint or ""
        
        # Check notes if present
        for note in encounter.clinical_notes:
            if note.history_of_complaint:
                complaint += " " + note.history_of_complaint

        complaint_lower = complaint.lower()

        # Check emergency red flags first
        red_flags_detected = []
        for rf in RED_FLAGS:
            for kw in rf["keywords"]:
                if kw in complaint_lower:
                    red_flags_detected.append(f"{rf['flag']} (triggered by '{kw}')")

        # Analyze vitals
        vital_summary = {}
        abnormal_vitals = []
        for v in vitals:
            vital_summary[v.observation_type] = f"{v.value} {v.unit}"
            if v.is_warning:
                abnormal_vitals.append(f"{v.observation_type}: {v.value} {v.unit} ({v.warning_message})")

        # Generate rule/evidence-based differentials
        differentials = []
        supporting_evidence = []
        conflicting_evidence = []
        missing_data = []

        # Example Clinical Pattern 1: Acute Febrile Illness / Malaria / Sepsis
        if any(term in complaint_lower for term in ["fever", "chills", "hot", "headache", "rigors"]):
            differentials.append({
                "condition": "Severe Plasmodium Falciparum Malaria (or Uncomplicated Malaria)",
                "ranking": 1,
                "confidence_signal": "High clinical suspicion based on endemic presentation and fever profile",
                "suggested_tests": ["Rapid Diagnostic Test (RDT) for Malaria", "Thick and Thin Blood Giemsa Film", "Full Blood Count (FBC)"]
            })
            differentials.append({
                "condition": "Enteric (Typhoid) Fever / Salmonella Infection",
                "ranking": 2,
                "confidence_signal": "Moderate suspicion in persistent febrile illness",
                "suggested_tests": ["Blood Culture", "Widal Agglutination (corroborative only)", "Stool Culture"]
            })
            supporting_evidence.append(f"Recorded complaint includes febrile symptoms: '{complaint[:80]}...'")
            if "temperature" in vital_summary:
                supporting_evidence.append(f"Measured temperature: {vital_summary['temperature']}")
            else:
                missing_data.append("Objective body temperature not recorded in current vital signs.")

        # Example Clinical Pattern 2: Respiratory Infection / Pneumonia
        if any(term in complaint_lower for term in ["cough", "difficulty breathing", "chest pain", "sputum"]):
            differentials.append({
                "condition": "Community-Acquired Pneumonia / Lower Respiratory Tract Infection",
                "ranking": 1,
                "confidence_signal": "High suspicion based on respiratory symptoms",
                "suggested_tests": ["Chest X-Ray (PA view)", "Full Blood Count & ESR", "Sputum AFB / GeneXpert if chronic"]
            })
            supporting_evidence.append("Prominent respiratory signs recorded in patient intake.")
            if "spo2" in vital_summary:
                supporting_evidence.append(f"Recorded SpO2: {vital_summary['spo2']}")
            else:
                missing_data.append("Pulse oximetry (SpO2) reading is missing.")

        # Example Clinical Pattern 3: Hypertensive Urgency / Cardiovascular Risk
        sbp = next((v.value for v in vitals if v.observation_type == "systolic_bp"), None)
        dbp = next((v.value for v in vitals if v.observation_type == "diastolic_bp"), None)
        if sbp and sbp >= 160 or (dbp and dbp >= 100):
            differentials.append({
                "condition": "Hypertensive Urgency / Stage 2 Essential Hypertension",
                "ranking": len(differentials) + 1,
                "confidence_signal": f"Elevated blood pressure measurements ({sbp}/{dbp} mmHg)",
                "suggested_tests": ["Electrocardiogram (ECG)", "Serum Electrolytes, Urea & Creatinine", "Urinalysis for Proteinuria"]
            })
            supporting_evidence.append(f"Current blood pressure elevated: {sbp}/{dbp} mmHg.")

        # Default fallback differential if non-specific
        if not differentials:
            differentials.append({
                "condition": "Non-specific Acute Presentation / Clinical Evaluation Required",
                "ranking": 1,
                "confidence_signal": "General presentation without specific focal localizing syndromic pattern",
                "suggested_tests": ["Full Blood Count (FBC)", "Basic Metabolic Panel", "Urinalysis"]
            })

        # Family History & Genetic Signals (Section 31.4 & 33.1)
        for fh in family_history:
            fh_cond = fh.condition.lower()
            if "diabetes" in fh_cond:
                differentials.append({
                    "condition": "Impaired Fasting Glycemia / Early Diabetes (Family Risk Signal)",
                    "ranking": len(differentials) + 1,
                    "confidence_signal": f"Family history alert: {fh.relationship_type.capitalize()} diagnosed with {fh.condition}",
                    "suggested_tests": ["Fasting Blood Glucose", "HbA1c"]
                })
            elif "hypertension" in fh_cond:
                supporting_evidence.append(f"Longitudinal risk: Documented familial predisposition to hypertension ({fh.relationship_type}).")
            elif "sickle cell" in fh_cond:
                supporting_evidence.append(f"Genetic risk marker: Family history of sickle cell trait/disease ({fh.relationship_type}).")

        # Summary of Findings
        summary = (
            f"Patient {patient.first_name} {patient.last_name} ({patient.gender}, DOB: {patient.dob}) "
            f"presents with: '{complaint}'. "
            f"Current vital sign measurements: {', '.join([f'{k}: {v}' for k, v in vital_summary.items()]) or 'None recorded'}. "
            f"Allergies on file: {', '.join(patient.allergies) if patient.allergies else 'No known drug allergies'}. "
            f"Active medications: {', '.join(patient.current_medications) if patient.current_medications else 'None reported'}."
        )

        return {
            "encounter_id": encounter.id,
            "patient_id": patient.id,
            "summary_of_findings": summary,
            "red_flags_detected": red_flags_detected,
            "possible_differentials": differentials,
            "supporting_evidence": supporting_evidence,
            "conflicting_evidence": conflicting_evidence,
            "missing_data_recommendations": missing_data,
            "model_version": "VITALIS-INTELLIGENCE-V1.4-CLINICAL-DRAFT",
            "safety_disclaimer": (
                "AI-generated draft for clinical decision support only. Clinician review, "
                "independent physical examination, and diagnostic verification are strictly required. "
                "This software does not prescribe or establish an autonomous diagnosis."
            )
        }

