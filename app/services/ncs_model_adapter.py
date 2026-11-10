import os
import sys
import types
from pathlib import Path
from typing import Dict, Any, Optional
import joblib
import numpy as np
import pandas as pd
from app.core.config import settings

# Register pickle unpickling shim for diabetes pipeline without modifying NCS Model folder
if "src.common.preprocessing_util" not in sys.modules:
    src_mod = types.ModuleType("src")
    src_common = types.ModuleType("src.common")
    src_util = types.ModuleType("src.common.preprocessing_util")
    src_util.replace_zeros_with_nan = lambda X: np.where(X == 0, np.nan, X)
    sys.modules["src"] = src_mod
    sys.modules["src.common"] = src_common
    sys.modules["src.common.preprocessing_util"] = src_util

class NCSModelAdapter:
    """
    Read-Only Integration Adapter for the NCS Model (Model-Health-Care).
    Loads pre-trained pipelines directly from their source folder without modifying any files.
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
        df = pd.DataFrame([input_data])
        prediction = int(model.predict(df)[0])
        probability = float(model.predict_proba(df)[0][1])

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
        df = pd.DataFrame([input_data])
        prediction = int(model.predict(df)[0])
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

