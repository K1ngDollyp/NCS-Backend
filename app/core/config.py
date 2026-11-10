from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "VITALIS Healthcare Coordination Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment & Security
    SECRET_KEY: str = "vitalis-super-secret-key-change-in-production-2026-itdc"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day for prototype ease
    
    # Database (Default to SQLite file if PostgreSQL not provided)
    DATABASE_URL: str = "sqlite:///./vitalis.db"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]
    
    # Prototype model settings (mock / heuristic engine for now, ready for external ML model plug)
    MODEL_PROVIDER: str = "ncs-ml-model"
    NCS_MODEL_DIR: str = "ml_model/model_dir"
    ENABLE_NCS_ML_MODEL: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow"
    )

settings = Settings()

