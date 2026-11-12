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
    Facility Matching Engine.
    Suitability formula:
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

            # If essential service not supported, exclude facility
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

    @staticmethod
    def compute_capability_suitability(
        facility_info: Dict[str, Any],
        required_capabilities: List[str],
        capability_record: Optional[Dict[str, Any]],
        availability_record: Optional[Dict[str, Any]],
        user_lat: float,
        user_lon: float,
        is_emergency: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Capability-based matching for CareConnect.
        Hard filters on the required capability set (services, specialists, equipment, theatre, blood bank, ICU/NICU).
        Explicitly handles availability states: accepting, limited, not_accepting, unknown.
        Never treats unknown or stale availability as accepting for emergencies.
        """
        if is_emergency and not facility_info.get("emergency_available", False):
            return None

        if not capability_record:
            if required_capabilities:
                return None
            all_caps = []
            last_confirmed = None
            reported_by = "Unknown"
        else:
            all_caps = (
                [c.lower() for c in capability_record.get("services", [])] +
                [c.lower() for c in capability_record.get("specialists", [])] +
                [c.lower() for c in capability_record.get("equipment", [])]
            )
            if capability_record.get("has_operating_theatre"):
                all_caps.extend(["operating theatre", "theatre", "c-section", "surgery"])
            if capability_record.get("has_blood_bank"):
                all_caps.extend(["blood bank", "blood transfusion", "transfusion"])
            if capability_record.get("has_icu"):
                all_caps.extend(["icu", "intensive care"])
            if capability_record.get("has_nicu"):
                all_caps.extend(["nicu", "neonatal intensive care", "neonatal"])
            last_confirmed = capability_record.get("last_confirmed_at")
            reported_by = capability_record.get("reported_by", "Facility Admin")

        # Hard filter on required capabilities
        matched_caps = []
        for req in required_capabilities:
            req_low = req.lower().strip()
            if not req_low:
                continue
            found = any(req_low in cap or cap in req_low for cap in all_caps)
            if not found:
                return None
            matched_caps.append(req)

        c_score = 100.0

        # Evaluate explicit availability state
        acceptance_status = "unknown"
        expected_wait = None
        if availability_record:
            acceptance_status = availability_record.get("emergency_acceptance_status", "unknown").lower()
            expected_wait = availability_record.get("expected_wait_minutes")
            if availability_record.get("last_confirmed_at"):
                last_confirmed = availability_record.get("last_confirmed_at")
            if availability_record.get("reported_by"):
                reported_by = availability_record.get("reported_by")

        # Unknown or not_accepting is never treated as accepting in emergency mode
        if is_emergency and acceptance_status in ["not_accepting", "unknown"]:
            return None

        if acceptance_status == "accepting":
            a_score = 100.0
        elif acceptance_status == "limited":
            a_score = 65.0
        elif acceptance_status == "unknown":
            a_score = 25.0
        else:  # not_accepting
            return None

        # Freshness evaluation (stale check)
        now = datetime.now(timezone.utc)
        freshness_label = "unknown"
        verif = facility_info.get("verification_status", "unverified")
        v_base = 100.0 if verif == "verified" else 50.0

        if last_confirmed:
            if isinstance(last_confirmed, str):
                try:
                    last_confirmed = datetime.fromisoformat(last_confirmed.replace("Z", "+00:00"))
                except Exception:
                    last_confirmed = now
            if last_confirmed.tzinfo is None:
                last_confirmed = last_confirmed.replace(tzinfo=timezone.utc)
            hours_diff = (now - last_confirmed).total_seconds() / 3600.0
            if hours_diff <= 12:
                freshness_label = "confirmed"
                v_score = v_base
            elif hours_diff <= 24:
                freshness_label = "reported"
                v_score = max(60.0, v_base - 15.0)
            else:
                freshness_label = "stale"
                v_score = max(25.0, v_base - 45.0)
                if is_emergency:
                    return None
        else:
            v_score = 35.0
            if is_emergency:
                return None

        # Distance suitability D
        dist_km = calculate_haversine_distance(
            user_lat, user_lon,
            facility_info["latitude"], facility_info["longitude"]
        )
        if dist_km <= 2.0:
            d_score = 100.0
        elif dist_km <= 10.0:
            d_score = 90.0 - (dist_km - 2.0) * 3.5
        elif dist_km <= 30.0:
            d_score = 62.0 - (dist_km - 10.0) * 2.0
        else:
            d_score = max(10.0, 22.0 - (dist_km - 30.0) * 0.5)

        suitability_score = round(
            0.40 * c_score + 0.25 * a_score + 0.20 * d_score + 0.15 * v_score,
            1
        )

        rationale = (
            f"Why this facility: Verified capability fit ({', '.join(matched_caps) if matched_caps else 'General Care'}), "
            f"Acceptance Status: {acceptance_status.upper()} ({freshness_label.upper()} by {reported_by}), "
            f"Distance: {dist_km} km, Suitability S={suitability_score}."
        )

        return {
            "facility_id": facility_info["id"],
            "suitability_score": suitability_score,
            "distance_km": dist_km,
            "matched_capabilities": matched_caps,
            "acceptance_status": acceptance_status,
            "freshness_label": freshness_label,
            "last_confirmed_at": last_confirmed,
            "reported_by": reported_by,
            "expected_wait_minutes": expected_wait,
            "score_breakdown": {
                "service_compatibility_C": c_score,
                "availability_A": a_score,
                "distance_suitability_D": d_score,
                "verification_freshness_V": v_score
            },
            "why_this_facility": rationale
        }
