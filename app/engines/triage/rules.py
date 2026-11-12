from typing import List, Dict, Any, Tuple

# Deterministic Emergency Red-Flag triggers
# Evaluated immediately to prevent triage delays
RED_FLAGS = [
    {
        "keywords": ["chest pain", "tightness in chest", "pressure in chest", "radiating to arm", "radiating to jaw"],
        "flag": "Potential Acute Coronary Syndrome / Myocardial Infarction",
        "urgency": "EMERGENCY_RED",
        "service": "Emergency Resuscitation & Cardiology Unit",
        "guidance": "CRITICAL EMERGENCY: Immediate clinical evaluation and resuscitation required. Do not wait."
    },
    {
        "keywords": ["difficulty breathing", "severe shortness of breath", "gasping", "unable to speak full sentences", "stridor"],
        "flag": "Severe Respiratory Distress",
        "urgency": "EMERGENCY_RED",
        "service": "Emergency Resuscitation / Respiratory Unit",
        "guidance": "CRITICAL EMERGENCY: Severe airway/breathing compromise. Requires urgent oxygenation and clinical stabilization."
    },
    {
        "keywords": ["loss of consciousness", "syncope", "unresponsive", "sudden weakness on one side", "facial droop", "slurred speech"],
        "flag": "Acute Neurological Deficit / Stroke Protocol",
        "urgency": "EMERGENCY_RED",
        "service": "Emergency / Neurology Stroke Team",
        "guidance": "CRITICAL EMERGENCY: Suspected acute stroke or intracranial event. Time-critical emergency response required."
    },
    {
        "keywords": ["severe bleeding", "hemorrhage", "vomiting blood", "coughing blood", "hematemesis"],
        "flag": "Acute Major Hemorrhage / Hemodynamic Instability",
        "urgency": "EMERGENCY_RED",
        "service": "Emergency Surgical / Trauma Unit",
        "guidance": "CRITICAL EMERGENCY: Major blood loss. Immediate IV access and surgical/hemodynamic evaluation needed."
    },
    {
        "keywords": ["high fever with stiff neck", "fever with confusion", "petechial rash", "photophobia"],
        "flag": "Suspected Meningitis / Central Nervous System Sepsis",
        "urgency": "EMERGENCY_RED",
        "service": "Emergency Medicine / Infectious Disease",
        "guidance": "CRITICAL EMERGENCY: Meningeal signs detected. Urgent lumbar puncture and intravenous antimicrobials indicated."
    }
]

URGENT_YELLOW_TRIGGERS = [
    {
        "keywords": ["high fever", "persistent fever", "chills", "rigors", "severe headache"],
        "flag": "Acute Febrile Illness / Suspected Severe Malaria or Typhoid",
        "urgency": "URGENT_YELLOW",
        "service": "General Outpatient / Internal Medicine",
        "guidance": "URGENT ATTENTION: Same-day medical evaluation and diagnostic testing (Malaria RDT/Microscopy) recommended."
    },
    {
        "keywords": ["severe abdominal pain", "right lower quadrant pain", "vomiting and diarrhea", "rebound tenderness"],
        "flag": "Acute Abdomen / Possible Appendicitis or Gastroenteritis with dehydration",
        "urgency": "URGENT_YELLOW",
        "service": "General Surgery / Acute Care Clinic",
        "guidance": "URGENT ATTENTION: Needs prompt surgical/medical examination within 2-4 hours."
    },
    {
        "keywords": ["joint pain with swelling", "sickle cell pain", "bone crisis"],
        "flag": "Vaso-occlusive Crisis / Acute Arthropathy",
        "urgency": "URGENT_YELLOW",
        "service": "Hematology / Acute Pain Management",
        "guidance": "URGENT ATTENTION: Prompt analgesia, hydration and clinician evaluation recommended."
    }
]

class TriageEngine:
    @staticmethod
    def evaluate_symptoms(symptoms: List[Dict[str, Any]]) -> Tuple[str, List[str], str, str]:
        """
        Deterministic, rule-based triage assessment.
        Returns: (urgency_level, matched_red_flags, recommended_service, recommendation_summary)
        """
        combined_text = " ".join([
            f"{s.get('symptom', '')} {s.get('details', '')}".lower() 
            for s in symptoms
        ])
        
        matched_red_flags = []
        
        # Check emergency red flags first
        for rf in RED_FLAGS:
            for kw in rf["keywords"]:
                if kw in combined_text:
                    matched_red_flags.append(f"{rf['flag']} (triggered by '{kw}')")
                    return (
                        "EMERGENCY_RED",
                        matched_red_flags,
                        rf["service"],
                        rf["guidance"]
                    )
                    
        # Check urgent yellow triggers
        matched_yellow = []
        for uy in URGENT_YELLOW_TRIGGERS:
            for kw in uy["keywords"]:
                if kw in combined_text:
                    matched_yellow.append(f"{uy['flag']} (triggered by '{kw}')")
                    return (
                        "URGENT_YELLOW",
                        matched_yellow,
                        uy["service"],
                        uy["guidance"]
                    )
                    
        # Routine Green fallback
        return (
            "ROUTINE_GREEN",
            [],
            "Primary Care / General Outpatient Department",
            "Routine clinical consultation recommended. No acute emergency red flags identified at intake."
        )

# Clinician vital sign warning thresholds
# Triggers alerts on the nursing triage station
VITAL_WARNING_THRESHOLDS = {
    "systolic_bp": {"min": 90, "max": 140, "unit": "mmHg", "label": "Systolic Blood Pressure"},
    "diastolic_bp": {"min": 60, "max": 90, "unit": "mmHg", "label": "Diastolic Blood Pressure"},
    "pulse_rate": {"min": 50, "max": 100, "unit": "bpm", "label": "Pulse / Heart Rate"},
    "respiratory_rate": {"min": 12, "max": 22, "unit": "cpm", "label": "Respiratory Rate"},
    "temperature": {"min": 36.0, "max": 37.8, "unit": "degC", "label": "Body Temperature"},
    "spo2": {"min": 94, "max": 100, "unit": "%", "label": "Oxygen Saturation (SpO2)"},
    "pain_score": {"min": 0, "max": 6, "unit": "/10", "label": "Pain Score"},
    "blood_glucose": {"min": 70, "max": 140, "unit": "mg/dL", "label": "Random Blood Glucose (POC)"}
}

def check_vital_warning(observation_type: str, value: float) -> Tuple[bool, Optional[str]]:
    threshold = VITAL_WARNING_THRESHOLDS.get(observation_type.lower())
    if not threshold:
        return False, None
    
    label = threshold["label"]
    unit = threshold["unit"]
    
    if value < threshold["min"]:
        return True, f"Abnormal low {label}: {value} {unit} (Normal range: {threshold['min']}-{threshold['max']} {unit})"
    elif value > threshold["max"]:
        return True, f"Abnormal elevated {label}: {value} {unit} (Normal range: {threshold['min']}-{threshold['max']} {unit})"
        
    return False, None

