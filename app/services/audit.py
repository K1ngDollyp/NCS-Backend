from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.models import AuditEvent, get_utc_now

def log_audit_event(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    patient_id: Optional[str] = None,
    encounter_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """Record immutable audit event for sensitive clinical / security actions"""
    event = AuditEvent(
        actor_id=actor_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        timestamp=get_utc_now(),
        event_metadata=metadata or {}
    )
    db.add(event)
    db.commit()
    return event

