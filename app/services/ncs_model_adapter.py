import os
import sys
import types
from pathlib import Path
from typing import Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
from app.core.config import settings

# Custom unpickler shim for diabetes preprocessing pipeline
if "src.common.preprocessing_util" not in sys.modules:
    src_mod = types.ModuleType("src")
    src_common = types.ModuleType("src.common")
    src_util = types.ModuleType("src.common.preprocessing_util")
    src_util.replace_zeros_with_nan = lambda X: np.where(X == 0, np.nan, X)
    sys.modules["src"] = src_mod
    sys.modules["src.common"] = src_common
    sys.modules["src.common.preprocessing_util"] = src_util

def _ordered_frame(model, input_data: Dict[str, Any]) -> pd.DataFrame:
    """Build a single-row DataFrame in exactly the column order the pipeline was trained on."""
    cols = list(getattr(model, "feature_names_in_", input_data.keys()))
    missing = [c for c in cols if c not in input_data]
    if missing:
        raise ValueError(f"Missing model features: {missing}")
    return pd.DataFrame([[input_data[c] for c in cols]], columns=cols)


class NCSModelAdapter:
    """
    Adapter for trained ML risk prediction pipelines.
    Handles feature validation, DataFrame construction, and inference.
    """
    _heart_pipeline = None
    _diabetes_pipeline = None

    @classmethod
    def get_model_dir(cls) -> Path:
        p = Path(settings.NCS_MODEL_DIR)
        if not p.is_absolute():
            # Resolve relative to project root
            p = (Path(__file__).parent.parent.parent / p).resolve()
        if not p.exists():
            # Fallback to Desktop location if local not found
            desktop_p = Path(r"C:\Users\USER\Desktop\NCS Model\Model-Health-Care\model_dir")
            if desktop_p.exists():
                return desktop_p
        return p

    @classmethod
    def get_heart_pipeline(cls):
        if cls._heart_pipeline is None:
            pipeline_path = cls.get_model_dir() / "heart_disease_prediction_pipeline.joblib"
            if pipeline_path.exists():
                cls._heart_pipeline = joblib.load(pipeline_path)
                # Single-row inference is faster without process/thread fan-out
                model = getattr(cls._heart_pipeline, "named_steps", {}).get("model")
                if model is not None and hasattr(model, "n_jobs"):
                    model.n_jobs = 1
            else:
                raise FileNotFoundError(f"Heart disease model not found at {pipeline_path}")
        return cls._heart_pipeline

    @classmethod
    def get_diabetes_pipeline(cls):
        if cls._diabetes_pipeline is None:
            pipeline_path = cls.get_model_dir() / "diabetes_prediction_pipeline.joblib"
            if pipeline_path.exists():
                cls._diabetes_pipeline = joblib.load(pipeline_path)
            else:
                raise FileNotFoundError(f"Diabetes model not found at {pipeline_path}")
        return cls._diabetes_pipeline

    @classmethod
    def predict_heart_disease(cls, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Features expected by heart_disease_prediction_pipeline:
        age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope, ca, thal
        """
        model = cls.get_heart_pipeline()
        df = _ordered_frame(model, input_data)
        probability = float(model.predict_proba(df)[0][1])  # one pass; class 1 = risk
        prediction = int(probability > 0.5)  # random forest predict == argmax of probabilities

        return {
            "prediction": prediction,
            "probability": round(probability, 4),
            "diagnosis": "Heart Disease Risk Detected" if prediction == 1 else "Low Risk / No Heart Disease Detected",
            "model_version": "NCS-RandomForestClassifier-HeartV1",
            "clinical_significance": (
                "Elevated cardiovascular risk profile detected based on clinical features. "
                "Recommend urgent 12-lead Electrocardiogram (ECG), Serum Troponin I, and Cardiology consult."
                if prediction == 1 else
                "Cardiovascular risk assessment within acceptable parameters. Continue routine clinical monitoring."
            )
        }

    @classmethod
    def predict_diabetes(cls, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Features expected by diabetes_prediction_pipeline:
        Pregnancies, Glucose, BloodPressure, SkinThickness, Insulin, BMI, DiabetesPedigreeFunction, Age
        """
        model = cls.get_diabetes_pipeline()
        df = _ordered_frame(model, input_data)
        prediction = int(model.predict(df)[0])  # SVC: decision function, not Platt probability
        probability = float(model.predict_proba(df)[0][1])

        return {
            "prediction": prediction,
            "probability": round(probability, 4),
            "diagnosis": "Elevated Diabetes Risk Detected" if prediction == 1 else "Normal / Low Diabetes Risk",
            "model_version": "NCS-SVC-DiabetesV1",
            "clinical_significance": (
                "Metabolic screening indicates significant risk of Type 2 Diabetes / Impaired Glucose Tolerance. "
                "Recommend confirmation with Fasting Blood Glucose (FBG) and HbA1c."
                if prediction == 1 else
                "Glycemic and metabolic risk factors are within normal thresholds."
            )
        }



def warm_up_models() -> None:
    """Load both pipelines at server start so the first clinical request is fast."""
    for loader in (NCSModelAdapter.get_heart_pipeline, NCSModelAdapter.get_diabetes_pipeline):
        try:
            loader()
        except Exception as exc:  # models are optional for the rest of the API
            print(f"[VITALIS] ML model warm-up skipped: {exc}")
