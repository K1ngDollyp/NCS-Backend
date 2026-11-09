import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two coordinates in kilometers"""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

class FacilityMatcher:
    """
    VITALIS ROUTE Engine (Section 12)
    Prototype suitability formula:
    S = 0.40 * C + 0.25 * A + 0.20 * D + 0.15 * V
    Where:
      C = Service compatibility (0-100)
      A = Reported availability (0-100)
      D = Distance suitability (0-100)
      V = Verification & Data Freshness (0-100)
    """

    @staticmethod
    def compute_suitability(
        facility_info: Dict[str, Any],
        target_service: Optional[str],
        user_lat: float,
        user_lon: float,
        facility_services: List[Dict[str, Any]],
        is_emergency: bool = False
    ) -> Optional[Dict[str, Any]]:
        # Hard filter 1: If emergency, facility must have emergency capabilities
        if is_emergency and not facility_info.get("emergency_available", False):
            return None

        # Hard filter 2: Service compatibility C
        # If target_service requested, check if facility supports it
        has_service = False
        service_availability = "unknown"
        last_confirmed = None

        if not target_service or target_service.lower() in ["general", "consultation", "any"]:
            has_service = True
            service_availability = "available"
            c_score = 100.0
        else:
            for s in facility_services:
                s_name = s.get("service_name", "").lower()
                s_code = s.get("service_code", "").lower()
                target_lower = target_service.lower()
                if target_lower in s_name or target_lower in s_code or s_name in target_lower:
                    has_service = True
                    service_availability = s.get("availability_status", "unknown")
                    last_confirmed = s.get("last_confirmed_at")
                    break

            # Hard eligibility filter: Exclude facilities missing an essential service requirement (Section 12)
            if not has_service:
                return None
            c_score = 100.0

        # Availability Score A (0-100)
        # Unknown availability is NOT treated as available
        if service_availability == "available":
            a_score = 100.0
        elif service_availability == "limited":
            a_score = 60.0
        elif service_availability == "unknown":
            a_score = 30.0  # severely penalize unknown
        else:  # unavailable
            a_score = 0.0

        # Distance Calculation & Suitability D (0-100)
        dist_km = calculate_haversine_distance(
            user_lat, user_lon,
            facility_info["latitude"], facility_info["longitude"]
        )
        # 0 km -> 100, 20 km -> 50, 40+ km -> 10
        if dist_km <= 2.0:
            d_score = 100.0
        elif dist_km <= 10.0:
            d_score = 90.0 - (dist_km - 2.0) * 3.5
        elif dist_km <= 30.0:
            d_score = 62.0 - (dist_km - 10.0) * 2.0
        else:
            d_score = max(10.0, 22.0 - (dist_km - 30.0) * 0.5)

        # Verification & Freshness V (0-100)
        verif = facility_info.get("verification_status", "unverified")
        v_base = 100.0 if verif == "verified" else (60.0 if verif == "pending" else 30.0)
        
        # Freshness decay
        now = datetime.now(timezone.utc)
        if last_confirmed:
            if isinstance(last_confirmed, str):
                try:
                    last_confirmed = datetime.fromisoformat(last_confirmed.replace("Z", "+00:00"))
                except Exception:
                    last_confirmed = now
            if last_confirmed.tzinfo is None:
                last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)
            hours_diff = (now - last_confirmed).total_seconds() / 3600.0
            if hours_diff > 48:
                v_score = max(30.0, v_base - 30.0)
            elif hours_diff > 24:
                v_score = max(50.0, v_base - 15.0)
            else:
                v_score = v_base
        else:
            v_score = 50.0

        # Final Weighted Score: S = 0.40C + 0.25A + 0.20D + 0.15V
        suitability_score = round(
            0.40 * c_score + 0.25 * a_score + 0.20 * d_score + 0.15 * v_score,
            1
        )

        rationale = (
            f"Compatibility: {c_score:.0f}%, Reported Availability: {service_availability.upper()} ({a_score:.0f}%), "
            f"Distance: {dist_km} km ({d_score:.0f}%), Verification & Data Freshness: {v_score:.0f}%."
        )

        return {
            "facility_id": facility_info["id"],
            "suitability_score": suitability_score,
            "distance_km": dist_km,
            "service_compatible": has_service,
            "reported_availability": service_availability,
            "last_confirmed_at": last_confirmed,
            "score_breakdown": {
                "service_compatibility_C": c_score,
                "availability_A": a_score,
                "distance_suitability_D": d_score,
                "verification_freshness_V": v_score
            },
            "recommendation_rationale": rationale
        }
