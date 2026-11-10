from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_roles
from app.models.models import Facility, FacilityService, Service, User, UserRole
from app.schemas.schemas import FacilityResponse, FacilityCreate, FacilitySuitabilityResult
from app.engines.matching.matcher import FacilityMatcher

router = APIRouter(prefix="/facilities", tags=["VITALIS ROUTE - Facility Matching"])

@router.get("", response_model=List[FacilityResponse])
def list_facilities(
    city: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Facility)
    if city:
        query = query.filter(Facility.city.ilike(f"%{city}%"))
    return query.all()

@router.get("/match", response_model=List[FacilitySuitabilityResult])
def match_facilities(
    user_lat: float = Query(..., description="Patient current latitude (e.g. 7.1557 for Abeokuta)"),
    user_lon: float = Query(..., description="Patient current longitude (e.g. 3.3450 for Abeokuta)"),
    service_needed: Optional[str] = Query(None, description="Required clinical service"),
    is_emergency: bool = Query(False, description="Emergency prioritization"),
    db: Session = Depends(get_db)
):
    """
    Facility matching algorithm:
    Applies eligibility filters, then computes multi-factor suitability score.
    """
    facilities = db.query(Facility).all()
    results = []

    for fac in facilities:
        # Load services
        fac_services = []
        for fs in fac.services:
            fac_services.append({
                "service_code": fs.service.service_code if fs.service else "",
                "service_name": fs.service.service_name if fs.service else "",
                "availability_status": fs.availability_status,
                "last_confirmed_at": fs.last_confirmed_at
            })

        fac_info = {
            "id": fac.id,
            "name": fac.name,
            "latitude": fac.latitude,
            "longitude": fac.longitude,
            "emergency_available": fac.emergency_available,
            "verification_status": fac.verification_status
        }

        match_res = FacilityMatcher.compute_suitability(
            facility_info=fac_info,
            target_service=service_needed,
            user_lat=user_lat,
            user_lon=user_lon,
            facility_services=fac_services,
            is_emergency=is_emergency
        )

        if match_res:
            results.append(FacilitySuitabilityResult(
                facility=FacilityResponse.model_validate(fac),
                suitability_score=match_res["suitability_score"],
                distance_km=match_res["distance_km"],
                service_compatible=match_res["service_compatible"],
                reported_availability=match_res["reported_availability"],
                last_confirmed_at=match_res["last_confirmed_at"],
                score_breakdown=match_res["score_breakdown"],
                recommendation_rationale=match_res["recommendation_rationale"]
            ))

    # Sort descending by suitability score
    results.sort(key=lambda x: x.suitability_score, reverse=True)
    return results

@router.post("", response_model=FacilityResponse)
def create_facility(
    fac_in: FacilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.NETWORK_ADMIN]))
):
    facility = Facility(**fac_in.model_dump())
    db.add(facility)
    db.commit()
    db.refresh(facility)
    return facility

