"""Recommendations API Router"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.model.database import get_db
from app.model.schemas import RecommendationResponse
from app.services.auth_service import get_current_user
from app.services.recommendation_service import get_recommendations_service

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=RecommendationResponse)
def get_recommendations_route(
    context: str = Query("home", description="Ngữ cảnh gợi ý: home, product_detail, cart"),
    trigger_item_id: Optional[str] = Query(None, description="Mã sản phẩm đang xem hoặc sản phẩm trong giỏ"),
    limit: int = Query(12, ge=1, le=48),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lấy danh sách gợi ý sản phẩm động theo ngữ cảnh (Home, Product Detail, Cart)
    Đồng thời lưu lịch sử recommendation_requests và recommendation_items vào DB.
    """
    user_id = current_user.id if current_user else None
    res = get_recommendations_service(
        db=db,
        context=context,
        trigger_item_id=trigger_item_id,
        user_id=user_id,
        limit=limit
    )
    return res
