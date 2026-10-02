"""User Analytics Event Tracking Endpoints"""

from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.orm import User
from backend.src.models.schemas import EventCreate, EventResponse
from backend.src.security.dependencies import get_current_user
from backend.src.services.event_service import log_user_event

router = APIRouter(prefix="/events", tags=["Event Tracking"])


@router.post("", response_model=EventResponse)
def track_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Ghi nhận các sự kiện tương tác của người dùng (xem sản phẩm, thêm giỏ hàng, mua hàng...)"""
    user_id = str(current_user.id) if current_user else None
    return log_user_event(db, event, user_id=user_id)
