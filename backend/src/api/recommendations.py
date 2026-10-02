"""Product Recommendation Endpoints"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.orm import User
from backend.src.models.schemas import RecommendationResponse, RecommendationRequest
from backend.src.security.dependencies import get_current_user
from backend.src.services.recommendation_service import get_recommendations

router = APIRouter(prefix="/recommendations", tags=["Product Recommendations"])


from typing import Literal
from uuid import UUID
from backend.src.services.personalization_service import recommendation_feed


@router.get("/feed")
def personalized_feed(
    context: Literal["home", "product_detail", "cart"] = "home",
    item_id: Optional[str] = Query(None, max_length=100),
    session_id: Optional[UUID] = None,
    limit: int = Query(12, ge=1, le=50),
    exclude: Optional[str] = Query(None, max_length=10000),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    return recommendation_feed(db, str(current_user.id) if current_user else None,
        str(session_id) if session_id else None, context, item_id, limit,
        [value for value in (exclude or "").split(",") if value][:100])


@router.get("", response_model=RecommendationResponse)
def recommendations_get(
    context: str = Query("home", description="Ngữ cảnh: 'home', 'product_detail', 'cart'"),
    item_id: Optional[str] = Query(None, description="Mã sản phẩm tham chiếu khi ở trang chi tiết/giỏ hàng"),
    limit: int = Query(10, ge=1, le=50, description="Số lượng gợi ý trả về"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Lấy danh sách gợi ý sản phẩm phù hợp cho người dùng (GET)"""
    user_id = str(current_user.id) if current_user else None
    return get_recommendations(db, context=context, item_id=item_id, user_id=user_id, limit=limit)


@router.post("", response_model=RecommendationResponse)
def recommendations_post(
    req: RecommendationRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Lấy danh sách gợi ý sản phẩm phù hợp cho người dùng (POST)"""
    user_id = str(current_user.id) if current_user else None
    return get_recommendations(db, context=req.context, item_id=req.item_id, user_id=user_id, limit=req.limit)
