from typing import List, Dict, Any, Optional

# Verified medication safety reference knowledge base
# Used for pre-prescription allergy and interaction checks
KNOWN_ALLERGIES_MAP = {
    "penicillin": ["amoxicillin", "ampicillin", "augmentin", "co-amoxiclav", "piperacillin"],
    "sulfa": ["co-trimoxazole", "bactrim", "septrin", "sulfamethoxazole", "sulfadoxine", "hydrochlorothiazide", "chlorthalidone", "bendroflumethiazide", "indapamide", "furosemide"],
    "sulfonamide": ["co-trimoxazole", "bactrim", "septrin", "sulfamethoxazole", "sulfadoxine", "hydrochlorothiazide", "chlorthalidone", "bendroflumethiazide", "indapamide", "furosemide"],
    "co-trimoxazole": ["sulfamethoxazole", "septrin", "bactrim"],
    "aspirin": ["ibuprofen", "diclofenac", "naproxen", "ketorolac", "indomethacin"],  # NSAID cross-sensitivity
    "nsaids": ["aspirin", "ibuprofen", "diclofenac", "naproxen", "piroxicam"]
}

KNOWN_DRUG_INTERACTIONS = [
    {
        "drug_a": "ciprofloxacin",
        "drug_b": "artemether-lumefantrine",
        "severity": "Major",
        "detail": "Risk of additive QT prolongation and cardiac arrhythmia. Co-administration should be avoided."
    },
    {
        "drug_a": "warfarin",
        "drug_b": "aspirin",
        "severity": "Major",
        "detail": "Significantly increased risk of life-threatening gastrointestinal and systemic hemorrhage."
    },
    {
        "drug_a": "lisinopril",
        "drug_b": "spironolactone",
        "severity": "Moderate to Major",
        "detail": "Increased risk of severe hyperkalemia. Serum potassium monitoring is essential."
    },
    {
        "drug_a": "amlodipine",
        "drug_b": "simvastatin",
        "severity": "Moderate",
        "detail": "Amlodipine raises simvastatin exposure (myopathy risk). Limit simvastatin to 20 mg or prefer atorvastatin."
    },
    {
        "drug_a": "lisinopril",
        "drug_b": "potassium",
        "severity": "Moderate",
        "detail": "ACE inhibitor with potassium supplementation increases hyperkalaemia risk. Monitor serum potassium."
    },
    {
        "drug_a": "metformin",
        "drug_b": "radiocontrast agent",
        "severity": "Major",
        "detail": "Risk of contrast-induced acute kidney injury and lactic acidosis. Withhold metformin 48h prior."
    }
]

class MedicationSafetyChecker:
    @staticmethod
    def check_medication_safety(
        proposed_meds: List[str],
        patient_allergies: List[str],
        current_medications: List[str],
        patient_conditions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        allergy_conflicts = []
        drug_interactions = []
        contraindications = []

        proposed_clean = [m.lower().strip() for m in proposed_meds]
        allergies_clean = [a.lower().strip() for a in patient_allergies]
        current_clean = [c.lower().strip() for c in current_medications]
        conditions_clean = [cond.lower().strip() for cond in (patient_conditions or [])]

        # Allergy conflicts check
        for prop in proposed_clean:
            for allergy in allergies_clean:
                # Direct match
                if allergy in prop or prop in allergy:
                    allergy_conflicts.append({
                        "proposed_medication": prop,
                        "documented_allergy": allergy,
                        "warning": f"Direct allergy conflict: Patient has documented allergy to '{allergy}'."
                    })
                # Cross-sensitivity check (allergy text may be descriptive, e.g. "Sulfonamides (Septrin)")
                else:
                    flagged = False
                    for allergy_key, derivatives in KNOWN_ALLERGIES_MAP.items():
                        if flagged or allergy_key not in allergy:
                            continue
                        for d in derivatives:
                            if d in prop:
                                allergy_conflicts.append({
                                    "proposed_medication": prop,
                                    "documented_allergy": allergy,
                                    "warning": f"Cross-reactivity risk: '{prop}' belongs to or shares cross-sensitivity with '{allergy}'."
                                })
                                flagged = True
                                break

        # Drug-Drug Interactions
        all_meds = proposed_clean + current_clean
        for rule in KNOWN_DRUG_INTERACTIONS:
            da = rule["drug_a"].lower()
            db = rule["drug_b"].lower()
            # If one is in proposed and one is in current/proposed
            has_da = any(da in m for m in all_meds)
            has_db = any(db in m for m in all_meds)
            if has_da and has_db:
                drug_interactions.append({
                    "interacting_pair": f"{rule['drug_a']} + {rule['drug_b']}",
                    "severity": rule["severity"],
                    "clinical_significance": rule["detail"]
                })

        # Disease-Drug Contraindications
        for prop in proposed_clean:
            if "peptic ulcer" in conditions_clean or "gastric ulcer" in conditions_clean:
                if any(nsaid in prop for nsaid in ["aspirin", "ibuprofen", "diclofenac", "piroxicam"]):
                    contraindications.append({
                        "proposed_medication": prop,
                        "condition": "Peptic Ulcer Disease",
                        "warning": "NSAIDs are contraindicated due to risk of gastric perforation and bleeding."
                    })
            if "chronic kidney disease" in conditions_clean or "renal impairment" in conditions_clean:
                if "metformin" in prop or "gentamicin" in prop:
                    contraindications.append({
                        "proposed_medication": prop,
                        "condition": "Renal Impairment",
                        "warning": "Dose adjustment or alternative agent required due to renal clearance concerns."
                    })

        is_safe = (len(allergy_conflicts) == 0 and len([i for i in drug_interactions if i["severity"] == "Major"]) == 0)

        return {
            "allergy_conflicts": allergy_conflicts,
            "drug_interactions": drug_interactions,
            "contraindications_and_warnings": contraindications,
            "is_safe_to_proceed": is_safe,
            "reference_source": "VITALIS Curated Clinical Safety Formulary & BNF/WHO Standard 2026.1",
            "disclaimer": "Decision support alert only. Prescribing authorization and clinical responsibility remain with the attending physician."
        }

