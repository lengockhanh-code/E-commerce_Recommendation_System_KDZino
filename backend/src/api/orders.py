"""Order & Checkout API Endpoints"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.src.database.connection import get_db
from backend.src.models.orm import User
from backend.src.models.schemas import OrderCreate, OrderResponse
from backend.src.security.dependencies import get_current_user, require_current_user
from backend.src.services.order_service import create_order, get_user_orders, get_order_by_id

router = APIRouter(prefix="/orders", tags=["Orders & Checkout"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def place_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Tạo đơn hàng mới (đặt hàng từ giỏ hàng - hỗ trợ cả khách vãng lai & khách đăng nhập)"""
    user_id = str(current_user.id) if current_user else None
    return create_order(db, data, user_id=user_id)


@router.get("", response_model=List[OrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user)
):
    """Lấy danh sách lịch sử đơn hàng của người dùng đang đăng nhập"""
    return get_user_orders(db, str(current_user.id))


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Xem thông tin chi tiết một đơn hàng theo mã order_id"""
    user_id = str(current_user.id) if current_user else None
    order = get_order_by_id(db, order_id, user_id=user_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Đơn hàng '{order_id}' không tồn tại"
        )
    return order
