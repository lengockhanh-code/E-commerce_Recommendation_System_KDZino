"""User Event Tracking API Router"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.schemas import UserEventCreate
from app.services.auth_service import get_current_user
from app.services.event_service import log_event_service

router = APIRouter(prefix="/events", tags=["User Interaction Telemetry"])


@router.post("", status_code=status.HTTP_201_CREATED)
def log_event_route(
    data: UserEventCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ghi nhận tương tác người dùng (view, like, cart, buy_comp) gắn với recommendation_request_id"""
    user_id = current_user.id if current_user else None
    return log_event_service(db=db, event_data=data, user_id=user_id)
