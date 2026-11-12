from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import engine, Base
from app.api.endpoints import (
    auth, patients, encounters, diagnostics,
    triage, facilities, referrals, connect,
    intelligence, transfers, admin, careconnect
)

# Initialize database schema tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    VITALIS - Healthcare Coordination Network API.
    Coordinating Reception, Nursing, Doctor, and Diagnostics with Clinical Decision Support & Inter-Hospital Record Exchange.
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/", tags=["System"])
def root():
    return {
        "system": "VITALIS Healthcare Coordination Network",
        "status": "operational",
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_STR}/docs",
        "departments": ["Reception", "Nursing", "Doctor", "Laboratory & Radiology"],
        "careconnect_actions": [
            "Talk to AI",
            "Find a doctor",
            "Home visit",
            "Find a hospital",
            "Emergency assistance"
        ],
        "modules": [
            "VITALIS CareConnect (Patient Access, AI Assistant, Telemedicine, Home Visits, Capability Search, Emergency Coordination)",
            "VITALIS AI Triage & Doctor Clinical Assistant",
            "VITALIS ROUTE (Capability & Facility Matching)",
            "VITALIS CONNECT (QR & Consent)",
            "VITALIS HOSPITAL (Encounters & Workflow)",
            "VITALIS REFERRAL",
            "VITALIS INTELLIGENCE (Decision Support)",
            "VITALIS TRANSFER (Inter-Hospital Exchange)",
            "VITALIS ADMIN"
        ]
    }

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}

# Include API Domain Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(patients.router, prefix=settings.API_V1_STR)
app.include_router(encounters.router, prefix=settings.API_V1_STR)
app.include_router(diagnostics.router, prefix=settings.API_V1_STR)
app.include_router(triage.router, prefix=settings.API_V1_STR)
app.include_router(facilities.router, prefix=settings.API_V1_STR)
app.include_router(referrals.router, prefix=settings.API_V1_STR)
app.include_router(connect.router, prefix=settings.API_V1_STR)
app.include_router(intelligence.router, prefix=settings.API_V1_STR)
app.include_router(transfers.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(careconnect.router, prefix=settings.API_V1_STR)

