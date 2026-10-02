"""User Interaction Event Logging Service"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.model.models import UserEvent
from app.model.schemas import UserEventCreate


def log_event_service(
    db: Session,
    event_data: UserEventCreate,
    user_id: Optional[str] = None
) -> Dict[str, str]:
    event = UserEvent(
        user_id=user_id,
        item_id=event_data.item_id,
        event_type=event_data.event_type,
        source_page=event_data.source_page,
        recommendation_request_id=event_data.recommendation_request_id,
        position=event_data.position,
        event_metadata=event_data.metadata
    )
    db.add(event)
    db.commit()
    return {"status": "logged"}
