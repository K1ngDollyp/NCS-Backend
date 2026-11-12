"""
VITALIS AI — longitudinal clinical decision support.

Combines, for one encounter:
  * today's presenting complaint and nursing vital signs
  * every prior encounter the facility is authorised to see (across the network)
  * laboratory history, chronic conditions, medications, allergies, family history
  * the trained NCS machine-learning risk models (diabetes, heart disease)

and produces ranked, evidence-linked possible conditions with qualified
likelihoods, red flags, trends, suggested investigations and medication options
that are pre-screened against the patient's documented allergies/medications.

It is a clinician-facing decision-support tool: it never diagnoses or prescribes.
"""
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.engines.triage.rules import RED_FLAGS
from app.models.models import Encounter, Patient
from app.services.medication_safety import MedicationSafetyChecker
from app.services.ncs_model_adapter import NCSModelAdapter
from app.services.record_serializer import patient_age

MODEL_VERSION = "VITALIS-AI-2026.2 (clinical rules + NCS-SVC-DiabetesV1 + NCS-RF-HeartV1)"

SAFETY_DISCLAIMER = (
    "Clinical decision support only. Likelihoods are qualified estimates from documented data and "
    "must be confirmed by examination and investigation. VITALIS AI does not diagnose or prescribe; "
    "the attending clinician makes and owns every decision."
)

LABEL = {
    "systolic_bp": "Systolic BP", "diastolic_bp": "Diastolic BP", "pulse_rate": "Pulse",
    "respiratory_rate": "Respiratory rate", "temperature": "Temperature", "spo2": "SpO₂",
    "weight": "Weight", "height": "Height", "blood_glucose": "Blood glucose (POC)", "pain_score": "Pain score",
}


# ----------------------------------------------------------------- helpers
def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_date(dt: Optional[datetime]) -> str:
    return _aware(dt).strftime("%d %b %Y") if dt else "date unknown"


def _short_fac(name: Optional[str]) -> str:
    if not name:
        return "Unknown facility"
    return name.replace("Federal Medical Centre (FMC), Abeokuta", "FMC Abeokuta").replace(", Abeokuta", "")


def _has(text: str, words: List[str]) -> List[str]:
    return [w for w in words if w in text]


def _likelihood(score: float) -> float:
    return max(0.05, min(0.95, 1 - math.exp(-score / 4.0)))


def _label(p: float) -> str:
    if p >= 0.7:
        return "High"
    if p >= 0.4:
        return "Moderate"
    return "Low"


def _to_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


LAB_KEYS = [
    ("hba1c", lambda p: "hba1c" in p or "a1c" in p),
    ("fbs", lambda p: "fasting" in p and ("glucose" in p or "sugar" in p)),
    ("rbs", lambda p: "random" in p and ("glucose" in p or "sugar" in p)),
    ("ldl", lambda p: "ldl" in p),
    ("hdl", lambda p: "hdl" in p),
    ("triglycerides", lambda p: "triglyceride" in p),
    ("chol", lambda p: "cholesterol" in p and "ldl" not in p and "hdl" not in p),
    ("hb", lambda p: p in ("hb", "haemoglobin", "hemoglobin") or p.startswith("haemoglobin") or p.startswith("hemoglobin")),
    ("creatinine", lambda p: "creatinine" in p),
    ("malaria", lambda p: "malaria" in p or "mp" == p),
    ("wbc", lambda p: "wbc" in p or "white cell" in p),
    ("urine_protein", lambda p: "protein" in p and "urin" in p),
]


def _lab_key(param: str) -> Optional[str]:
    p = param.lower().strip()
    for key, fn in LAB_KEYS:
        if fn(p):
            return key
    return None


# ----------------------------------------------------------------- engine
class VitalisClinicalAI:

    def __init__(self, patient: Patient, encounter: Encounter, visible: List[Encounter]):
        self.patient = patient
        self.encounter = encounter
        self.prior = sorted(
            [e for e in visible if e.id != encounter.id],
            key=lambda e: _aware(e.opened_at),
        )
        self.all_visible = self.prior + [encounter]
        self.age = patient_age(patient)
        self.female = (patient.gender or "").lower().startswith("f")
        self.trace: List[str] = []
        self.missing: List[str] = []
        self.here = _short_fac(encounter.facility.name if encounter.facility else None)

        # Complaint text (today)
        parts = []
        if encounter.reception_intake:
            parts.append(encounter.reception_intake.presenting_complaint or "")
        for n in encounter.clinical_notes:
            parts += [n.history_of_complaint or "", n.examination_findings or ""]
        self.complaint = " ".join(p for p in parts if p).strip()
        self.text = self.complaint.lower()

        # Today's vitals (latest per type)
        self.vitals: Dict[str, float] = {}
        for v in sorted(encounter.nursing_observations, key=lambda v: _aware(v.measured_at)):
            self.vitals[v.observation_type] = v.value

        # Historical vital series per type: list of (date, value, facility)
        self.vital_hist: Dict[str, List[Tuple[datetime, float, str]]] = {}
        for e in self.all_visible:
            for v in e.nursing_observations:
                self.vital_hist.setdefault(v.observation_type, []).append(
                    (_aware(v.measured_at) or _aware(e.opened_at), v.value, _short_fac(e.facility.name if e.facility else None))
                )
        for k in self.vital_hist:
            self.vital_hist[k].sort(key=lambda x: x[0])

        # Labs: key -> list of dict(value, unit, date, facility, test, flag)
        self.labs: Dict[str, List[Dict[str, Any]]] = {}
        for e in self.all_visible:
            for o in e.investigation_orders:
                lab = o.lab_result
                if not lab or not isinstance(lab.result_payload, dict):
                    continue
                when = _aware(lab.verified_at or lab.entered_at or o.ordered_at)
                for param, res in lab.result_payload.items():
                    key = _lab_key(param)
                    if not key:
                        continue
                    raw = res.get("value") if isinstance(res, dict) else res
                    self.labs.setdefault(key, []).append({
                        "value": raw, "num": _to_float(raw),
                        "unit": res.get("unit") if isinstance(res, dict) else None,
                        "date": when, "facility": _short_fac(e.facility.name if e.facility else None),
                        "test": o.test_or_modality, "param": param,
                        "today": e.id == encounter.id,
                    })
        for k in self.labs:
            self.labs[k].sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc))

        # Note corpus for provenance lookups
        self.notes = []
        for e in self.all_visible:
            blob = []
            if e.reception_intake:
                blob.append(e.reception_intake.presenting_complaint or "")
            for n in e.clinical_notes:
                blob += [n.history_of_complaint or "", n.examination_findings or "", n.assessment or "", n.clinical_plan or ""]
            self.notes.append((e, " ".join(blob).lower()))

        self.conditions_lc = [c.lower() for c in (patient.chronic_conditions or [])]
        self.meds_lc = [m.lower() for m in (patient.current_medications or [])]
        self.family = list(patient.family_history or [])

    # ------------------------------------------------------------ provenance
    def provenance(self, item: str) -> Optional[str]:
        word = re.split(r"[\s(/,]+", item.lower().strip())[0]
        stem = word[:-1] if word.endswith("s") and len(word) > 5 else word
        for e, blob in self.notes:
            if stem and stem in blob:
                when = "today" if e.id == self.encounter.id else _fmt_date(e.opened_at)
                return f"{_short_fac(e.facility.name if e.facility else None)} · {when}"
        return None

    def src_today(self, what: str = "nursing vitals") -> str:
        return f"Today · {self.here} ({what})"

    def src_lab(self, lab: Dict[str, Any]) -> str:
        return f"Today · {lab['facility']} (lab)" if lab["today"] else f"{lab['facility']} · {_fmt_date(lab['date'])} (lab)"

    def latest_lab(self, key: str) -> Optional[Dict[str, Any]]:
        vals = [l for l in self.labs.get(key, []) if l["num"] is not None]
        return vals[-1] if vals else None

    def bmi(self) -> Optional[float]:
        w = self.vitals.get("weight") or (self.vital_hist.get("weight", [])[-1][1] if self.vital_hist.get("weight") else None)
        h = self.vitals.get("height") or (self.vital_hist.get("height", [])[-1][1] if self.vital_hist.get("height") else None)
        if w and h:
            return round(w / ((h / 100) ** 2), 1)
        return None

    def glucose_now(self) -> Optional[Tuple[float, str]]:
        if "blood_glucose" in self.vitals:
            return self.vitals["blood_glucose"], self.src_today("point-of-care glucose")
        for key in ("rbs", "fbs"):
            lab = self.latest_lab(key)
            if lab:
                return lab["num"], self.src_lab(lab)
        return None

    def family_with(self, words: List[str]):
        return [f for f in self.family if any(w in (f.condition or "").lower() for w in words)]

    # ------------------------------------------------------------ trends
    def trends(self) -> List[Dict[str, Any]]:
        out = []
        specs = [
            ("systolic_bp", "Systolic blood pressure", "mmHg", 8),
            ("diastolic_bp", "Diastolic blood pressure", "mmHg", 6),
            ("weight", "Body weight", "kg", 2),
            ("blood_glucose", "Blood glucose (POC)", "mg/dL", 20),
        ]
        for key, label, unit, delta in specs:
            pts = self.vital_hist.get(key, [])
            if len(pts) >= 2:
                first, last = pts[0][1], pts[-1][1]
                direction = "rising" if last - first >= delta else "falling" if first - last >= delta else "stable"
                out.append({
                    "metric": key, "label": label, "unit": unit, "direction": direction,
                    "points": [{"date": d.isoformat(), "value": v, "facility": f} for d, v, f in pts],
                    "text": f"{label} {direction}: " + " → ".join(f"{v:g}" for _, v, _ in pts) + f" {unit} across {len({f for _, _, f in pts})} facilities",
                })
        for key, label, unit, delta in [("fbs", "Fasting blood glucose", "mg/dL", 10), ("hba1c", "HbA1c", "%", 0.3), ("chol", "Total cholesterol", "mg/dL", 15)]:
            pts = [l for l in self.labs.get(key, []) if l["num"] is not None]
            if len(pts) >= 2:
                first, last = pts[0]["num"], pts[-1]["num"]
                direction = "rising" if last - first >= delta else "falling" if first - last >= delta else "stable"
                out.append({
                    "metric": key, "label": label, "unit": unit, "direction": direction,
                    "points": [{"date": l["date"].isoformat() if l["date"] else None, "value": l["num"], "facility": l["facility"]} for l in pts],
                    "text": f"{label} {direction}: " + " → ".join(f"{l['num']:g}" for l in pts) + f" {unit}",
                })
        return out

    # ------------------------------------------------------------ ML models
    def run_diabetes_model(self) -> Optional[Dict[str, Any]]:
        g = self.glucose_now()
        dbp = self.vitals.get("diastolic_bp")
        bmi = self.bmi()
        if not g or self.age is None:
            self.missing.append("Blood glucose not available — NCS diabetes risk model not run (record a point-of-care glucose).")
            return None
        fam = self.family_with(["diabetes"])
        first_degree = [f for f in fam if (f.relationship_type or "").lower() in ("mother", "father", "sibling", "brother", "sister", "child", "son", "daughter")]
        dpf = round(min(1.5, 0.25 + 0.35 * len(first_degree) + 0.15 * (len(fam) - len(first_degree))), 2)
        inputs = [
            {"feature": "Glucose", "label": "Plasma glucose", "value": g[0], "source": "measured", "detail": g[1]},
            {"feature": "BloodPressure", "label": "Diastolic BP", "value": dbp if dbp else 72.0, "source": "measured" if dbp else "assumed", "detail": self.src_today() if dbp else "Not recorded — population mean used"},
            {"feature": "BMI", "label": "Body-mass index", "value": bmi if bmi else 27.0, "source": "derived" if bmi else "assumed", "detail": "Weight ÷ height² from nursing record" if bmi else "Not recorded — population mean used"},
            {"feature": "Age", "label": "Age", "value": self.age, "source": "record", "detail": "Date of birth on VITALIS profile"},
            {"feature": "DiabetesPedigreeFunction", "label": "Family diabetes risk", "value": dpf, "source": "derived", "detail": f"{len(first_degree)} first-degree relative(s) with diabetes in family history"},
            {"feature": "Pregnancies", "label": "Pregnancies", "value": 0, "source": "assumed", "detail": "Not recorded"},
            {"feature": "SkinThickness", "label": "Skin-fold thickness", "value": 0, "source": "imputed", "detail": "Not measured — imputed by model pipeline"},
            {"feature": "Insulin", "label": "Serum insulin", "value": 0, "source": "imputed", "detail": "Not measured — imputed by model pipeline"},
        ]
        try:
            res = NCSModelAdapter.predict_diabetes({i["feature"]: i["value"] for i in inputs})
        except Exception as exc:  # model file missing etc.
            self.trace.append(f"NCS diabetes model unavailable ({exc.__class__.__name__}); continuing with clinical rules.")
            return None
        measured = sum(1 for i in inputs if i["source"] in ("measured", "derived", "record"))
        self.trace.append(f"Ran NCS-SVC-DiabetesV1 on {measured}/8 documented inputs → risk probability {res['probability']*100:.0f}%.")
        return {
            "key": "diabetes", "name": "Type 2 diabetes risk", "model_version": res["model_version"],
            "algorithm": "Support Vector Classifier (trained by the VITALIS team, Pima Indians Diabetes dataset)",
            "probability": res["probability"], "prediction": res["prediction"], "label": res["diagnosis"],
            "inputs": inputs, "measured_inputs": measured, "total_inputs": len(inputs),
        }

    def run_heart_model(self) -> Optional[Dict[str, Any]]:
        sbp = self.vitals.get("systolic_bp")
        if not sbp or self.age is None:
            return None
        chol = self.latest_lab("chol")
        g = self.glucose_now()
        fbs_lab = self.latest_lab("fbs")
        chest = bool(_has(self.text, ["chest pain", "chest tightness", "angina"]))
        inputs = [
            {"feature": "age", "label": "Age", "value": self.age, "source": "record", "detail": "VITALIS profile"},
            {"feature": "sex", "label": "Sex", "value": 0 if self.female else 1, "source": "record", "detail": self.patient.gender},
            {"feature": "trestbps", "label": "Resting systolic BP", "value": sbp, "source": "measured", "detail": self.src_today()},
            {"feature": "chol", "label": "Serum cholesterol", "value": chol["num"] if chol else 200.0, "source": "measured" if chol else "assumed", "detail": self.src_lab(chol) if chol else "No lipid profile on record — population mean used"},
            {"feature": "fbs", "label": "Fasting glucose > 120 mg/dL", "value": 1 if (fbs_lab and fbs_lab["num"] > 120) or (g and g[0] > 200) else 0, "source": "measured" if (fbs_lab or g) else "assumed", "detail": self.src_lab(fbs_lab) if fbs_lab else (g[1] if g else "Not recorded")},
            {"feature": "cp", "label": "Chest pain type", "value": 1 if chest else 0, "source": "derived", "detail": "From presenting complaint"},
            {"feature": "thalach", "label": "Max heart rate", "value": float(220 - self.age), "source": "assumed", "detail": "No exercise test — age-predicted maximum used"},
            {"feature": "restecg", "label": "Resting ECG", "value": 0, "source": "assumed", "detail": "ECG not on record — normal assumed"},
            {"feature": "exang", "label": "Exercise angina", "value": 0, "source": "assumed", "detail": "No exercise test"},
            {"feature": "oldpeak", "label": "ST depression", "value": 0.0, "source": "assumed", "detail": "No exercise ECG"},
            {"feature": "slope", "label": "ST slope", "value": 2, "source": "assumed", "detail": "No exercise ECG"},
            {"feature": "ca", "label": "Vessels on fluoroscopy", "value": 0, "source": "assumed", "detail": "No angiography"},
            {"feature": "thal", "label": "Thallium scan", "value": 2, "source": "assumed", "detail": "Not performed"},
        ]
        try:
            res = NCSModelAdapter.predict_heart_disease({i["feature"]: i["value"] for i in inputs})
        except Exception as exc:
            self.trace.append(f"NCS heart model unavailable ({exc.__class__.__name__}).")
            return None
        measured = sum(1 for i in inputs if i["source"] in ("measured", "derived", "record"))
        self.trace.append(f"Ran NCS-RF-HeartV1 cardiovascular screen on {measured}/13 documented inputs (screening only).")
        return {
            "key": "heart", "name": "Cardiovascular disease screen", "model_version": res["model_version"],
            "algorithm": "Random Forest (1,119 trees, trained by the VITALIS team, UCI Heart Disease dataset)",
            "probability": res["probability"], "prediction": res["prediction"], "label": res["diagnosis"],
            "inputs": inputs, "measured_inputs": measured, "total_inputs": len(inputs),
            "note": "Several exercise-test inputs are not available outside a cardiology work-up, so this screen is indicative only. An ECG and lipid profile improve it.",
        }

    # ------------------------------------------------------------ red flags
    def red_flags(self) -> List[Dict[str, str]]:
        v, flags = self.vitals, []
        sbp, dbp = v.get("systolic_bp"), v.get("diastolic_bp")
        organ_sx = _has(self.text, ["blurred vision", "blurring", "visual", "severe headache", "headache", "chest pain", "confusion", "weakness", "breathless", "shortness of breath", "nosebleed"])
        if (sbp and sbp >= 180) or (dbp and dbp >= 120):
            flags.append({"severity": "critical", "title": "Severe hypertension", "detail": f"BP {sbp:g}/{dbp:g} mmHg.", "action": "Repeat BP after 5 min rest; assess urgently for hypertensive emergency (target-organ damage)."})
        elif ((sbp and sbp >= 160) or (dbp and dbp >= 100)) and organ_sx:
            flags.append({"severity": "high", "title": "Markedly raised BP with possible target-organ symptoms", "detail": f"BP {sbp:g}/{dbp:g} mmHg with {', '.join(organ_sx[:3])}.", "action": "Same-visit review: fundoscopy, urinalysis for protein, ECG and serum creatinine to exclude hypertensive emergency."})
        if v.get("spo2") is not None and v["spo2"] < 92:
            flags.append({"severity": "critical", "title": "Hypoxaemia", "detail": f"SpO₂ {v['spo2']:g}%.", "action": "Give oxygen, assess airway and breathing immediately."})
        if v.get("temperature") is not None and v["temperature"] >= 39.5:
            flags.append({"severity": "high", "title": "High fever", "detail": f"{v['temperature']:g} °C.", "action": "Screen for sepsis and severe malaria."})
        if v.get("pulse_rate") is not None and (v["pulse_rate"] >= 130 or v["pulse_rate"] < 40):
            flags.append({"severity": "critical", "title": "Critical heart rate", "detail": f"{v['pulse_rate']:g} bpm.", "action": "ECG and immediate clinical review."})
        if v.get("respiratory_rate") is not None and v["respiratory_rate"] >= 30:
            flags.append({"severity": "critical", "title": "Severe tachypnoea", "detail": f"RR {v['respiratory_rate']:g}/min.", "action": "Immediate respiratory assessment."})
        g = v.get("blood_glucose")
        if g is not None and g >= 300:
            flags.append({"severity": "high", "title": "Severe hyperglycaemia", "detail": f"Glucose {g:g} mg/dL.", "action": "Check urine/serum ketones; assess hydration (exclude DKA/HHS)."})
        if g is not None and g < 70:
            flags.append({"severity": "critical", "title": "Hypoglycaemia", "detail": f"Glucose {g:g} mg/dL.", "action": "Give glucose now; recheck in 15 minutes."})
        for rf in RED_FLAGS:
            hit = _has(self.text, rf["keywords"])
            if hit:
                flags.append({"severity": "critical", "title": rf["flag"], "detail": f"Complaint mentions '{hit[0]}'.", "action": rf["guidance"]})
        return flags

    # ------------------------------------------------------------ conditions
    def _hypertension(self) -> Optional[Dict[str, Any]]:
        sbp, dbp = self.vitals.get("systolic_bp"), self.vitals.get("diastolic_bp")
        score, ev, against = 0.0, [], []
        if sbp and dbp:
            if sbp >= 160 or dbp >= 100:
                score += 3.5
                ev.append({"text": f"BP {sbp:g}/{dbp:g} mmHg today — stage 2 range", "source": self.src_today(), "kind": "current"})
            elif sbp >= 140 or dbp >= 90:
                score += 2.0
                ev.append({"text": f"BP {sbp:g}/{dbp:g} mmHg today — stage 1 range", "source": self.src_today(), "kind": "current"})
            else:
                against.append({"text": f"BP {sbp:g}/{dbp:g} mmHg today is within target", "source": self.src_today(), "kind": "current"})
        prior_high = [(d, val, f) for d, val, f in self.vital_hist.get("systolic_bp", []) if val >= 140 and d < (_aware(self.encounter.opened_at) or d)]
        if prior_high:
            score += min(3.0, 1.0 * len(prior_high))
            ev.append({"text": f"Raised systolic BP on {len(prior_high)} previous visit(s): " + ", ".join(f"{v:g} ({f}, {_fmt_date(d)})" for d, v, f in prior_high), "source": "VITALIS network history", "kind": "history"})
        on_treatment = [m for m in (self.patient.current_medications or []) if any(k in m.lower() for k in ["amlodipine", "lisinopril", "losartan", "nifedipine", "hydrochlorothiazide", "atenolol", "methyldopa", "ramipril", "telmisartan"])]
        known = any("hypertension" in c for c in self.conditions_lc)
        if known:
            score += 1.0
            ev.append({"text": "Hypertension already on problem list", "source": self.provenance("hypertension") or "VITALIS profile", "kind": "history"})
        if on_treatment and sbp and sbp >= 140:
            score += 1.0
            ev.append({"text": f"BP above target despite {', '.join(on_treatment)}", "source": self.provenance(on_treatment[0]) or "Medication list", "kind": "history"})
        fam = self.family_with(["hypertension", "stroke"])
        for f in fam:
            score += 0.5
            ev.append({"text": f"{f.relationship_type}: {f.condition}" + (f" (onset {f.age_of_onset})" if f.age_of_onset else ""), "source": "Family history", "kind": "family"})
        bmi = self.bmi()
        if bmi and bmi >= 30:
            score += 0.5
            ev.append({"text": f"BMI {bmi} kg/m² (obesity)", "source": self.src_today("weight & height"), "kind": "current"})
        if score < 2:
            return None
        uncontrolled = bool(on_treatment) and sbp and sbp >= 140
        name = "Uncontrolled stage 2 hypertension" if uncontrolled and (sbp >= 160 or (dbp or 0) >= 100) else \
               "Stage 2 hypertension" if sbp and (sbp >= 160 or (dbp or 0) >= 100) else "Hypertension"
        if _has(self.text, ["blurred vision", "blurring", "visual"]) and sbp and sbp >= 160:
            name += " — exclude hypertensive urgency / retinopathy"
        return {
            "condition": name, "score": score, "evidence": ev, "against": against,
            "recommended_investigations": ["Repeat BP (both arms) after 5 min rest", "Fundoscopy", "Urinalysis (protein)", "Serum electrolytes, urea & creatinine", "12-lead ECG", "Lipid profile"],
            "management_considerations": ["Confirm adherence to current antihypertensive", "Optimise / add a second agent per guideline", "Salt reduction, weight loss, physical activity", "Review in 2–4 weeks with home BP readings"],
            "guideline": "WHO 2021 Hypertension Guideline · NICE NG136",
        }

    def _diabetes(self, ml: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        score, ev, against = 0.0, [], []
        known = any("diabetes" in c and "pre" not in c for c in self.conditions_lc)
        g = self.glucose_now()
        osmotic = _has(self.text, ["thirst", "polydipsia", "frequent urination", "polyuria", "urinating", "weight loss", "tired", "fatigue", "blurred vision"])
        if g:
            if g[0] >= 200:
                score += 3.0
                ev.append({"text": f"Random glucose {g[0]:g} mg/dL (≥ 200)", "source": g[1], "kind": "current"})
            elif g[0] >= 140:
                score += 1.5
                ev.append({"text": f"Glucose {g[0]:g} mg/dL (elevated)", "source": g[1], "kind": "current"})
            else:
                against.append({"text": f"Glucose {g[0]:g} mg/dL is not elevated", "source": g[1], "kind": "current"})
        if osmotic:
            score += 1.5
            ev.append({"text": "Classic symptoms reported: " + ", ".join(osmotic), "source": self.src_today("presenting complaint"), "kind": "current"})
        if g and g[0] >= 200 and osmotic:
            score += 1.0
            ev.append({"text": "Symptoms + random glucose ≥ 200 mg/dL meets the WHO diagnostic threshold, pending confirmation", "source": "WHO diagnostic criteria", "kind": "rule"})
        for l in self.labs.get("hba1c", []):
            if l["num"] is None:
                continue
            if l["num"] >= 6.5:
                score += 3.0
                ev.append({"text": f"HbA1c {l['num']:g}% (diabetic range)", "source": self.src_lab(l), "kind": "lab"})
            elif l["num"] >= 5.7:
                score += 1.5
                ev.append({"text": f"HbA1c {l['num']:g}% (prediabetes range)", "source": self.src_lab(l), "kind": "lab"})
        fbs = [l for l in self.labs.get("fbs", []) if l["num"] is not None]
        if fbs:
            raised = [l for l in fbs if l["num"] >= 100]
            if raised:
                score += 0.8 * len(raised)
                ev.append({"text": "Fasting glucose " + " → ".join(f"{l['num']:g}" for l in fbs) + " mg/dL (rising, above 100)", "source": " / ".join(sorted({l['facility'] for l in fbs})), "kind": "lab"})
        if any("prediabetes" in c or "pre-diabetes" in c or "impaired fasting" in c for c in self.conditions_lc):
            score += 1.0
            ev.append({"text": "Prediabetes on problem list", "source": self.provenance("prediabetes") or "VITALIS profile", "kind": "history"})
        for f in self.family_with(["diabetes"]):
            score += 0.7
            ev.append({"text": f"{f.relationship_type}: {f.condition}" + (f" (onset {f.age_of_onset})" if f.age_of_onset else ""), "source": "Family history", "kind": "family"})
        bmi = self.bmi()
        if bmi and bmi >= 30:
            score += 0.5
            ev.append({"text": f"BMI {bmi} kg/m²", "source": self.src_today("weight & height"), "kind": "current"})
        if self.age and self.age >= 45:
            score += 0.3
        if ml:
            ev.append({"text": f"NCS diabetes model: {ml['probability']*100:.0f}% risk probability", "source": ml["model_version"], "kind": "ml"})
        if score < 2 and not known:
            return None
        if known:
            name = "Type 2 diabetes mellitus — assess glycaemic control"
        elif score >= 6:
            name = "Type 2 diabetes mellitus (probable new diagnosis)"
        else:
            name = "Impaired glucose regulation / prediabetes"
        return {
            "condition": name, "score": score, "evidence": ev, "against": against, "ml_probability": ml["probability"] if ml else None,
            "recommended_investigations": ["HbA1c", "Fasting plasma glucose", "Urinalysis (glucose, ketones, protein)", "Serum creatinine / eGFR", "Lipid profile"],
            "management_considerations": ["Confirm diagnosis with HbA1c or repeat fasting glucose", "Structured diet & physical-activity counselling", "If confirmed: first-line oral therapy per guideline, with renal function checked", "Retinal and foot screening"],
            "guideline": "WHO 2019 Diabetes Classification · ADA Standards of Care 2026",
        }

    def _dyslipidaemia(self) -> Optional[Dict[str, Any]]:
        chol, ldl = self.latest_lab("chol"), self.latest_lab("ldl")
        score, ev = 0.0, []
        if chol and chol["num"] >= 200:
            score += 2.0 if chol["num"] >= 240 else 1.2
            ev.append({"text": f"Total cholesterol {chol['num']:g} mg/dL", "source": self.src_lab(chol), "kind": "lab"})
        if ldl and ldl["num"] >= 130:
            score += 2.0 if ldl["num"] >= 160 else 1.0
            ev.append({"text": f"LDL cholesterol {ldl['num']:g} mg/dL", "source": self.src_lab(ldl), "kind": "lab"})
        if score < 2:
            return None
        if any("hypertension" in c for c in self.conditions_lc) or (self.vitals.get("systolic_bp") or 0) >= 140:
            score += 0.5
            ev.append({"text": "Co-existing hypertension raises cardiovascular risk", "source": "Combined record", "kind": "rule"})
        return {
            "condition": "Dyslipidaemia (raised cardiovascular risk)", "score": score, "evidence": ev, "against": [],
            "recommended_investigations": ["Repeat fasting lipid profile", "10-year cardiovascular risk calculation"],
            "management_considerations": ["Lifestyle modification", "Consider moderate-intensity statin given combined risk factors"],
            "guideline": "WHO HEARTS technical package · NICE NG238",
        }

    def _malaria(self) -> Optional[Dict[str, Any]]:
        fever_words = _has(self.text, ["fever", "chills", "rigors", "body ache", "body pain", "hot body", "malaise"])
        temp = self.vitals.get("temperature")
        score, ev, against = 0.0, [], []
        if fever_words:
            score += 2.0
            ev.append({"text": "Febrile symptoms: " + ", ".join(fever_words), "source": self.src_today("presenting complaint"), "kind": "current"})
        if temp is not None:
            if temp >= 37.8:
                score += 2.0
                ev.append({"text": f"Temperature {temp:g} °C", "source": self.src_today(), "kind": "current"})
            else:
                against.append({"text": f"Afebrile today ({temp:g} °C)", "source": self.src_today(), "kind": "current"})
        prior = [l for l in self.labs.get("malaria", []) if str(l["value"]).lower().startswith("pos") and not l["today"]]
        if prior and fever_words:
            score += 0.5
            ev.append({"text": f"Previous positive malaria test ({prior[-1]['facility']}, {_fmt_date(prior[-1]['date'])})", "source": "VITALIS network history", "kind": "history"})
        if score < 2.5:
            return None
        return {
            "condition": "Malaria (Plasmodium falciparum — endemic setting)", "score": score, "evidence": ev, "against": against,
            "recommended_investigations": ["Malaria RDT", "Thick & thin blood film", "Full blood count"],
            "management_considerations": ["Treat only parasitologically-confirmed malaria", "Assess for severe-malaria criteria"],
            "guideline": "WHO Guidelines for Malaria 2025 · Nigeria National Malaria Treatment Guidelines",
        }

    def _respiratory(self) -> Optional[Dict[str, Any]]:
        sx = _has(self.text, ["cough", "sputum", "breathless", "shortness of breath", "difficulty breathing", "wheeze", "chest pain"])
        if not sx:
            return None
        score, ev = 2.0, [{"text": "Respiratory symptoms: " + ", ".join(sx), "source": self.src_today("presenting complaint"), "kind": "current"}]
        spo2, rr, temp = self.vitals.get("spo2"), self.vitals.get("respiratory_rate"), self.vitals.get("temperature")
        if spo2 is not None and spo2 < 94:
            score += 1.5
            ev.append({"text": f"SpO₂ {spo2:g}%", "source": self.src_today(), "kind": "current"})
        if rr is not None and rr > 22:
            score += 1.0
            ev.append({"text": f"Respiratory rate {rr:g}/min", "source": self.src_today(), "kind": "current"})
        if temp is not None and temp >= 37.8:
            score += 1.0
            ev.append({"text": f"Fever {temp:g} °C", "source": self.src_today(), "kind": "current"})
        asthma = any("asthma" in c for c in self.conditions_lc)
        name = "Acute asthma exacerbation" if asthma and _has(self.text, ["wheeze", "breathless", "shortness of breath", "tight"]) else "Lower respiratory tract infection / community-acquired pneumonia"
        if asthma:
            ev.append({"text": "Known asthma", "source": self.provenance("asthma") or "VITALIS profile", "kind": "history"})
        return {
            "condition": name, "score": score, "evidence": ev, "against": [],
            "recommended_investigations": ["Chest X-ray (PA)", "Full blood count", "Peak flow (if asthmatic)", "Sputum microscopy if > 2 weeks cough"],
            "management_considerations": ["Assess severity (CURB-65 / asthma severity)", "Oxygen if SpO₂ < 94%"],
            "guideline": "WHO IMAI · BTS/SIGN Asthma Guideline",
        }

    # ------------------------------------------------------------ medication options
    MED_OPTIONS = {
        "hypertension": [
            ("Amlodipine 10 mg once daily (dose optimisation)", "Calcium-channel blocker; patient already tolerates amlodipine"),
            ("Lisinopril 10 mg once daily", "ACE inhibitor — preferred add-on when diabetes is suspected (renal protection)"),
            ("Hydrochlorothiazide 12.5 mg once daily", "Thiazide diuretic — common second-line agent"),
        ],
        "diabetes": [
            ("Metformin 500 mg twice daily with meals", "First-line oral agent once diagnosis is confirmed and eGFR is adequate"),
        ],
        "dyslipidaemia": [
            ("Atorvastatin 20 mg at night", "Moderate-intensity statin for combined cardiovascular risk"),
            ("Simvastatin 40 mg at night", "Alternative statin"),
        ],
        "malaria": [
            ("Artemether-lumefantrine 80/480 mg (6-dose course)", "WHO first-line ACT for uncomplicated falciparum malaria"),
        ],
        "respiratory": [
            ("Amoxicillin 1 g three times daily (5 days)", "First-line for non-severe community-acquired pneumonia"),
            ("Salbutamol inhaler 2 puffs PRN", "Short-acting bronchodilator"),
        ],
    }

    def medication_options(self, keys: List[str]) -> List[Dict[str, Any]]:
        out = []
        for key in keys:
            for drug, why in self.MED_OPTIONS.get(key, []):
                drug_name = drug.split(" ")[0].lower()
                already_on = any(drug_name in m for m in self.meds_lc)
                if ("optimisation" in drug) != already_on:
                    continue  # suggest dose optimisation only for current drugs, new starts only for others
                res = MedicationSafetyChecker.check_medication_safety(
                    proposed_meds=[drug],
                    patient_allergies=self.patient.allergies or [],
                    current_medications=self.patient.current_medications or [],
                    patient_conditions=self.patient.chronic_conditions or [],
                )
                alerts = []
                safety = "ok"
                for c in res["allergy_conflicts"]:
                    src = self.provenance(c["documented_allergy"])
                    alerts.append(f"Allergy: documented {c['documented_allergy'].title()}" + (f" — recorded at {src}" if src else "") + ". Cross-reactivity risk.")
                    safety = "avoid"
                for i in res["drug_interactions"]:
                    alerts.append(f"Interaction ({i['severity']}): {i['interacting_pair']} — {i['clinical_significance']}")
                    if safety != "avoid":
                        safety = "avoid" if i["severity"] == "Major" else "caution"
                for c in res["contraindications_and_warnings"]:
                    alerts.append(f"{c['condition']}: {c['warning']}")
                    if safety == "ok":
                        safety = "caution"
                if drug_name == "metformin" and not self.latest_lab("creatinine"):
                    alerts.append("Check renal function (creatinine/eGFR) before starting.")
                    if safety == "ok":
                        safety = "caution"
                if drug_name == "lisinopril" and not self.latest_lab("creatinine"):
                    alerts.append("Check creatinine and potassium within 1–2 weeks of starting.")
                out.append({"drug": drug, "for_condition": key, "rationale": why, "safety": safety, "alerts": alerts})
        return out

    # ------------------------------------------------------------ main
    def assess(self) -> Dict[str, Any]:
        facs = sorted({_short_fac(e.facility.name if e.facility else None) for e in self.prior})
        vit_points = sum(len(v) for v in self.vital_hist.values())
        lab_points = sum(len(v) for v in self.labs.values())
        self.trace.append(
            f"Loaded {len(self.prior)} prior encounter(s) from {len(facs)} facilit{'y' if len(facs) == 1 else 'ies'}"
            + (f" ({', '.join(facs)})" if facs else "") + " via the VITALIS network."
        )
        self.trace.append(f"Extracted {vit_points} vital-sign readings and {lab_points} laboratory values; {len(self.family)} family-history entries.")
        self.trace.append(f"Cross-referenced {len(self.patient.allergies or [])} documented allergy(ies) and {len(self.patient.current_medications or [])} active medication(s).")

        trends = self.trends()
        for t in trends:
            if t["direction"] == "rising":
                self.trace.append(f"Detected trend — {t['text']}.")

        red_flags = self.red_flags()
        if red_flags:
            self.trace.append(f"Red-flag screen: {len(red_flags)} alert(s) raised.")
        else:
            self.trace.append("Red-flag screen: no emergency criteria met.")

        ml_diab = self.run_diabetes_model()
        ml_heart = self.run_heart_model()

        raw = []
        for key, cond in [
            ("hypertension", self._hypertension()),
            ("diabetes", self._diabetes(ml_diab)),
            ("dyslipidaemia", self._dyslipidaemia()),
            ("malaria", self._malaria()),
            ("respiratory", self._respiratory()),
        ]:
            if cond:
                cond["key"] = key
                raw.append(cond)

        for c in raw:
            p = _likelihood(c["score"])
            if c.get("ml_probability") is not None:
                p = 0.65 * p + 0.35 * c["ml_probability"]
            c["likelihood"] = round(p, 2)
            c["likelihood_label"] = _label(p)
            c.pop("score", None)
        raw.sort(key=lambda c: c["likelihood"], reverse=True)
        for i, c in enumerate(raw, 1):
            c["rank"] = i

        if not raw:
            raw.append({
                "key": "nonspecific", "rank": 1, "condition": "Non-specific presentation — clinical evaluation required",
                "likelihood": 0.3, "likelihood_label": "Low", "evidence": [], "against": [],
                "recommended_investigations": ["Full blood count", "Urinalysis", "Malaria RDT (endemic setting)"],
                "management_considerations": ["Detailed history and examination"], "guideline": "—",
            })
        self.trace.append(f"Ranked {len(raw)} possible condition(s) by documented evidence.")

        meds = self.medication_options([c["key"] for c in raw])
        blocked = [m for m in meds if m["safety"] == "avoid"]
        self.trace.append(f"Screened {len(meds)} treatment option(s) against allergies & interactions — {len(blocked)} flagged to avoid.")

        # Missing data
        for k, label in [("systolic_bp", "Blood pressure"), ("pulse_rate", "Pulse"), ("temperature", "Temperature"), ("spo2", "SpO₂"), ("weight", "Weight")]:
            if k not in self.vitals:
                self.missing.append(f"{label} not recorded at this visit.")
        if not self.latest_lab("creatinine"):
            self.missing.append("No renal function (creatinine/eGFR) on record — needed before ACE inhibitor or metformin.")

        # Narrative summary
        p = self.patient
        sex = "female" if self.female else "male"
        v = self.vitals
        vit_bits = []
        if "systolic_bp" in v and "diastolic_bp" in v:
            vit_bits.append(f"BP {v['systolic_bp']:g}/{v['diastolic_bp']:g}")
        if "blood_glucose" in v:
            vit_bits.append(f"glucose {v['blood_glucose']:g} mg/dL")
        if "temperature" in v:
            vit_bits.append(f"T {v['temperature']:g} °C")
        if "spo2" in v:
            vit_bits.append(f"SpO₂ {v['spo2']:g}%")
        bmi = self.bmi()
        if bmi:
            vit_bits.append(f"BMI {bmi}")
        summary = (
            f"{self.age}-year-old {sex}"
            + (f" with {', '.join(p.chronic_conditions)}" if p.chronic_conditions else "")
            + (f", on {', '.join(p.current_medications)}" if p.current_medications else "")
            + f". {len(self.prior)} previous visit(s) across {len(facs)} facilit{'y' if len(facs) == 1 else 'ies'} in the VITALIS network. "
            + (f"Presents today with: {self.complaint}. " if self.complaint else "")
            + (f"Today: {', '.join(vit_bits)}. " if vit_bits else "")
            + (f"Top consideration: {raw[0]['condition']} ({raw[0]['likelihood_label'].lower()} likelihood). " if raw else "")
            + (f"⚠ {len(blocked)} commonly used option(s) conflict with this patient's history." if blocked else "")
        )

        return {
            "model_version": MODEL_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_coverage": {
                "prior_encounters": len(self.prior),
                "facilities": facs,
                "vital_readings": vit_points,
                "lab_values": lab_points,
                "family_history_entries": len(self.family),
            },
            "analysis_trace": self.trace,
            "summary": summary,
            "red_flags": red_flags,
            "conditions": raw,
            "trends": trends,
            "ml_models": [m for m in (ml_diab, ml_heart) if m],
            "medication_options": meds,
            "missing_data": self.missing,
            "safety_disclaimer": SAFETY_DISCLAIMER,
        }
